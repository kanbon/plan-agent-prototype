# Plan-agent eval report

Batch: `/Users/simonprast/git/plan-agent-prototype/eval/runs/smoke`

## Overview

| task | condition | runs | pass rate | score mean ± std | answer agreement | distinct answers | cost/run | time/run | turns |
|---|---|---|---|---|---|---|---|---|---|
| dimcheck | naive | 1/1 | 100% | 0.81 ± 0.00 | 100% | 1 | $0.55 | 82 s | 2.0 |
| dimcheck | tools | 1/1 | 100% | 1.00 ± 0.00 | 100% | 1 | $2.61 | 189 s | 13.0 |
| takeoff | tools | 1/1 | 100% | 1.00 ± 0.00 | 100% | 1 | $3.88 | 389 s | 28.0 |

Answer agreement = share of runs whose canonical answer equals the modal answer (dimcheck: set of ground-truth items found + false-positive count; takeoff: per-type count vector A,B,C,D,H,I,J, so a different reading of 'ceiling vents' counts as a different answer).

## dimcheck / naive

| metric | value |
|---|---|
| planted error found (4.00 vs 3.485 m) | 100% |
| planted error at least flagged | 100% |
| chain-sum inconsistency found (10.575 vs 10.00) | 100% |
| living-room 5.86 vs 5.80 found | 0% |
| runs with false positives | 0/1 (mean 0.00) |
| qualitative remarks per run (not scored) | 0.00 |
| measured bedroom width, abs. error mean | 0.045 m |
| measured values reported | [3.44] |
| findings per run | [4] |
| modal answer | ['area_bad', 'area_wohnen', 'bedroom_4.00', 'chain_sum', 'FP=0'] |

Process: 1.0 tool calls/run, 0.0 images viewed/run, plan_tools usage {}; errors: 0; total cost $0.55.

## dimcheck / tools

| metric | value |
|---|---|
| planted error found (4.00 vs 3.485 m) | 100% |
| planted error at least flagged | 100% |
| chain-sum inconsistency found (10.575 vs 10.00) | 100% |
| living-room 5.86 vs 5.80 found | 100% |
| runs with false positives | 0/1 (mean 0.00) |
| qualitative remarks per run (not scored) | 0.00 |
| measured bedroom width, abs. error mean | 0.000 m |
| measured values reported | [3.485] |
| findings per run | [6] |
| modal answer | ['area_bad', 'area_schlafen', 'area_wohnen', 'bedroom_4.00', 'chain_sum', 'living_5.86', 'FP=0'] |

Process: 0.0 tool calls/run, 0.0 images viewed/run, plan_tools usage {}; errors: 0; total cost $2.61.

## takeoff / tools

| metric | value |
|---|---|
| interpretation of 'ceiling vents' | {'ceiling_only': 1} (agreement 100%) |
| sidewall types H/I acknowledged | 100% |
| total exact (35 all supply / 28 ceiling only) | 100% (reported/expected: ['28/28']) |
| total within ±2 | 100% |
| per-type counts exact (mean over the types of each run's interpretation) | 100% |
| summed abs. count error, mean | 0.00 |
| type set Jaccard, mean | 1.00 |
| sizes correct (mean over types) | 100% |
| models correct (mean over types) | 100% |
| runs reporting a false-positive type | 0%  |
| F/121, M/123 explicitly excluded | 0% |
| cross-verified M101 + M601 | 100% |
| total supply CFM within 3% of expected (10,000 / 6,550) | 100% |
| modal count vector (A,B,C,D,H,I,J) | [5, 4, 15, 1, None, None, 3] |

| type | expected | reported per run | exact rate | agreement | std | size ok |
|---|---|---|---|---|---|---|
| A | 5 | [5] | 100% | 100% | 0.00 | 100% |
| B | 4 | [4] | 100% | 100% | 0.00 | 100% |
| C | 15 | [15] | 100% | 100% | 0.00 | 100% |
| D | 1 | [1] | 100% | 100% | 0.00 | 100% |
| H | 3 | [None] | 0% | n/a | n/a | 0% |
| I | 4 | [None] | 0% | n/a | n/a | 0% |
| J | 3 | [3] | 100% | 100% | 0.00 | 100% |

Process: 25.0 tool calls/run, 4.0 images viewed/run, plan_tools usage {'zoom': 4}; errors: 0; total cost $3.88.
