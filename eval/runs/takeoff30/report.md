# Plan-agent eval report

Batch: `/Users/simonprast/git/plan-agent-prototype/eval/runs/takeoff30`

## Overview

| task | condition | runs | pass rate | score mean ± std | answer agreement | distinct answers | cost/run | time/run | turns |
|---|---|---|---|---|---|---|---|---|---|
| takeoff | tools | 30/30 | 100% | 1.00 ± 0.00 | 57% | 2 | $3.91 | 398 s | 38.9 |

Answer agreement = share of runs whose canonical answer equals the modal answer (dimcheck: set of ground-truth items found + false-positive count; takeoff: per-type count vector A,B,C,D,H,I,J, so a different reading of 'ceiling vents' counts as a different answer).

## takeoff / tools

| metric | value |
|---|---|
| interpretation of 'ceiling vents' | {'ceiling_only': 17, 'all_supply': 13} (agreement 57%) |
| sidewall types H/I acknowledged | 100% |
| total exact (35 all supply / 28 ceiling only) | 100% (reported/expected: ['28/28', '35/35', '28/28', '28/28', '28/28', '35/35', '28/28', '28/28', '35/35', '35/35', '28/28', '35/35', '28/28', '28/28', '35/35', '28/28', '28/28', '35/35', '28/28', '35/35', '35/35', '28/28', '35/35', '28/28', '28/28', '28/28', '35/35', '35/35', '35/35', '28/28']) |
| total within ±2 | 100% |
| per-type counts exact (mean over the types of each run's interpretation) | 100% |
| summed abs. count error, mean | 0.00 |
| type set Jaccard, mean | 1.00 |
| sizes correct (mean over types) | 100% |
| models correct (mean over types) | 100% |
| runs reporting a false-positive type | 0%  |
| F/121, M/123 explicitly excluded | 73% |
| cross-verified M101 + M601 | 100% |
| total supply CFM within 3% of expected (10,000 / 6,550) | 100% |
| modal count vector (A,B,C,D,H,I,J) | [5, 4, 15, 1, None, None, 3] |

| type | expected | reported per run | exact rate | agreement | std | size ok |
|---|---|---|---|---|---|---|
| A | 5 | [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5] | 100% | 100% | 0.00 | 100% |
| B | 4 | [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4] | 100% | 100% | 0.00 | 100% |
| C | 15 | [15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15] | 100% | 100% | 0.00 | 100% |
| D | 1 | [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1] | 100% | 100% | 0.00 | 100% |
| H | 3 | [None, 3, None, None, None, 3, None, None, 3, 3, None, 3, None, None, 3, None, None, 3, None, 3, 3, None, 3, None, None, None, 3, 3, 3, None] | 43% | 100% | 0.00 | 43% |
| I | 4 | [None, 4, None, None, None, 4, None, None, 4, 4, None, 4, None, None, 4, None, None, 4, None, 4, 4, None, 4, None, None, None, 4, 4, 4, None] | 43% | 100% | 0.00 | 43% |
| J | 3 | [3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3] | 100% | 100% | 0.00 | 100% |

Process: 33.8 tool calls/run, 9.7 images viewed/run, plan_tools usage {'zoom': 231, 'mark': 8, 'overview': 36, 'text': 2, '2': 1}; errors: 0; total cost $117.20.
