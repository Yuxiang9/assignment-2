# Experiment ledger

Scoring: official `workflow score` (macro-MCC over four families). "Seed" =
110 released runs vs `seed_labels.json`; "authored" = 15 generated runs vs
`labels.json`; "subset" = fixed diagnostic subset (see
`experiments/diagnostic_subset.json`, labels used by the harness only).
Serving: fixed judge Qwen/Qwen3-VL-30B-A3B-Instruct-FP8, vLLM 0.13.0,
temperature 0, max_tokens 500 per call. Baselines and repeats recorded per
row. Stretch target (engineering, not a course requirement): seed macro-MCC
0.60.

| id | hypothesis | parent | change | status |
| --- | --- | --- | --- | --- |
| e00 | (incumbent freeze) submitted Part-4 validator; seed 0.4582, authored 0.3552 | - | none (sha 2ae5e298...) | frozen |

## e00 — incumbent freeze (2026-09-27)

- Source: `experiments/e00/solution.py`, sha256 `2ae5e298a4ad22262a0dc48c56e15b99ef13c72f39595509b786163be5073f04`.
- Predictions copied from the designated final sweeps
  (`output/final_seed_predictions.json`, `output/authored_predictions.json`).
- Scores: seed macro 0.4582 (exec 1.0000, wd 0.4235, wc 0.1758, hr 0.2334);
  authored macro 0.3552 (exec 1.0000, wd 0.0000, wc 0.5556, hr −0.1348).
  Verified against the official scorer at freeze time; matches the
  improvement-plan table.
- Run/input manifest: `experiments/e00/run_manifest.json` (144 entries).
- Environment: `experiments/e00/environment.json`.
- Calls/run: ≤ 5 normal for a valid figure (3 family + ≤1 arbitration +
  rare truncation re-ask); 0 model calls for missing-figure runs.

## Infrastructure (2026-09-27, pre-candidate)

- **e00b**: `validator/solution.py` gained HW2_DIAG_DIR observability
  (sha in `e00/source_with_diagnostics.sha256`). Verified decision-neutral
  with a mocked judge: identical outputs with diagnostics on/off; no-op and
  no files when unset. Not a candidate; incumbent decisions unchanged.
- **Diagnostic subset**: `experiments/diagnostic_subset.json`, 39 runs from
  the improvement plan's mechanism table + 2 genuine execution failures +
  5 acceptable negatives. Support (+/-): exec 2/37, wd 13/24, wc 22/15,
  hr 13/24. Labels used only by `experiments/harness.py`.
- **Reserved validation suite**: `experiments/holdout/` — 12 fresh
  correct/faulty pairs (4 data, 4 chart, 4 readability intended defects)
  + 2 execution failures; 26 runs in released format. Every figure visually
  verified; two labels refined during verification (hourly-ticks bad also
  violates the explicit rotation request -> wrong_chart+hard_to_read;
  top-films bad also breaks the requested order -> evidence extended).
  Labels are constructed-and-verified, NOT human-reviewed course labels.
  RESERVED: not to be scored until finalist selection.

## e01 — repair destructive filtering + malformed-response handling

- Parent: e00b. Source: `experiments/e01/solution.py`,
  sha256 02b2297a... Change: (1) the deterministic colour filter is
  disconnected from validate(); (2) the arbiter may no longer emit a YES for
  a family no reviewer proposed when it supplies no evidence of its own
  ("confirmed by arbitration" fabrication removed).
- Hypothesis / expected benefit (written before running): restores valid
  colour findings the filter destroyed (4/5 of the plan's regression cases
  fail on the incumbent) and removes an invented-verdict path; on the
  subset, wrong_chart/wrong_data recall should not fall, and evidence
  quality improves.
- Plausible regression (written before running): the city-temps-style
  "X instead of tab:X" hallucination may return on authored city-temps runs
  (NOT in the subset; will show in full authored sweeps), since only the
  arbiter's prompt-level grounding rule remains against it.
- Local gates: regression suite 9/9 pass (incumbent fails 5).
- Status: awaiting subset evaluation (queued behind e00b repeatability).

## e03-prep — deterministic DPI component (not yet a candidate)

- `experiments/dpi_check.py`: extracts explicit DPI requests
  (exact vs minimum), reads PNG metadata (missing = unknown), 5% tolerance.
  Unit cases pass. Offline audit across all 125 released+authored runs:
  fires on exactly 046/060/130 (all true wrong_chart positives, evidence
  matches the human labels), silent on the 12 compliant DPI-mentioning
  runs. Zero false positives. Will be wired into the current best source as
  its own candidate after e01 is decided.

## e00b repeatability + stage attribution (2026-09-27)

- Two identical subset repeats: macro 0.2891 / 0.2675; two identical
  authored repeats: macro 0.3468 / 0.3215 (designated final sweep 0.3552 in
  band). Verdict flips: 2/39 subset (016 +/- hard_to_read; 030 +/-
  hard_to_read), 2/15 authored (city-temps ministral clean<->wrong_chart FP,
  city-temps qwen). **Repeat noise ~ +/-0.02-0.03 macro**; promotion rules
  use this floor.
- Stage attribution from diagnostics (content families, subset, both
  repeats): FN causes = never_detected 34-35, arbitrated_away 4,
  filtered_out 0; FP causes = asker_and_kept 6-9, arbiter_added 1-3.
  **Conclusion: recall is bounded by first-stage detection, not by the
  filter or arbitration.** Steps 4-6 (checklist design checks, readability
  prompt, data derivation) are where recall can move; e01 is justified as a
  correctness repair, not as a recall gain.

## e01 — subset result and decision

- Subset macro 0.2688 vs e00 repeats 0.2891/0.2675: inside the repeat band.
  Families: exec 1.0, wd 0.2906 (one new FP), wc -0.0451 (unchanged), hr
  -0.1702 (= e00 r1).
- Only two runs differ from BOTH e00 repeats; audited both against the
  artifacts: 038 (asker misreads the requested split violins as wrong data)
  and 164 (annotation-clipping claim). Neither contains colour language --
  the removed filter never touched either; both match the known
  asker-hallucination pattern seen in e00's own repeat flips.
- DECISION: PROMOTE (new incumbent). Verified correctness repair (5
  regression failures of the incumbent fixed), no systematic subset cost.
  Residual risk (city-temps tab-alias FPs returning) is not measurable on
  the subset and is carried to the full-sweep comparison of the finalist;
  noted that e00 with the filter still produced a ministral colour FP in
  repeat r2, so the filter was not reliably preventing the pattern either.

## e04 — checklist wrong_chart prompt (pre-registration)

- Parent: e01. Source sha 995353f3... Change: wrong_chart reasoning steps
  replaced with a bounded (<=12 item) REQ-line checklist -- quote |
  expected | observed | source image/code | status pass/fail/unknown --
  with an explicit image-over-code rule ("set in code but absent from the
  saved image is absent"). Rubric, parsing, token budget unchanged.
- Hypothesis (before running): wrong_chart recall rises on the subset's 22
  positives (never_detected is the dominant FN cause); the image-over-code
  rule specifically targets label-saved-off-canvas mechanisms.
- Plausible regression (before running): more truncation re-asks (watch
  diagnostics); over-literal readings creating wrong_chart FPs on the 15
  subset negatives.
- Local gates: regression suite 9/9.

## e05 — readability-specific prompt (pre-registration)

- Parent: e01 (independent of e04's wrong_chart change). Source sha
  c9599d05... Change: hard_to_read gets (1) per-element-group CHECK lines
  (title / axis labels / tick labels / legend / annotations / series) with
  ok|problem|unknown, (2) a family-specific confidence rule replacing the
  shared "explicit requirement" gate -- readability defects need a named
  element + location + visible mechanism, not an explicit task clause;
  "an element entirely absent is NOT clipped" is stated in the steps.
  Other families keep the explicit-requirement gate. Prompt rendering
  verified per family with a mocked judge.
- Hypothesis (before running): recovers intrinsic-readability FNs (29 on
  seed; 13 subset positives) that the explicit-requirement gate suppressed;
  the named-mechanism requirement should not raise clipping hallucinations
  (they already occur) and the absent-is-not-clipped rule may cut them.
- Plausible regression (before running): recall-up brings FP-up on the 24
  subset negatives; watch stage-attendance__glm/qwen (existing clipping
  false alarms) specifically.
- Local gates: regression suite 9/9; prompt render check.

## e07-prep — deterministic literal-array component (not yet a candidate)

- `experiments/data_check.py`: compares comma-run literal series (>=4
  numbers) in the instructions against literal lists in the LAST successful
  figure-writing command; same multiset re-ordered -> wrong-order evidence
  (suppressed when the task asks for sorting), few changed values ->
  wrong-values evidence; silent otherwise. 7 unit cases pass. Offline audit
  across all 125 runs: fires exactly once -- run 077, a true wrong_data
  positive -- zero false positives.
- Out of scope, by measurement: 204 (values scattered in prose, no safe
  extraction), 216 (numbers never form a comma run), 126 (formula
  constant, not a series). Will ship together with dpi_check as one
  "deterministic fact layer" candidate (plan step 4 candidate A).

## e04 — subset result and decision

- Subset: macro 0.2688 -> 0.3701 (vs e00 repeats 0.2675-0.2891; gain ~4x
  the repeat noise). wrong_chart -0.0451 -> +0.2793 (TP 5->15, FN 17->7,
  FP 4->6); wrong_data back at 0.3715 (e01's 038 FP did not recur =
  serving noise, as suspected); hard_to_read unchanged.
- Audit of the 10 new TPs: 016 (legend missing), 021 (xlabel missing),
  028 (legend), 142 (vertical-for-horizontal), 164 (x not from 0), 203
  (colorbar missing) match the human evidence nearly verbatim; 075 and 126
  not individually audited (counted, not cited); 087 is family-correct but
  cites subplot-title text the label does not corroborate;
  sensor-share__ministral is family-correct for the wrong reason (cites
  the order inversion, which our labels file under wrong_data; the true
  wrong_chart defect is the off-canvas y label). Recorded as such.
- Audit of the 2 new FPs: fine-totals__ministral claims the descending
  order is violated when it is factually correct (checklist-induced
  re-derivation error, same mechanism as the older fine-totals__glm FP);
  sensor-share__glm correctly detects the barh inversion but files order
  under wrong_chart (family boundary; the arbiter's order->wrong_data rule
  did not fire).
- DECISION: PROMOTE (gains span legend, axis-label, orientation,
  axis-limit, colorbar defect types; both FPs are order-boundary cases,
  deferred to the step-7 deterministic-mapping ablation on recorded
  findings rather than another prompt tweak).

## Step-7 ablation on e04's recorded subset findings (offline)

- Same raw findings, three family-assignment configs
  (`experiments/arbitration_ablation.py`): direct macro +0.3778; mapped
  (deterministic subtype re-file) +0.4359; model-arbitrated (shipped)
  +0.3701. The model arbiter costs wrong_chart (0.473 -> 0.279) and
  hard_to_read (-0.066 -> -0.170) by erasing/moving correct findings, and
  only slightly helps wrong_data. Conclusion per plan step 7: remove the
  arbiter's responsibility; use deterministic mapping.

## e06 — deterministic mapping replaces model arbitration (pre-registration)

- Parent: e04. Source sha f5e706ea... Change: validate() no longer calls
  the model arbiter; findings are re-filed deterministically (order
  language -> wrong_data; title/label/legend/colormap/scale presence
  language filed as data -> wrong_chart; partial clipping filed as
  data/chart -> hard_to_read, "entirely outside" stays wrong_chart) and
  deduplicated one-per-family. Saves one model call per positive run.
- Hypothesis (before running): live subset macro moves toward the ablation's
  +0.4359 and wrong_chart/hard_to_read recover the arbiter's erasures.
- Plausible regression (before running): the arbiter's genuine drops of
  hallucinated findings are gone, so FPs the askers produce now always
  land; watch the clipping-hallucination runs.
- Local gates: regression suite 9/9; mapping unit cases.

## e05 — subset result and decision

- Subset vs parent e01: hard_to_read -0.1702 -> +0.1071 (TP 1->10, FN
  12->3) but FP 5->16; macro 0.2688 -> 0.3794. Transition audit: 9 FN->TP
  including genuinely grounded occlusion/overlap/indistinct findings
  (city-temps__qwen legend-over-lines, 200 legend-over-points, 111
  indistinct bars, 046 real top-edge clip) -- and 11 new FPs, almost all
  "partially cut off at the image edge" fabrications.
- Deterministic edge-ink audit of every clipping claim in the run: only
  046's is physically real (ink reaches the claimed edge). Several scored
  TPs (030, 060, 069, 087, 177) cite fabricated clipping on runs that are
  hard_to_read for other reasons -- family-correct, evidence-wrong;
  recorded as such, not as qualitative successes.
- Offline replay of an edge-verification filter (strike clipping sentences
  whose claimed edge strip holds no ink; drop empty findings):
  hard_to_read +0.1071 -> +0.4442 (FP 16->1), replay macro +0.4636.
- DECISION: adopt e05's readability prompt ONLY together with the
  edge-verification filter (plan step 5's "confirm suspected clipping"
  realized deterministically); composed candidate follows e06.

## e09 — composed candidate (pre-registration)

- Parent: e06 (itself e04+mapping). Source sha 2066e668... Composition of
  separately measured components: e04 checklist wrong_chart (live subset
  +0.28 wc), e05 readability prompt (live: hr recall 1->10 TP), e06
  deterministic mapping (ablation +0.066 macro over model arbiter), edge
  verification of clipping claims (replay: hr +0.107 -> +0.444), and the
  DPI + literal-array fact layer (offline audits: 4 TPs, 0 FPs across all
  125 dev runs). All ported self-contained (PIL-only, stdlib) so
  solution.py stays grading-safe.
- Order in validate(): exec -> three asks -> remap+dedup -> edge-verify
  clipping -> merge deterministic facts (one error per family).
- Hypothesis (before running): live subset macro >= 0.45 (e04's wc gain +
  edge-verified hr gain should combine; families are independent).
- Plausible regression (before running): e05's non-clipping FP channels
  (occlusion/contrast claims) are not edge-checkable and may keep hr FPs;
  interaction between checklist wc and mapping refile could shift wd.
- Local gates: regression suite 9/9; in-module component verification
  (DPI 046/130 fire + 004 silent; array 077 fires + 216 silent; edge check
  strikes fabricated stage-attendance claim, keeps 046's real one, leaves
  occlusion claims alone; fact merge keeps one error per family).

## Incident: e06 first subset run crashed (2026-09-28)

- e06's surgery removed the `findings` variable but the validate() diag
  block still referenced it -> NameError on every run with findings; the
  harness's non-zero exit was masked by piping through tail (the plan's
  "check each process exit code" warning realized). ~11 min of endpoint
  time lost; no results recorded.
- Fixes: e06/e09 patched (new shas 29e3086b... / 16042f61...); regression
  suite now includes a mocked end-to-end validate() smoke (figure and
  no-figure paths); harness invocations now use pipefail.

## e06 — live subset result and decision

- Live macro 0.4324 (ablation predicted 0.4359; parent e04 0.3701; gain
  ~2-3x repeat noise). wc 0.2793 -> 0.4078; wd 0.3715 -> 0.3883; hr
  -0.1702 -> -0.0664; exec 1.0.
- Transition audit (11 runs): mapping filed the sensor-share__glm barh
  inversion under wrong_data (TP; previously a wrong_chart boundary FP);
  030 lost its spurious wrong_data and now matches truth exactly; 008
  gained its hard_to_read TP; 216 gained its wrong_data TP via order
  refiling. Cost: without the arbiter's drops, 022 (wc) and 031 (wd)
  hallucinations survive, and two existing FPs changed family without
  disappearing (196, fine-totals__ministral).
- DECISION: PROMOTE. Also one fewer model call per positive run.

## e09 — live subset result and decision

- Live macro 0.6104 (parent e06 0.4324; incumbent e00 0.2675-0.2891 on the
  same subset). exec 1.0000, wd 0.4576, wc 0.6126, hr 0.3715.
- Transition audit vs e06 (17 runs): edge verification removed every
  fabricated clipping claim (016, 047, 143, both stage-attendance false
  alarms now clean) at the cost of two lucky-family hr credits (008, 030)
  whose cited clipping was fabricated; DPI facts produced deterministic
  wrong_chart TPs on 046 and 130; the array fact produced 077's wrong_data
  TP; the readability prompt recovered genuinely grounded occlusion TPs
  (111, 200, city-temps__qwen with the exact legend-over-lines mechanism);
  one new hr FP (028: a MISSING legend mis-filed as a rendering problem
  despite the absence-is-not-clipped rule).
- DECISION: FINALIST. Proceeding to the plan's finalist-vs-incumbent
  comparison: two fresh full sweeps each (seed + authored), interleaved,
  matched serving settings; then one reserved-holdout evaluation.

## Finalist-vs-incumbent comparison (two fresh full sweeps each, interleaved)

| sweep | exec | wd | wc | hr | macro |
|---|---|---|---|---|---|
| e00 seed r1 | 1.0000 | 0.3643 | 0.0736 | 0.3177 | 0.4389 |
| e00 seed r2 | 1.0000 | 0.4006 | 0.1618 | 0.3177 | 0.4700 |
| e09 seed r1 | 1.0000 | 0.4071 | 0.4352 | 0.0779 | 0.4800 |
| e09 seed r2 | 1.0000 | 0.4411 | 0.4493 | 0.0851 | 0.4939 |
| e00 authored r1 | 1.0000 | 0.0000 | 0.5556 | -0.1348 | 0.3552 |
| e00 authored r2 | 1.0000 | 0.0000 | 0.2582 | -0.1348 | 0.2808 |
| e09 authored r1 | 1.0000 | 0.6325 | 0.4082 | 0.6742 | 0.6787 |
| e09 authored r2 | 1.0000 | 0.5292 | 0.4082 | 0.6742 | 0.6529 |

- Seed: e09's worse repeat (0.4800) beats e00's better repeat (0.4700);
  authored: e09 by +0.30-0.37. All repeats reported.
- Investigated the seed hard_to_read loss (0.3177 -> ~0.08, > 0.03 rule):
  every one of the 12 lost "TPs" (009, 026, 030, 052, 059, 146, 150, 169,
  173, 175, 191, 212) was a fabricated clipping claim on a run whose true
  defect is another mechanism (overlapping labels, invisible series,
  upside-down text, legend-over-ticks, overlapping panels); the edge check
  removes that unsound credit. e09 gains 6 grounded hr TPs (025, 046, 098,
  111, 128, 200). Genuine non-clipping recall (overlap/invisible) remains
  weak -- 33 FNs -- an honest open limitation; targeted crops (plan step
  5, second half) recorded as the natural next candidate, not pursued
  within this campaign after the six-candidate review.
- DECISION: CHAMPION = e09.

## Reserved holdout — single evaluation (2026-09-28)

- e00 macro +0.7248 (wd 0.7746, wc 0.4503, hr 0.6742); e09 macro +0.7108
  (wd 0.5774, wc 0.2660, hr 1.0000). Within repeat noise of each other:
  the development-set gains do NOT establish private-set superiority; the
  claim reported is "comparable on an unseen suite, better on both
  human-labelled development sets, with sounder (audited) evidence".
- e09 holdout detail: readability perfect (4/4 TP incl. occlusion and
  low-contrast, 0 FP); recall otherwise equal to e00 (wd 4/4, wc 4/5).
  FP channels, audited: (1) dual-filing -- one real defect credited in a
  second family (clipped-xlabel, contrast-series, cumulative-rainfall,
  scatter-styled, sem-errorbars bad variants); (2) re-derivation or
  misbinding hallucinations on clean charts (top-films top-5 membership,
  sem-errorbars sqrt confusion, log-decay scale misread,
  quarterly-revenue colour claim that concedes no colour was specified).
  Not tuned on: the suite is spent; recorded as limitations.
- CHAMPION CONFIRMED: e09 (selection rested on the pre-registered
  comparison-sweep rule; holdout is validation only).

## e10 + e11 — user-approved continuation (2026-09-28)

- **e10 dual-filing dedup**: near-duplicate cross-family errors collapse
  toward the family their combined language names (similarity gate ratio
  >= 0.45, or >= 0.35 with token-Jaccard >= 0.25, calibrated on 75 real
  cross-family pairs; legitimate dual-family cases sit <= 0.38 and
  survive). 8 unit cases incl. the hourly-ticks keep-case.
- **e11 contrast check**: colour literals from drawing-call kwargs across
  all successful commands (excluding edgecolor, legend proxies, unlabeled
  reference lines, translucent fills, masking patches, and dark-canvas
  runs) vs the rendered corner background; WCAG-style ratio < 2.5:1 fires
  hard_to_read. Iterated three times against the audit (edgecolor and
  donut-hole idioms, dark-axes Hinton case); final: fires on 8 runs, all
  hard_to_read truths (008, 026, 052, 069, 129, 141, 200, 205), 0 FPs
  across all 125 dev runs.
- Offline replay on all six existing e09 sweeps: seed macro
  0.4800/0.4931/0.4939 -> 0.5338/0.5367/0.5411 (+0.045-0.055, ~2x noise
  floor, consistent); hr 0.078 -> 0.26-0.29; authored unchanged.
- NOTE: e10 was motivated partly by reserved-holdout observations, so the
  holdout is development data for this revision; no untouched suite
  remains.
- Integrated into validator/solution.py (sha f9e9e2cb...); mocked-validate
  smoke caught one port bug (messages->run.messages) before any GPU use.
- Fresh designated sweeps with the revised shipped code follow.

## Shipped revision (e09 + e10 + e11) — final numbers (2026-09-28)

- Designated sweeps: seed macro 0.5002 (exec 1.0, wd 0.3553, wc 0.3061,
  hr 0.3395), authored 0.6210 (hr 1.0). Fresh repeat: seed 0.5093
  (hr 0.4223), authored 0.6416. Shipped band seed 0.500-0.509: the worse
  shipped sweep beats the pre-revision champion's best repeat (0.4939).
- hard_to_read recovered from the 0.08 evidence-soundness trough to
  0.34-0.42 on physically verified evidence; seed wrong_chart TP 50/71.
- Stretch target 0.60 seed: still not reached; recorded plainly.
