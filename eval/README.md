# Plan-agent eval harness

Measures how reliably the plan-reading agent gets the right answer on the two
experiments of the prototype, by running each task N times and comparing every
run against verified ground truth.

| task | plan | question | reference answer |
|---|---|---|---|
| `dimcheck` | `testplan.pdf` (synthetic, 1:100, one page) | "Check it for errors." No hint what kind of error or where. | bedroom chain dimension labeled 4.00 m, drawn 3.485 m; plus two weaker inconsistencies (see below) |
| `takeoff` | `realplan.pdf` (Macon-Bibb bid set, 44 sheets, 190 CAD layers) | "How many ceiling air vents do I need to buy for this renovation, what kinds are they, and how big?" | 35 supply diffusers in 7 types on M101 (28 ceiling + 7 sidewall), sizes/models from the M601 schedule, F/121 and M/123 rejected as room numbers |

Two conditions:

- `tools` (default): the prototype. Claude Code harness with Bash/Read/Write/Glob/Grep
  and `plan_tools.py` in an isolated working directory, so the agent can zoom, measure,
  snap to vector edges, toggle layers and mark. This reproduces how the original
  session ran.
- `naive`: the baseline. No tools; the pages are attached as images downscaled to
  1568 px on the long edge, which is what a plan pasted into a chat window turns into.

## Setup

```sh
python3 -m venv .venv
.venv/bin/pip install pymupdf claude-agent-sdk pillow
```

The `takeoff` task needs `realplan.pdf` in the repo root. It is not committed; download
it from the [Macon-Bibb County website](https://www.maconbibb.us/wp-content/uploads/2016/06/Attachment-C-Drawings.pdf)
(see the Setup section of the main README).

The runner uses the Claude Agent SDK, which drives the locally installed Claude Code
CLI, so it authenticates the same way your `claude` command does (login or
`ANTHROPIC_API_KEY`). Runs are billed like any Claude Code session.

## Run

```sh
# 5 runs of both tasks with tools (default condition), sequential
.venv/bin/python -m eval run --n 5

# both conditions, 3 runs each, two at a time, named batch
.venv/bin/python -m eval run --task dimcheck takeoff --condition tools naive --n 3 --parallel 2 --batch aug18

# pin model / effort, tighten caps
.venv/bin/python -m eval run --task takeoff --n 3 --model claude-opus-5 --effort high --max-budget 6 --max-turns 100
```

Every batch lands in `eval/runs/<batch>/`:

```
eval/runs/<batch>/
  config.json                 CLI arguments
  summary.json                aggregated metrics per task/condition
  report.md                   human-readable report (tables below come from here)
  <task>__<condition>/run_01/
     answer.json              structured answer (schema-validated by the SDK's output_format)
     answer.md                final assistant text
     score.json               metrics for this run
     meta.json                cost, turns, tool calls, plan_tools commands, images viewed, errors
     transcript.jsonl         every message; tool results truncated to 4 kB
     work/                    the agent's working dir (its zoom.png, marks, ad-hoc scripts)
```

Re-score a batch after changing a scorer or ground truth, or re-render its report:

```sh
.venv/bin/python -m eval score aug18
.venv/bin/python -m eval report aug18
```

Runs that already have a `score.json` are skipped on re-run unless `--force` is given,
so an interrupted batch can be resumed with the same `--batch` name.

Scorer tests (offline, no API calls): `.venv/bin/python -m unittest eval.tests.test_score`.

## What is measured

Per run the scorer produces a `score` in [0, 1] and a `pass` flag. Across runs the
report gives pass rate, score mean/std, cost, time, and two consistency measures:

- **answer agreement**: share of runs whose canonical answer equals the modal answer.
  For `dimcheck` the canonical answer is the set of ground-truth items found plus the
  false-positive count; for `takeoff` it is the per-type count vector (A, B, C, D, H, I, J).
- **per-field agreement** (`takeoff`): for each diffuser type, share of runs agreeing on
  the count, plus the std of the reported counts.

### dimcheck

| item | printed | drawn | weight |
|---|---|---|---|
| bedroom width, top chain (planted) | 4.00 m | 3.485 m | required for `pass`; 0.70 + up to 0.10 for measurement precision |
| chain sum vs. overall dimension | chain sums to 10.575 m, overall says 10.00 m | | +0.10 |
| living-room width, top chain (second wrong label) | 5.86 m | 5.80 m | +0.10 |
| bedroom door leaf and swing drawn 1.00 m above the wall opening (unintended, `draw_sector` direction) | | | +0.05, matched by text |
| area labels (31.2 / 13.4 / 6.9 m²) vs. computed room areas, or their sum 51.5 m² vs. the ~59 m² net floor area | | 37.1 / 14.2 / 7.7 m² | tracked, not scored |
| a wrong label (4.00 or 5.86) flagged with a measurement outside tolerance | | | primary: 0.35 partial credit; 5.86: no bonus, no penalty |
| any other numeric finding, incl. flagging a correct dimension (10.00, 30, 11.5, 7.00) | | | −0.15 each; blocks `pass` |
| qualitative remarks without numbers (e.g. "no windows drawn") | | | tracked, not scored |

Measurement tolerance is ±0.05 m; units are normalised (30 cm and 0.30 m are the same label).
The prompt only says "check it for errors" and the answer schema asks for a printed value,
a unit, the value found instead and a free-text category, so neither prompt nor schema
hints at dimensions, chains or areas. The scorer classifies findings by their numbers
alone (a finding with 4.00 printed and about 3.485 measured counts as the planted error
regardless of the category the agent chose).

### takeoff

"Ceiling air vents" has two defensible readings, and the scorer accepts both:

| reading | expected supply types | total | CFM | detected when |
|---|---|---|---|---|
| `all_supply` (the original session's answer) | A, B, C, D, H, I, J | 35 | 10,000 | the run reports H or I as supply |
| `ceiling_only` (H and I are sidewall grilles per M601 note 10) | A, B, C, D, J | 28 | 6,550 | the run reports neither H nor I |

Under `ceiling_only` the run must still say that the sidewall types H and I exist
(in `excluded_false_positives` or the summary); silently dropping seven supply grilles
costs 0.15 and blocks `pass`. Which reading a run took is reported per batch, so
disagreement about the interpretation shows up as a consistency finding of its own.

| component | weight |
|---|---|
| per-type counts (exact = 1, ±1 = 0.5) averaged over the types of the run's reading | 0.40 |
| Jaccard between reported and expected type set | 0.15 |
| total exact = 1, within ±2 = 0.5 | 0.15 |
| size correct per type (A 6", B 8", C 10", D 12", H 18×8, I 14×8, J 12×12 or 8") | 0.15 |
| no false-positive supply type (F, M, or any tag outside the set) | 0.10 |
| cross-verified: sheets_used names both M101 and M601 | 0.05 |
| sidewall types not acknowledged (`ceiling_only` only) | −0.15 |

`pass` requires the reading's total, all of its counts exact, no false-positive type,
and (for `ceiling_only`) the sidewall acknowledgement. Also tracked: model names
(SCD / 520D / SMD), total supply CFM within 3 % of the reading's expected value,
whether F/121 and M/123 were explicitly listed as rejected, return grilles and exhaust
fans mentioned, per-type count agreement across runs.

## Results so far

Two batches from 2026-08-18 are in `eval/runs/` (their `report.md` and `summary.json`
are committed; the agents' rendered images under `work/` and `pages/` are not):

| batch | task / condition | runs | pass | headline |
|---|---|---|---|---|
| `dimcheck30` | dimcheck / tools | 30 | 29 | planted error measured at 3.485 m in 30/30 (mean error 1 mm); chain sum and 5.86 label 30/30; one false positive |
| `dimcheck30` | dimcheck / naive | 30 | 0 | 4.00 label flagged in 28/30, measured within tolerance in 1/30; 7 runs with a false positive |
| `takeoff30` | takeoff / tools | 30 | 30 | identical per-type counts in all runs (A5 B4 C15 D1 H3 I4 J3), sizes/models 30/30, no false-positive types; 17 runs read "ceiling" as 28, 13 as 35 |

## Ground truth

Everything was re-derived from the PDFs with PyMuPDF on 2026-08-18, independent of the
original session's answer:

- `testplan.pdf`: wall edges from vector rectangles at x = 0, 0.30, 6.10, 6.215, 9.70,
  10.00 m from the building origin (chain labels 30 / 5.86 / 11.5 / 4.00 / 30 above them).
  The 5.86 label also does not match the drawn 5.80 m; flagging it is correct and scores
  as a bonus.
- `realplan.pdf`: page 32 is M101 (Mechanical New Work Floor Plan), page 34 is M601
  (Schedules). Pairing each single uppercase letter with the number directly below it in
  the plan area gives A 5, B 4, C 15, D 1, H 3, I 4, J 3, F 1 (121), M 1 (123). The M601
  GRILLES table shows F as a 24×24 egg-crate return grille (no airflow), and 121/123 sit
  next to room labels, so those two are false positives. The five A tags were checked
  visually (75, 75, 75, 90, 130 CFM hexagons). Total supply airflow of the 35 tags is
  exactly 10,000 CFM. H and I carry schedule note 10 ("double deflection sidewall
  grille"), I additionally says SIDEWALL in the throw column; the first smoke run
  excluded both from a "ceiling" count and that reading is accepted (see above).

## Notes and limits

- The agent runs with `permission_mode=bypassPermissions` inside its `work/` directory,
  with `setting_sources=[]` so your global CLAUDE.md, memory and skills do not leak into
  the runs. Bash is unrestricted; keep the machine you run this on in mind.
- Runs are non-deterministic; that is what the harness measures. Five runs per task is
  a reasonable minimum to see the spread. Typical cost per run with the Claude Code
  default model (Opus 5): `dimcheck/tools` about $1.40 and 5 min, `dimcheck/naive` about
  $0.36 and 2 min, `takeoff/tools` about $3.90 and 7 min. Use `--parallel` for batches.
- The agent's Bash tool runs a login shell, so `PATH` set by the harness does not reach
  it (pyenv shims win). The prompt therefore names the venv interpreter by absolute
  path. Keep that in mind if you move the venv.
- The structured answer comes from the SDK's `output_format` (JSON schema). If a run
  ends without one (budget or turn cap, error), the harness falls back to parsing the
  last assistant text; `meta.json` records `answer_source`.
- `plan_tools.py` is copied, not modified. Changing it changes the thing under test.
