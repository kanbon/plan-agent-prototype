"""Aggregate scored runs into consistency metrics and a report.

A batch directory looks like:
  <batch>/<task>__<condition>/run_01/{meta.json, answer.json, score.json, ...}

`aggregate()` returns one summary dict per (task, condition) group; `render_markdown()`
turns the summaries into report.md. Everything is stdlib.
"""
from __future__ import annotations

import json
import statistics as st
from collections import Counter
from pathlib import Path
from typing import Any

from .tasks import TASKS


def _load_group(group_dir: Path) -> list[dict[str, Any]]:
    runs = []
    for rd in sorted(p for p in group_dir.iterdir() if p.is_dir() and p.name.startswith("run_")):
        rec: dict[str, Any] = {"run": rd.name}
        for name in ("meta", "answer", "score"):
            f = rd / f"{name}.json"
            rec[name] = json.loads(f.read_text()) if f.exists() else None
        runs.append(rec)
    return runs


def _mean(xs: list[float]) -> float | None:
    xs = [x for x in xs if x is not None]
    return round(st.fmean(xs), 3) if xs else None


def _std(xs: list[float]) -> float | None:
    xs = [x for x in xs if x is not None]
    return round(st.pstdev(xs), 3) if len(xs) > 1 else (0.0 if xs else None)


def _rate(bools: list[Any]) -> float | None:
    bools = [b for b in bools if b is not None]
    return round(sum(1 for b in bools if b) / len(bools), 3) if bools else None


def _agreement(keys: list[Any]) -> tuple[float | None, Any, int]:
    """Fraction of runs that gave the modal answer, the mode itself, and #distinct answers."""
    keys = [k for k in keys if k is not None]
    if not keys:
        return None, None, 0
    c = Counter(keys)
    mode, n = c.most_common(1)[0]
    return round(n / len(keys), 3), mode, len(c)


def summarize_group(task_id: str, condition: str, runs: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [r["score"] for r in runs if r["score"]]
    metas = [r["meta"] for r in runs if r["meta"]]
    s: dict[str, Any] = {
        "task": task_id, "condition": condition,
        "n_runs": len(runs),
        "n_scored": len(scores),
        "n_parsed": sum(1 for x in scores if x.get("parsed")),
        "n_errors": sum(1 for m in metas if m.get("error") or m.get("is_error")),
        "pass_rate": _rate([x.get("pass") for x in scores]),
        "score_mean": _mean([x.get("score") for x in scores]),
        "score_std": _std([x.get("score") for x in scores]),
        "score_min": min((x.get("score", 0) for x in scores), default=None),
        "score_max": max((x.get("score", 0) for x in scores), default=None),
        "cost_usd_mean": _mean([m.get("total_cost_usd") for m in metas]),
        "cost_usd_std": _std([m.get("total_cost_usd") for m in metas]),
        "cost_usd_total": round(sum(m.get("total_cost_usd") or 0 for m in metas), 3),
        "duration_s_mean": _mean([(m.get("duration_ms") or 0) / 1000 for m in metas]),
        "turns_mean": _mean([m.get("num_turns") for m in metas]),
        "tool_calls_mean": _mean([sum((m.get("tool_calls") or {}).values()) for m in metas]),
        "images_viewed_mean": _mean([m.get("images_viewed") for m in metas]),
        "plan_tools_usage": dict(sum((Counter(m.get("plan_tools_cmds") or {}) for m in metas), Counter())),
        "models": sorted({k for m in metas for k in (m.get("model_usage") or {})}),
    }

    if task_id == "dimcheck":
        keys = [tuple(x.get("matched_ids") or []) + (f"FP={x.get('false_positives', 0)}",) for x in scores]
        agree, mode, distinct = _agreement(keys)
        s.update({
            "found_primary_rate": _rate([x.get("found_primary") for x in scores]),
            "found_primary_or_label_rate": _rate([x.get("found_primary") or x.get("found_primary_label_only")
                                                  for x in scores]),
            "found_chain_sum_rate": _rate([x.get("found_chain_sum") for x in scores]),
            "found_living_5.86_rate": _rate([x.get("found_living_5.86") for x in scores]),
            "found_door_swing_rate": _rate([x.get("found_door_swing") for x in scores]),
            "area_findings_mean": _mean([x.get("area_findings") for x in scores]),
            "false_positives_mean": _mean([x.get("false_positives") for x in scores]),
            "runs_with_false_positives": sum(1 for x in scores if x.get("false_positives")),
            "other_observations_mean": _mean([x.get("other_observations") for x in scores]),
            "primary_abs_error_m_mean": _mean([x.get("primary_abs_error_m") for x in scores]),
            "primary_measured_values": [x.get("primary_measured_m") for x in scores],
            "n_findings_values": [x.get("n_findings") for x in scores],
            "answer_agreement": agree, "answer_mode": list(mode) if mode else None,
            "answer_distinct": distinct,
        })
    elif task_id == "takeoff":
        vecs = [tuple(x["counts_vector"]) if x.get("counts_vector") else None for x in scores]
        agree, mode, distinct = _agreement(vecs)
        interp_agree, interp_mode, _ = _agreement([x.get("interpretation") for x in scores])
        tags = list(TASKS["takeoff"].ground_truth["supply"].keys())
        per_tag: dict[str, Any] = {}
        for i, t in enumerate(tags):
            vals = [x["per_type"][t]["reported"] for x in scores if x.get("per_type")]
            a, m, d = _agreement(vals)
            per_tag[t] = {
                "expected": TASKS["takeoff"].ground_truth["supply"][t]["count"],
                "reported": vals,
                "exact_rate": _rate([x["per_type"][t]["exact"] for x in scores if x.get("per_type")]),
                "agreement": a, "mode": m, "distinct": d,
                "std": _std([v for v in vals if v is not None]),
                "size_ok_rate": _rate([x["per_type"][t]["size_ok"] for x in scores if x.get("per_type")]),
            }
        s.update({
            "interpretations": dict(Counter(x.get("interpretation") for x in scores)),
            "interpretation_agreement": interp_agree, "interpretation_mode": interp_mode,
            "sidewall_noted_rate": _rate([x.get("sidewall_noted") for x in scores]),
            "total_exact_rate": _rate([x.get("total_exact") for x in scores]),
            "total_within_2_rate": _rate([x.get("total_within_2") for x in scores]),
            "totals_reported": [f"{x.get('reported_total')}/{x.get('expected_total')}" for x in scores],
            "count_exact_frac_mean": _mean([x.get("count_exact_frac") for x in scores]),
            "count_abs_error_sum_mean": _mean([x.get("count_abs_error_sum") for x in scores]),
            "type_jaccard_mean": _mean([x.get("type_jaccard") for x in scores]),
            "size_ok_frac_mean": _mean([x.get("size_ok_frac") for x in scores]),
            "model_ok_frac_mean": _mean([x.get("model_ok_frac") for x in scores]),
            "false_positive_rate": _rate([bool(x.get("false_positive_tags")) for x in scores]),
            "false_positive_tags_seen": dict(Counter(t for x in scores for t in (x.get("false_positive_tags") or []))),
            "explicit_exclusion_rate": _rate([x.get("false_positives_excluded_explicitly") for x in scores]),
            "cross_verified_rate": _rate([x.get("cross_verified") for x in scores]),
            "cfm_ok_rate": _rate([x.get("cfm_ok") for x in scores]),
            "answer_agreement": agree, "answer_mode": list(mode) if mode else None,
            "answer_distinct": distinct,
            "per_tag": per_tag,
        })
    return s


def aggregate(batch_dir: Path) -> list[dict[str, Any]]:
    out = []
    for g in sorted(p for p in batch_dir.iterdir() if p.is_dir() and "__" in p.name):
        task_id, condition = g.name.split("__", 1)
        runs = _load_group(g)
        if runs:
            out.append(summarize_group(task_id, condition, runs))
    return out


# ---------------------------------------------------------------------------
# markdown
# ---------------------------------------------------------------------------

def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def _f(x: Any, nd: int = 2) -> str:
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def render_markdown(summaries: list[dict[str, Any]], batch_dir: Path) -> str:
    L: list[str] = [f"# Plan-agent eval report", "", f"Batch: `{batch_dir}`", ""]

    L += ["## Overview", "",
          "| task | condition | runs | pass rate | score mean ± std | answer agreement | distinct answers | cost/run | time/run | turns |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for s in summaries:
        L.append(
            f"| {s['task']} | {s['condition']} | {s['n_scored']}/{s['n_runs']} | {_pct(s['pass_rate'])} | "
            f"{_f(s['score_mean'])} ± {_f(s['score_std'])} | {_pct(s['answer_agreement'])} | "
            f"{s['answer_distinct']} | ${_f(s['cost_usd_mean'])} | {_f(s['duration_s_mean'], 0)} s | {_f(s['turns_mean'], 1)} |")
    L.append("")
    L.append("Answer agreement = share of runs whose canonical answer equals the modal answer "
             "(dimcheck: set of ground-truth items found + false-positive count; takeoff: per-type count "
             "vector A,B,C,D,H,I,J, so a different reading of 'ceiling vents' counts as a different answer).")
    L.append("")

    for s in summaries:
        L += [f"## {s['task']} / {s['condition']}", ""]
        if s["task"] == "dimcheck":
            L += [
                "| metric | value |", "|---|---|",
                f"| planted error found (4.00 vs 3.485 m) | {_pct(s['found_primary_rate'])} |",
                f"| planted error at least flagged | {_pct(s['found_primary_or_label_rate'])} |",
                f"| chain-sum inconsistency found (10.575 vs 10.00) | {_pct(s['found_chain_sum_rate'])} |",
                f"| living-room 5.86 vs 5.80 found | {_pct(s['found_living_5.86_rate'])} |",
                f"| misplaced bedroom door swing found | {_pct(s['found_door_swing_rate'])} |",
                f"| area labels flagged per run (of 3, not scored) | {_f(s['area_findings_mean'])} |",
                f"| runs with false positives | {s['runs_with_false_positives']}/{s['n_scored']} (mean {_f(s['false_positives_mean'])}) |",
                f"| qualitative remarks per run (not scored) | {_f(s['other_observations_mean'])} |",
                f"| measured bedroom width, abs. error mean | {_f(s['primary_abs_error_m_mean'], 3)} m |",
                f"| measured values reported | {s['primary_measured_values']} |",
                f"| findings per run | {s['n_findings_values']} |",
                f"| modal answer | {s['answer_mode']} |",
                "",
            ]
        else:
            L += [
                "| metric | value |", "|---|---|",
                f"| interpretation of 'ceiling vents' | {s['interpretations']} (agreement {_pct(s['interpretation_agreement'])}) |",
                f"| sidewall types H/I acknowledged | {_pct(s['sidewall_noted_rate'])} |",
                f"| total exact (35 all supply / 28 ceiling only) | {_pct(s['total_exact_rate'])} (reported/expected: {s['totals_reported']}) |",
                f"| total within ±2 | {_pct(s['total_within_2_rate'])} |",
                f"| per-type counts exact (mean over the types of each run's interpretation) | {_pct(s['count_exact_frac_mean'])} |",
                f"| summed abs. count error, mean | {_f(s['count_abs_error_sum_mean'])} |",
                f"| type set Jaccard, mean | {_f(s['type_jaccard_mean'])} |",
                f"| sizes correct (mean over types) | {_pct(s['size_ok_frac_mean'])} |",
                f"| models correct (mean over types) | {_pct(s['model_ok_frac_mean'])} |",
                f"| runs reporting a false-positive type | {_pct(s['false_positive_rate'])} {s['false_positive_tags_seen'] or ''} |",
                f"| F/121, M/123 explicitly excluded | {_pct(s['explicit_exclusion_rate'])} |",
                f"| cross-verified M101 + M601 | {_pct(s['cross_verified_rate'])} |",
                f"| total supply CFM within 3% of expected (10,000 / 6,550) | {_pct(s['cfm_ok_rate'])} |",
                f"| modal count vector (A,B,C,D,H,I,J) | {s['answer_mode']} |",
                "",
                "| type | expected | reported per run | exact rate | agreement | std | size ok |",
                "|---|---|---|---|---|---|---|",
            ]
            for t, p in s["per_tag"].items():
                L.append(f"| {t} | {p['expected']} | {p['reported']} | {_pct(p['exact_rate'])} | "
                         f"{_pct(p['agreement'])} | {_f(p['std'])} | {_pct(p['size_ok_rate'])} |")
            L.append("")
        L += [
            f"Process: {_f(s['tool_calls_mean'], 1)} tool calls/run, {_f(s['images_viewed_mean'], 1)} images viewed/run, "
            f"plan_tools usage {s['plan_tools_usage'] or '{}'}; errors: {s['n_errors']}; "
            f"total cost ${_f(s['cost_usd_total'])}.",
            "",
        ]
    return "\n".join(L)
