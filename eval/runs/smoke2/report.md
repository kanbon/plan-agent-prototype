# Plan-agent eval report

Batch: `/Users/simonprast/git/plan-agent-prototype/eval/runs/smoke2`

## Overview

| task | condition | runs | pass rate | score mean ± std | answer agreement | distinct answers | cost/run | time/run | turns |
|---|---|---|---|---|---|---|---|---|---|
| dimcheck | naive | 1/1 | 0% | 0.30 ± 0.00 | 100% | 1 | $1.05 | 112 s | 2.0 |

Answer agreement = share of runs whose canonical answer equals the modal answer (dimcheck: set of ground-truth items found + false-positive count; takeoff: per-type count vector A,B,C,D,H,I,J, so a different reading of 'ceiling vents' counts as a different answer).

## dimcheck / naive

| metric | value |
|---|---|
| planted error found (4.00 vs 3.485 m) | 0% |
| planted error at least flagged | 100% |
| chain-sum inconsistency found (10.575 vs 10.00) | 100% |
| living-room 5.86 vs 5.80 found | 0% |
| runs with false positives | 1/1 (mean 1.00) |
| qualitative remarks per run (not scored) | 1.00 |
| measured bedroom width, abs. error mean | 0.055 m |
| measured values reported | [3.43] |
| findings per run | [6] |
| modal answer | ['area_bad', 'area_wohnen', 'bedroom_4.00?', 'chain_sum', 'FP=1'] |

Process: 0.0 tool calls/run, 0.0 images viewed/run, plan_tools usage {}; errors: 0; total cost $1.05.
