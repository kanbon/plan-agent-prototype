"""CLI: python -m eval {run|score|report} ...

  run     execute N runs per task/condition, score each, write a report
  score   re-score an existing batch (after changing a scorer or ground truth)
  report  re-render summary.json / report.md for a batch
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import time
from pathlib import Path

from .agent import run_once
from .report import aggregate, render_markdown
from .score import score
from .tasks import ROOT, TASKS

RUNS_DIR = ROOT / "eval" / "runs"


def _batch_dir(name: str | None) -> Path:
    if name:
        p = Path(name)
        return p if p.is_absolute() else RUNS_DIR / name
    return RUNS_DIR / time.strftime("%Y%m%d_%H%M%S")


def _write_report(batch: Path) -> list[dict]:
    summaries = aggregate(batch)
    (batch / "summary.json").write_text(json.dumps(summaries, indent=2))
    md = render_markdown(summaries, batch)
    (batch / "report.md").write_text(md)
    return summaries


def _print_overview(summaries: list[dict]) -> None:
    print()
    print(f"{'task':9} {'cond':6} {'runs':>5} {'pass':>6} {'score':>12} {'agree':>6} {'$/run':>7} {'s/run':>6}")
    for s in summaries:
        sm = s["score_mean"]; sd = s["score_std"]
        print(f"{s['task']:9} {s['condition']:6} {s['n_scored']:>2}/{s['n_runs']:<2} "
              f"{'n/a' if s['pass_rate'] is None else f'{100*s['pass_rate']:.0f}%':>6} "
              f"{'n/a' if sm is None else f'{sm:.2f}±{sd:.2f}':>12} "
              f"{'n/a' if s['answer_agreement'] is None else f'{100*s['answer_agreement']:.0f}%':>6} "
              f"{'n/a' if s['cost_usd_mean'] is None else f'{s['cost_usd_mean']:.2f}':>7} "
              f"{'n/a' if s['duration_s_mean'] is None else f'{s['duration_s_mean']:.0f}':>6}")
    print()


async def _run_batch(args: argparse.Namespace) -> Path:
    batch = _batch_dir(args.batch)
    batch.mkdir(parents=True, exist_ok=True)
    (batch / "config.json").write_text(json.dumps(vars(args), indent=2, default=str))
    sem = asyncio.Semaphore(args.parallel)

    async def one(task_id: str, cond: str, i: int) -> None:
        task = TASKS[task_id]
        run_dir = batch / f"{task_id}__{cond}" / f"run_{i:02d}"
        if (run_dir / "score.json").exists() and not args.force:
            print(f"  skip {task_id}/{cond}/run_{i:02d} (already scored)")
            return
        if run_dir.exists():
            shutil.rmtree(run_dir)          # unscored leftover from an earlier attempt
        async with sem:
            print(f"  start {task_id}/{cond}/run_{i:02d}", flush=True)
            res = await run_once(task, cond, run_dir, model=args.model, effort=args.effort,
                                 max_turns=args.max_turns, max_budget_usd=args.max_budget,
                                 verbose=args.verbose)
        m = res["meta"]
        transport_failure = bool(m.get("error")) or (m.get("is_error") and m.get("api_error_status"))
        if transport_failure and res["answer"] is None:
            # rate limit / API error / crash: leave unscored so a re-run of the batch retries it
            print(f"  FAIL  {task_id}/{cond}/run_{i:02d}  {m.get('error') or m.get('errors') or m.get('api_error_status')} "
                  f"(unscored, re-run the batch to retry)", flush=True)
            return
        sc = score(task, res["answer"])
        (run_dir / "score.json").write_text(json.dumps(sc, indent=2))
        print(f"  done  {task_id}/{cond}/run_{i:02d}  score={sc['score']:.2f} pass={sc['pass']} "
              f"cost=${m.get('total_cost_usd') or 0:.2f} turns={m.get('num_turns')} "
              f"{'ERROR: ' + str(m['error']) if m.get('error') else ''}", flush=True)

    jobs = [one(t, c, i) for t in args.task for c in args.condition for i in range(1, args.n + 1)]
    await asyncio.gather(*jobs)
    return batch


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m eval", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run the agent N times per task/condition and score")
    r.add_argument("--task", nargs="+", choices=sorted(TASKS), default=sorted(TASKS))
    r.add_argument("--condition", nargs="+", choices=["tools", "naive"], default=["tools"])
    r.add_argument("--n", type=int, default=3, help="runs per task/condition (default 3)")
    r.add_argument("--parallel", type=int, default=1, help="concurrent runs (default 1)")
    r.add_argument("--model", default=None, help="model alias or id; default = Claude Code default")
    r.add_argument("--effort", default=None, choices=["low", "medium", "high", "xhigh", "max"])
    r.add_argument("--max-turns", type=int, default=120)
    r.add_argument("--max-budget", type=float, default=8.0, help="USD cap per run (default 8)")
    r.add_argument("--batch", default=None, help="batch name or path under eval/runs (default: timestamp)")
    r.add_argument("--force", action="store_true", help="re-run runs that already have a score")
    r.add_argument("--verbose", action="store_true", help="echo assistant text while running")

    s = sub.add_parser("score", help="re-score all runs in a batch from their answer.json")
    s.add_argument("batch")

    p = sub.add_parser("report", help="re-render summary.json and report.md for a batch")
    p.add_argument("batch")

    args = ap.parse_args(argv)

    if args.cmd == "run":
        batch = asyncio.run(_run_batch(args))
    elif args.cmd == "score":
        batch = _batch_dir(args.batch)
        for group in sorted(p for p in batch.iterdir() if p.is_dir() and "__" in p.name):
            task = TASKS[group.name.split("__", 1)[0]]
            for rd in sorted(p for p in group.iterdir() if p.is_dir()):
                af = rd / "answer.json"
                answer = json.loads(af.read_text()) if af.exists() else None
                (rd / "score.json").write_text(json.dumps(score(task, answer), indent=2))
    else:
        batch = _batch_dir(args.batch)

    summaries = _write_report(batch)
    _print_overview(summaries)
    print(f"report: {batch / 'report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
