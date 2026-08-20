# Plan-agent eval report

Batch: `/Users/simonprast/git/plan-agent-prototype/eval/runs/dimcheck30`

## Overview

| task | condition | runs | pass rate | score mean ± std | answer agreement | distinct answers | cost/run | time/run | turns |
|---|---|---|---|---|---|---|---|---|---|
| dimcheck | naive | 30/30 | 0% | 0.38 ± 0.12 | 20% | 17 | $0.36 | 120 s | 2.0 |
| dimcheck | tools | 30/30 | 97% | 1.00 ± 0.02 | 63% | 4 | $1.40 | 320 s | 12.6 |

Answer agreement = share of runs whose canonical answer equals the modal answer (dimcheck: set of ground-truth items found + false-positive count; takeoff: per-type count vector A,B,C,D,H,I,J, so a different reading of 'ceiling vents' counts as a different answer).

## dimcheck / naive

| metric | value |
|---|---|
| planted error found (4.00 vs 3.485 m) | 3% |
| planted error at least flagged | 93% |
| chain-sum inconsistency found (10.575 vs 10.00) | 57% |
| living-room 5.86 vs 5.80 found | 0% |
| misplaced bedroom door swing found | 63% |
| area labels flagged per run (of 3, not scored) | 2.40 |
| runs with false positives | 7/30 (mean 0.40) |
| qualitative remarks per run (not scored) | 0.10 |
| measured bedroom width, abs. error mean | 0.060 m |
| measured values reported | [3.425, 3.43, 3.425, 3.43, 3.425, 3.425, 3.43, 3.6, 3.43, 3.43, 3.43, 3.425, 3.425, 3.43, 3.425, 3.43, 3.43, 3.43, 3.425, 3.5, 3.43, 3.43, None, 3.425, 3.59, 3.425, 3.43, None, 3.425, 3.425] |
| findings per run | [5, 5, 5, 4, 4, 3, 3, 8, 6, 3, 3, 5, 5, 9, 4, 8, 7, 4, 5, 9, 6, 5, 11, 3, 8, 3, 2, 3, 6, 5] |
| modal answer | ['area_bad', 'area_wohnen', 'bedroom_4.00?', 'FP=0'] |

Process: 0.0 tool calls/run, 0.0 images viewed/run, plan_tools usage {}; errors: 0; total cost $10.78.

## dimcheck / tools

| metric | value |
|---|---|
| planted error found (4.00 vs 3.485 m) | 100% |
| planted error at least flagged | 100% |
| chain-sum inconsistency found (10.575 vs 10.00) | 100% |
| living-room 5.86 vs 5.80 found | 100% |
| misplaced bedroom door swing found | 67% |
| area labels flagged per run (of 3, not scored) | 3.03 |
| runs with false positives | 1/30 (mean 0.03) |
| qualitative remarks per run (not scored) | 0.07 |
| measured bedroom width, abs. error mean | 0.001 m |
| measured values reported | [3.485, 3.49, 3.485, 3.485, 3.485, 3.485, 3.485, 3.485, 3.485, 3.485, 3.485, 3.485, 3.485, 3.485, 3.49, 3.49, 3.485, 3.485, 3.485, 3.485, 3.485, 3.49, 3.485, 3.485, 3.49, 3.485, 3.485, 3.485, 3.485, 3.485] |
| findings per run | [7, 6, 6, 7, 8, 6, 7, 7, 7, 8, 7, 8, 7, 8, 6, 7, 7, 7, 6, 7, 6, 6, 7, 7, 7, 7, 6, 6, 7, 9] |
| modal answer | ['area_bad', 'area_schlafen', 'area_wohnen', 'bedroom_4.00', 'chain_sum', 'door_swing', 'living_5.86', 'FP=0'] |

Process: 9.6 tool calls/run, 2.7 images viewed/run, plan_tools usage {'overview': 30, 'text': 30, 'measure': 102, 'layers': 23, 'zoom': 53, 'mark': 2}; errors: 0; total cost $41.93.
