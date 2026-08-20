"""Run one evaluation episode: the plan-reading agent on one task, in an isolated workdir.

Backend: Claude Agent SDK (Claude Code as a library). This is the same harness the
prototype ran in (Bash + Read over `plan_tools.py`), so the eval measures the prototype
as it actually operates.

Two conditions:
  tools   Bash/Read/Write/Glob/Grep + plan_tools.py in the workdir (the prototype).
  naive   no tools; the plan pages are attached as downscaled images (max 1568 px on the
          long edge), like pasting the PDF into a chat window. The baseline.

Each run writes into <run_dir>:
  meta.json          options, timing, cost, tool-call stats, errors
  transcript.jsonl   every message (tool inputs, truncated tool results, assistant text)
  answer.json        the structured answer (schema-validated by the SDK when it arrives
                     via output_format; otherwise parsed from the final text)
  answer.md          the final assistant text, for humans
  work/              the agent's working directory (its PNGs, marks, scripts)
"""
from __future__ import annotations

import asyncio
import base64
import dataclasses
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from .tasks import ROOT, Task

VENV_BIN = Path(sys.executable).resolve().parent

_JSON_OBJ = re.compile(r"\{.*\}", re.S)

AUTONOMY_NOTE = (
    "You are running unattended inside an evaluation. Nobody will answer questions, so "
    "never ask; make reasonable assumptions and finish. Do all the work yourself (no "
    "subagents). When you are done, give the final answer in the requested JSON structure. "
    "Keep intermediate narration short; the JSON answer is what gets scored."
)


# ---------------------------------------------------------------------------
# workdir preparation
# ---------------------------------------------------------------------------

def prepare_workdir(task: Task, run_dir: Path) -> Path:
    work = run_dir / "work"
    work.mkdir(parents=True, exist_ok=True)
    pdf_link = work / task.pdf
    if not pdf_link.exists():
        os.symlink(task.pdf_path, pdf_link)
    shutil.copy(ROOT / "plan_tools.py", work / "plan_tools.py")
    return work


def render_pages(task: Task, run_dir: Path, max_edge: int = 1568) -> list[Path]:
    """Render the pages for the naive condition as JPEGs with the long edge at max_edge px.
    1568 px is what a chat attachment gets after the API downscales it."""
    import pymupdf  # local import keeps the SDK path import-light

    pages_dir = run_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(task.pdf_path)
    idx = task.naive_pages if task.naive_pages is not None else list(range(len(doc)))
    out: list[Path] = []
    for i in idx:
        page = doc[i]
        scale = max_edge / max(page.rect.width, page.rect.height)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale))
        p = pages_dir / f"page_{i:02d}.jpg"
        pix.save(p, jpg_quality=85)
        out.append(p)
    return out


# ---------------------------------------------------------------------------
# message serialization
# ---------------------------------------------------------------------------

def _trunc(s: str, n: int = 4000) -> str:
    return s if len(s) <= n else s[:n] + f"... [truncated {len(s) - n} chars]"


def serialize_message(msg: Any) -> dict[str, Any]:
    from claude_agent_sdk import (AssistantMessage, ResultMessage, SystemMessage, TextBlock,
                                  ThinkingBlock, ToolResultBlock, ToolUseBlock, UserMessage)

    if isinstance(msg, AssistantMessage):
        blocks = []
        for b in msg.content:
            if isinstance(b, TextBlock):
                blocks.append({"type": "text", "text": b.text})
            elif isinstance(b, ThinkingBlock):
                # summarised reasoning (requested via thinking.display); empty if the model omits it
                blocks.append({"type": "thinking", "text": _trunc(b.thinking or "", 40000)})
            elif isinstance(b, ToolUseBlock):
                blocks.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
            else:
                blocks.append({"type": type(b).__name__})
        return {"role": "assistant", "model": getattr(msg, "model", None), "content": blocks}
    if isinstance(msg, UserMessage):
        c = msg.content
        if isinstance(c, str):
            return {"role": "user", "content": _trunc(c)}
        blocks = []
        for b in c:
            if isinstance(b, ToolResultBlock):
                content = b.content
                if isinstance(content, list):
                    parts = []
                    for x in content:
                        if isinstance(x, dict) and x.get("type") == "text":
                            parts.append(_trunc(x.get("text", "")))
                        elif isinstance(x, dict) and x.get("type") == "image":
                            parts.append("[image]")
                        else:
                            parts.append(f"[{type(x).__name__}]")
                    content = parts
                elif isinstance(content, str):
                    content = _trunc(content)
                blocks.append({"type": "tool_result", "tool_use_id": b.tool_use_id,
                               "is_error": bool(getattr(b, "is_error", False)), "content": content})
            elif isinstance(b, TextBlock):
                blocks.append({"type": "text", "text": _trunc(b.text)})
            else:
                blocks.append({"type": type(b).__name__})
        return {"role": "user", "content": blocks}
    if isinstance(msg, ResultMessage):
        d = dataclasses.asdict(msg)
        d["role"] = "result"
        return d
    if isinstance(msg, SystemMessage):
        return {"role": "system", "subtype": msg.subtype,
                "data": {k: v for k, v in (msg.data or {}).items() if k in ("model", "tools", "permissionMode", "cwd")}}
    return {"role": type(msg).__name__}


def parse_answer_from_text(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    m = _JSON_OBJ.search(text)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------

async def run_once(
    task: Task,
    condition: str,
    run_dir: Path,
    *,
    model: str | None = None,
    effort: str | None = None,
    max_turns: int = 120,
    max_budget_usd: float | None = 8.0,
    verbose: bool = False,
) -> dict[str, Any]:
    from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock,
                                  ToolUseBlock, query)

    run_dir.mkdir(parents=True, exist_ok=True)
    work = prepare_workdir(task, run_dir)
    t0 = time.time()

    env = {
        "PATH": f"{VENV_BIN}:{os.environ.get('PATH', '')}",
        "VIRTUAL_ENV": str(VENV_BIN.parent),
        "PYTHONWARNINGS": "ignore",
    }
    common = dict(
        cwd=str(work),
        env=env,
        setting_sources=[],
        permission_mode="bypassPermissions",
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        output_format={"type": "json_schema", "schema": task.schema},
        thinking={"type": "adaptive", "display": "summarized"},   # keep the reasoning summary in the transcript
        max_buffer_size=64 * 1024 * 1024,   # big tool results (full-page text dumps) exceed the 1 MB default
        model=model,
        effort=effort,
        system_prompt={"type": "preset", "preset": "claude_code", "append": AUTONOMY_NOTE},
    )

    if condition == "tools":
        tools = ["Bash", "Read", "Write", "Edit", "Glob", "Grep"]
        options = ClaudeAgentOptions(
            tools=tools, allowed_tools=tools,
            disallowed_tools=["WebSearch", "WebFetch", "Task", "Agent", "Skill", "NotebookEdit"],
            **common,
        )
        prompt: Any = task.instructions
        pages: list[Path] = []
    elif condition == "naive":
        pages = render_pages(task, run_dir)
        options = ClaudeAgentOptions(
            tools=[], allowed_tools=[],
            disallowed_tools=["Bash", "Read", "Write", "Edit", "Glob", "Grep", "WebSearch",
                              "WebFetch", "Task", "Agent", "Skill", "NotebookEdit"],
            **common,
        )
        text = (
            f"{task.framing}\n\nThe plan is attached as {len(pages)} page image(s). You have no "
            f"tools; answer from what you can see."
        )
        content: list[dict[str, Any]] = [{"type": "text", "text": text}]
        for p in pages:
            content.append({"type": "image", "source": {
                "type": "base64", "media_type": "image/jpeg",
                "data": base64.b64encode(p.read_bytes()).decode()}})

        async def _gen():
            yield {"type": "user", "message": {"role": "user", "content": content}}

        prompt = _gen()
    else:
        raise ValueError(f"unknown condition {condition!r}")

    meta: dict[str, Any] = {
        "task": task.id, "condition": condition, "model": model, "effort": effort,
        "max_turns": max_turns, "max_budget_usd": max_budget_usd,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_pages_attached": len(pages),
        "tool_calls": {}, "plan_tools_cmds": {}, "images_viewed": 0, "bash_calls": 0,
        "n_assistant_messages": 0, "error": None,
    }
    answer: dict[str, Any] | None = None
    final_text: str | None = None
    result_meta: dict[str, Any] = {}

    with open(run_dir / "transcript.jsonl", "w") as tf:
        try:
            async for msg in query(prompt=prompt, options=options):
                rec = serialize_message(msg)
                tf.write(json.dumps(rec, default=str) + "\n")
                tf.flush()
                if isinstance(msg, AssistantMessage):
                    meta["n_assistant_messages"] += 1
                    for b in msg.content:
                        if isinstance(b, ToolUseBlock):
                            if b.name == "StructuredOutput":   # the SDK's answer channel, not a tool use
                                continue
                            meta["tool_calls"][b.name] = meta["tool_calls"].get(b.name, 0) + 1
                            if b.name == "Bash":
                                meta["bash_calls"] += 1
                                cmd = str(b.input.get("command", ""))
                                for m in re.finditer(r"plan_tools\.py\s+(\w+)", cmd):
                                    k = m.group(1)
                                    meta["plan_tools_cmds"][k] = meta["plan_tools_cmds"].get(k, 0) + 1
                            if b.name == "Read":
                                fp = str(b.input.get("file_path", ""))
                                if fp.lower().endswith((".png", ".jpg", ".jpeg")):
                                    meta["images_viewed"] += 1
                        elif isinstance(b, TextBlock) and b.text.strip():
                            final_text = b.text
                            if verbose:
                                print(f"    [{task.id}] {b.text[:160].replace(chr(10), ' ')}", flush=True)
                elif isinstance(msg, ResultMessage):
                    result_meta = {
                        "subtype": msg.subtype, "is_error": msg.is_error,
                        "terminal_reason": msg.terminal_reason, "num_turns": msg.num_turns,
                        "duration_ms": msg.duration_ms, "duration_api_ms": msg.duration_api_ms,
                        "total_cost_usd": msg.total_cost_usd, "usage": msg.usage,
                        "model_usage": msg.model_usage, "errors": msg.errors,
                        "api_error_status": msg.api_error_status, "session_id": msg.session_id,
                    }
                    if msg.structured_output is not None:
                        answer = msg.structured_output
                    if msg.result:
                        final_text = msg.result
        except Exception as e:  # noqa: BLE001, record the error and move on to the next run
            meta["error"] = f"{type(e).__name__}: {e}"

    if answer is None:
        answer = parse_answer_from_text(final_text)
        meta["answer_source"] = "parsed_from_text" if answer is not None else "none"
    else:
        meta["answer_source"] = "structured_output"

    meta.update(result_meta)
    meta["wall_seconds"] = round(time.time() - t0, 1)
    (run_dir / "answer.json").write_text(json.dumps(answer, indent=2, ensure_ascii=False))
    (run_dir / "answer.md").write_text(final_text or "")
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2, default=str))
    return {"meta": meta, "answer": answer}
