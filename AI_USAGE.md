# AI Usage Declaration

I carefully reviewed the assignment guidelines and made sure I understood
the task completely before giving any instructions to AI tools.

I used **Claude Code** (Anthropic, Claude Fable 5 model) as an AI pair
programmer for this assignment, working in my local checkout with my own
Modal deployments. Specifically, Claude Code:

- Implemented `validator/solution.py` (deterministic execution check,
  per-family rubric prompts, structured verdict parsing, trajectory digest,
  context-overflow fallback adapted from the released baseline), based on an
  error analysis of the baseline validator's predictions on the seed runs.
- Designed the five self-authored tasks under `tasks/` (task descriptors,
  synthetic CSV inputs, and hand-checkable expected values) after surveying
  the seed tasks and my validator's likely generalization weaknesses.
- Packaged the Harbor environments under `harbor/tasks/` (verifiers in
  `tests/test_state.py`, reference solutions, instruction/schema blocks, and
  the two mutant solutions) following the released `harbor/example/`.
- Ran and monitored the experiment commands (`validator.runner`,
  `workflow generate/score/package/check-submission`, `harbor run`) and
  summarized their outputs.
- Conducted the Part 4 improvement campaign under my direction: frozen
  baselines, a diagnostic subset and repeat-noise measurement,
  pre-registered candidate implementations with regression tests, an
  arbitration ablation, deterministic verification components, and a
  reserved validation suite (the experiment ledger and frozen sources are
  under `experiments/`).
- Drafted `report.tex`, which I reviewed and edited.

I reviewed the generated code and analyses before committing them, and the
human labels in `labels.json` were assigned by reviewing each generated run
and its figure against the assignment's evidence standard.

No other AI tools were used. The validator itself calls only the
course-fixed judge model (Qwen/Qwen3-VL-30B-A3B-Instruct-FP8) through the
provided endpoint, as required.
