# Solution documentation

This file documents everything added to the course release in this fork:
what the validator does, what the numbers are, where every artifact lives,
and how to reproduce each reported result. The graded write-up is
`report.tex` / `report.pdf`; this file is the engineering companion.

## What was built

A validator (`validator/solution.py`) that, given one data-visualization
agent run (task text, full trajectory, final `figure.png`), reports which
of the four error families apply: `execution_failure`, `wrong_data`,
`wrong_chart`, `hard_to_read`. It is scored per family with MCC against
human labels; `macro_mcc` is the four-family mean.

### Architecture (pipeline order)

1. **Deterministic execution check** — a run failed exactly when it left
   no decodable, non-empty `figure.png`. No model call; reproduces the
   seed ground truth 110/110.
2. **Three focused judge calls** (fixed course model
   Qwen/Qwen3-VL-30B-A3B-Instruct-FP8, one call per content family), each
   carrying the family rubric from ASSIGNMENT.md, the task verbatim, input
   files, a trajectory digest that preserves every executed command, and
   the figure. `wrong_chart` fills an enumerated requirement checklist
   (quote | expected | observed | source image/code | pass/fail/unknown)
   with an image-over-code rule; `hard_to_read` walks element groups with
   CHECK lines and must name element, location, and visible mechanism.
   Structured `VERDICT`/`EVIDENCE` tails, robust parsing, bounded re-ask
   on truncation, reactive context compaction and image downscaling on
   overflow.
3. **Deterministic family mapping** — findings are re-filed by rule
   (order language → `wrong_data`; missing/wrong title, label, legend,
   colormap, scale → `wrong_chart`; partial clipping → `hard_to_read`)
   and deduplicated to one error per family. A model arbitration pass was
   measured here and removed: replaying identical findings showed it
   erased more true positives than it repaired.
4. **Deterministic verification and facts** — an edge-ink check keeps a
   "text cut off at <edge>" claim only if ink actually reaches that image
   edge; an explicit DPI request is compared with the PNG's own metadata;
   literal number series in the instructions are compared with literal
   lists in the last successful figure-writing command. Each component
   was audited offline to zero false positives on all 125 labelled
   development runs before inclusion.

Optional diagnostics: set `HW2_DIAG_DIR=<dir>` to write one JSON record
per model call and per run (prompt hashes, raw replies, parse status,
findings at each stage). Reads no labels, changes no decisions, off by
default.

## Results

| validator | seed macro-MCC (110 runs) | authored macro-MCC (15 runs) |
| --- | ---: | ---: |
| course baseline (`validator/baseline.py`) | 0.0268 | — |
| Part 2 version (`validator/solution_part2.py`) | 0.4475 | 0.1047 |
| **shipped champion (`validator/solution.py`)** | **0.4931** | **0.7313** |

Designated-sweep per-family numbers, repeat variability (two fresh
comparison sweeps each for champion and incumbent), the investigated
seed `hard_to_read` trade-off, and the reserved 26-run holdout evaluation
(champion 0.7108 vs incumbent 0.7248 — a tie within measured noise) are
reported in `report.pdf` §4 and `experiments/LEDGER.md`.

## Repository layout (additions to the release)

| path | contents |
| --- | --- |
| `validator/solution.py` | the shipped validator (see architecture above) |
| `validator/solution_part2.py` | frozen Part 2 validator, for reproducing the pre-iteration numbers |
| `tasks/` | 5 self-authored tasks (2 weakness classes) with inputs |
| `runs/` | 15 generated agent runs (3 fixed agents × 5 tasks) |
| `labels.json` | human-reviewed labels for the 15 runs, evidence cited |
| `output/` | all required prediction files (baseline, pre-iteration seed/authored, final seed, authored) |
| `harbor/tasks/` | each task packaged as a Harbor environment + the two required mutants |
| `report.tex` / `report.pdf` | the graded report (Parts 1–4) |
| `AI_USAGE.md` | AI-usage declaration |
| `experiments/` | improvement-campaign records: `LEDGER.md` (every candidate: hypothesis, change, scores, audit, decision), frozen per-candidate sources with SHA-256s, the arbitration ablation, subset harness, regression tests, diagnostic logs, and the reserved validation suite (`experiments/holdout/`, constructed and visually verified — not human-reviewed course labels) |
| `SOLUTION.md` | this file |

## Reproducing the numbers

Setup is the course's (`ASSIGNMENT.md`): `uv sync`, deploy the validator
model to Modal, fill `.env`. Then:

```bash
# baseline (report §1)
uv run python -m validator.runner --solution validator.baseline \
  --artifacts artifacts --out output/baseline_predictions.json
uv run python -m workflow score --labels seed_labels.json \
  --predictions output/baseline_predictions.json

# Part 2 validator (report §2) — frozen module
uv run python -m validator.runner --solution validator.solution_part2 \
  --artifacts artifacts --out /tmp/part2_seed.json
uv run python -m workflow score --labels seed_labels.json --predictions /tmp/part2_seed.json

# shipped validator, designated sweeps (report §4)
uv run python -m validator.runner --artifacts artifacts --out output/final_seed_predictions.json
uv run python -m validator.runner --artifacts runs --out output/authored_predictions.json
uv run python -m workflow score --labels seed_labels.json --predictions output/final_seed_predictions.json
uv run python -m workflow score --predictions output/authored_predictions.json

# local (no-endpoint) checks
uv run python experiments/regression_tests.py validator.solution
uv run python experiments/arbitration_ablation.py experiments/e04/diag_subset_r1 experiments/e04/subset_r1.json

# diagnostic-subset harness (labels used by the harness only)
uv run python -m experiments.harness --solution validator.solution --out /tmp/subset.json

# end-to-end structural + Harbor verification
uv run python -m workflow check-submission
```

Judged runs are nondeterministic at the margin (vLLM batching); observed
repeat noise is ±0.02–0.03 macro-MCC on these set sizes. All sweeps
reported in the ledger include their repeats.

## Known limitations (measured, documented in report §4.4)

Dual-filing of one real defect into two families; re-derivation and
misbinding hallucinations on correct charts (including the residual
"X instead of tab:X" colour claim); a genuine recall gap on non-clipping
readability mechanisms; and tiny-but-unclipped text, which evades the
deterministic Harbor verifier and both VLM validators alike.
