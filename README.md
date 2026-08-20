# plan-agent-prototype

A prototype for reading construction drawings with an AI model, plus an eval harness
that measures how consistently it gets the right answer.

The idea: a plan pasted into a chat window is downscaled to about 1,500 px and becomes
unreadable, so the model fails. Given the tools a person uses at the plan table (zoom,
text with coordinates, snapping to vector edges, measuring at scale, CAD layer toggling,
markup), the same model reads the plan.

## What is here

| file | purpose |
|---|---|
| `plan_tools.py` | the toolkit: `overview`, `zoom`, `text`, `snap`, `measure`, `layers`, `mark`, `overlay` over a vector PDF (PyMuPDF) |
| `make_testplan.py` | generates `testplan.pdf`, a synthetic 1:100 floor plan with wrong dimension labels |
| `testplan.pdf` | the synthetic plan (one A3 page) |
| `realplan.pdf` | a real bid set, 44 sheets, 190 CAD layers: "Renovation & Addition to North Macon Park Recreation Center", Macon-Bibb County, Georgia, USA, 2016, public tender documents. Not committed (39 MB); download it from the [county website](https://www.maconbibb.us/wp-content/uploads/2016/06/Attachment-C-Drawings.pdf), see Setup |
| `marks.json`, `marked.png`, `marked_crop.png` | the model's markup of the errors it found on the test plan |
| `m101_overview.png`, `m101_ducts.png`, `m101_supply_only.png` | sheet M101 as overview, zoomed to 300 dpi, and with the return-air layers switched off |
| `eval/` | the eval harness: tasks, runner (Claude Agent SDK), scorers, report; see [eval/README.md](eval/README.md) |
| `eval/runs/` | committed results of the batches run so far (reports, answers, scores, transcripts) |

## Setup

```sh
python3 -m venv .venv
.venv/bin/pip install pymupdf claude-agent-sdk pillow
curl -L -o realplan.pdf "https://www.maconbibb.us/wp-content/uploads/2016/06/Attachment-C-Drawings.pdf"
```

`plan_tools.py` needs only PyMuPDF and Pillow. The eval harness additionally drives the
locally installed Claude Code CLI through the Claude Agent SDK.

`realplan.pdf` is the public tender attachment "Attachment C - Drawings" from
Macon-Bibb County and stays out of the repository; the `curl` line above fetches it.
The drawings remain the work of their authors (county and design firm); they are used
here as a public test document.

## Using the tools by hand

```sh
.venv/bin/python plan_tools.py overview realplan.pdf 32           # sheet M101 at 150 dpi -> overview.png
.venv/bin/python plan_tools.py zoom realplan.pdf 32 1300 100 2000 700 300   # region in PDF points -> zoom.png
.venv/bin/python plan_tools.py text realplan.pdf 34               # words with coordinates on M601
.venv/bin/python plan_tools.py snap realplan.pdf 32 1500 400      # vector edges near a point
.venv/bin/python plan_tools.py measure testplan.pdf 100 289.56 466 388.35 466   # 1:100, two points -> metres
.venv/bin/python plan_tools.py layers realplan.pdf                # list CAD layers
```

Every rendered image prints its page-space bounding box, so pixel positions convert
back to page coordinates.

## Eval

```sh
.venv/bin/python -m eval run --task dimcheck takeoff --condition tools naive --n 30 --parallel 15
```

Details, scoring rules, ground truth and results in [eval/README.md](eval/README.md).
