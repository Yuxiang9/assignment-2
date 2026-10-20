# Decision register

Every load-bearing design decision in this solution, in one place, each
entry answering: what was decided, why, what was rejected, and what
evidence backs it. Numbers are macro-MCC unless stated. Deeper detail:
`SOLUTION.md` (architecture), `experiments/LEDGER.md` (full experiment
log), `report.tex` (graded write-up).

## The one-sentence design thesis

Every decision with a mechanical answer is taken away from the judge
model and made deterministic; the fixed VLM judge is kept only for
perception and language understanding, and even there its claims are
verified against the pixels where physics allows.

---

## D1. `execution_failure` is decided by a file check, not the model

- **Decision:** a run fails execution iff it left no decodable, non-empty
  `figure.png`. Zero model calls.
- **Why:** the family is *defined* by the artifact ("failed to produce a
  valid figure"), and the baseline's model-asked version was the single
  worst behavior observed: 33 false positives whose own evidence said
  "the agent successfully completed the task" (verdict-polarity confusion
  on a negatively-framed question), plus 8 missed real failures.
- **Rejected:** asking the judge "did the agent crash?" (the baseline).
- **Evidence:** deterministic rule matches staff labels 110/110 on seed;
  family MCC −0.0022 → 1.0000, holds 1.0 on every set ever measured.

## D2. One rubric-scoped question per content family, structured verdicts

- **Decision:** three separate judge calls (`wrong_data`, `wrong_chart`,
  `hard_to_read`), each carrying the assignment's own sub-criteria for
  that family, the task verbatim, input files, a trajectory digest, and
  the figure; replies must end `VERDICT: YES/NO` + `EVIDENCE: ...`,
  parsed by regex with fallbacks, truncation triggers one bounded re-ask.
- **Why:** the baseline's single broad question per family plus a
  literal starts-with-"YES" parse yielded 3 scored positives against 135
  true ones; rubric + structured tail recovered 17/25 wd, 20/71 wc,
  13/39 hr true positives in Part 2.
- **Rejected:** free-form answers parsed by prefix (baseline); JSON mode
  (not supported reliably by the serving config).
- **Evidence:** seed 0.0268 → 0.4475 (Part 2 designated sweep).

## D3. Trajectory digest keeps code, clips chatter

- **Decision:** the judge sees every executed command in full (the
  plotting code is the evidence) while assistant prose and tool output
  are clipped per message; the baseline's reactive compaction and image
  downscaling remain as overflow fallbacks.
- **Why:** 32k context; median trajectory ~5k tokens but max ~25k; the
  code is what lets the judge check derivations the image can't show.

## D4. `wrong_chart` uses an enumerated requirement checklist

- **Decision:** the wc question demands at most 12 lines of
  `REQ n: "quote" | expected | observed | source image/code |
  pass/fail/unknown`, with the rule "a property set in code but absent
  from the saved image is absent."
- **Why:** diagnostics attributed 34–35 of ~38 content misses to
  "never detected" — the judge skimmed broad instructions. Forcing it to
  visit each clause fixed that. The image-over-code rule targets a real
  mechanism found in the data: `sensor-share__ministral` *calls*
  `ax.set_ylabel('Site')` but the label renders outside the saved image.
- **Rejected:** longer token budgets (deferred, never needed); asking
  one mega-question (measured useless).
- **Evidence:** subset wc −0.045 → +0.279 (TP 5→15); recovered legend,
  xlabel, orientation, axis-limit, colorbar defects nearly verbatim
  against staff evidence. Seed wc recall 23/71 → 50/71 final.

## D5. `hard_to_read` gets its own confidence rule + CHECK lines

- **Decision:** readability does NOT answer under the shared "explicit
  requirement" gate (legibility defects are rarely explicit task
  clauses); instead it walks element groups (title/axis labels/ticks/
  legend/annotations/series) and must name element + location + visible
  mechanism; "an element entirely absent is NOT clipped."
- **Why:** the explicit-requirement gate suppressed intrinsic
  readability defects (29 seed misses under Part 2).
- **Evidence:** alone it recovered real occlusions (city-temps legend
  over lines, 200's legend over points, 111's indistinct bars) but
  added 11 clipping fabrications → which forced D6.

## D6. Clipping claims are verified by physics (edge-ink check)

- **Decision:** a hard_to_read claim that text is "cut off at the <edge>"
  survives only if non-background ink actually touches that edge of the
  PNG (3-pixel strip test).
- **Why:** an audit of one full subset run found exactly ONE physically
  real clipping claim out of 19 — the judge fabricates "partially cut
  off" constantly, and several of the incumbent's hr "true positives"
  were fabricated claims luckily landing on truthy runs (not counted as
  success per our evidence standard).
- **Rejected:** prompting harder (measured: the model asserts clipping
  with conviction regardless).
- **Evidence:** replay on the same run: hr +0.107 → +0.444, FP 16 → 1.
  Trade-off accepted knowingly: seed hr briefly fell to 0.08 because the
  unsound lucky credit was removed, then D10 rebuilt it soundly.

## D7. The model arbitration pass was removed (deterministic mapping instead)

- **Decision:** no second "referee" model call; findings re-file by rule
  (order language → wrong_data; title/label/legend/colormap/scale
  presence → wrong_chart; partial clipping → hard_to_read; "entirely
  outside the image" stays wrong_chart) and dedupe to one error/family.
- **Why:** a three-way ablation replaying IDENTICAL recorded findings
  scored: direct +0.378, deterministically re-filed +0.436,
  model-arbitrated +0.370 — the arbiter erased more true positives than
  it repaired, and a truncated arbiter reply could silently drop
  findings for unanswered families.
- **Rejected:** keeping the arbiter with better prompts; constraining it
  to ambiguous cases only.
- **Evidence:** live subset confirm 0.370 → 0.432; also one fewer model
  call per positive run.

## D8. The deterministic colour filter was removed

- **Decision:** an earlier filter that struck "colour X instead of
  tab:X" hallucination sentences was disconnected entirely.
- **Why:** a review showed it destroyed valid findings: "the requested
  tab:blue series is red and the required tab:red series is blue" (both
  paired → struck), "the title is missing and the line colour is
  incorrect" (whole sentence struck, title defect lost), colour names
  outside its vocabulary, and genuine literal blue-vs-tab:blue code
  mismatches (matplotlib literal `blue` is #0000ff; `tab:blue` is
  #1f77b4 — they differ).
- **Cost accepted knowingly:** the tab-alias hallucination channel stays
  open (it still appears on city-temps runs); documented as the dominant
  remaining FP channel together with re-derivation errors.
- **Evidence:** 4/5 required-preservation regression cases fail against
  the old filter; subset score unchanged within noise after removal.

## D9. A zero-false-positive deterministic fact layer

- **Decision:** three model-free checks merge into the findings:
  (a) DPI: explicit "save at N dpi" requests vs the PNG's own metadata
  (exact vs minimum distinguished, 5% tolerance, missing metadata =
  unknown); (b) literal arrays: comma-run number series in the task vs
  literal lists in the LAST successful figure-writing command (same
  multiset re-ordered → wrong order unless sorting was requested; few
  changed values → wrong values); (c) contrast: colour literals from
  drawing-call kwargs vs the rendered corner background, hard_to_read
  below a 2.5:1 WCAG-style ratio, with exclusions for edgecolors,
  legend-proxy `Line2D`, unlabeled reference lines, translucent fills,
  masking patches (donut holes), and dark-restyled canvases.
- **Why:** these questions have mechanical answers; the judge got them
  wrong or missed them.
- **Evidence (offline audits over all 125 labelled dev runs):** DPI
  fires on exactly the 3 true violations (046/060/130), silent on 12
  compliant DPI-mentioning runs; arrays fire on exactly 1 (077's
  re-ordered series); contrast fires on 8, all hard_to_read truths,
  after three audit iterations. Zero false positives each.

## D10. Dual-filing dedup

- **Decision:** near-duplicate cross-family errors (one defect reported
  by two questions, e.g. "sd instead of sem" filed as both wd and wc)
  collapse toward the family their combined language names; similarity
  gate (ratio ≥0.45, or ≥0.35 with Jaccard ≥0.25) calibrated on 75 real
  evidence pairs; genuinely distinct coexisting defects sit ≤0.38 and
  survive (hourly-ticks rotation+overlap keep-case).
- **Why:** each duplicate is a guaranteed FP in one family — the one
  useful thing the removed arbiter had done.
- **Evidence:** with D9c, exact replay over three fixed seed sweeps:
  0.480/0.493/0.494 → 0.534/0.537/0.541, a consistent +0.045–0.055
  (~2× repeat noise).

## D11. Evaluation methodology (how changes were accepted)

- **Decision:** frozen incumbent (hashes, predictions, manifest);
  measured repeat-noise floor (±0.02–0.03 macro from identical repeats);
  fixed 39-run diagnostic subset; every candidate pre-registered
  (hypothesis + plausible regression before running), gated on a local
  regression suite incl. a mocked end-to-end validate() smoke, evaluated
  on the subset, audited finding-by-finding before promotion; finalist
  vs incumbent on two fresh interleaved full sweeps each; a reserved
  26-run holdout built before tuning and evaluated once.
- **Why:** earlier intuition-driven fixes produced plausible components
  that measurement later rejected (D7, D8).
- **Honesty records:** holdout verdict was a TIE (incumbent 0.7248 vs
  champion 0.7108) → no private-set superiority claimed; the holdout
  later became development data (D10 drew on its errors) → no untouched
  suite remains, stated in the report; the 0.60 seed stretch target was
  NOT reached (0.500–0.509), stated plainly.

## D12. Task design (Part 3) — two weakness classes, five traps

- **Decision:** class "derived-value aggregation" (fine-totals,
  sensor-share, weighted-latency) and class "readability stress"
  (stage-attendance, city-temps), each task carrying a designed trap:
  waived-rows filter that changes every bar AND the order; barh's
  bottom-up default vs "alphabetical from top"; request-weighted vs
  plain mean (with one service as a control where both agree); 12 long
  rotated labels on a mandated 14×6 canvas; six crossing lines with a
  legend required OUTSIDE.
- **Why:** aimed at the two judged families with the least corroborating
  signal (values unreadable from pixels; legibility = pure perception).
  They worked: Part 2 validator scored 0.105 there, and the traps fired
  (agents hit the barh inversion, inside-legend occlusion, LimitsExceeded
  loops).

## D13. Harbor verifier strategy and the two mutants

- **Decision:** verifiers use S1 artifact checks + hand-derived literal
  answer keys compared against the required `plotted_values.json` sidecar
  + one re-execution of the delivered script in a scrubbed copy of /app
  (delivered artifacts snapshotted first). NOT the full artist-tree
  instrumentation of the staff example (overbuilt for the budget).
  Rejected mutant: `fine-totals/mutants/no_filter` (drops the waived
  filter; caught by the sidecar-literals assertion, reward 0). Accepted
  mutant: `stage-attendance/mutants/illegible` (correct values, correct
  14×6 canvas, correct rotation — every checkable clause satisfied —
  but all text at 2pt; reward 1.0).
- **Why the accepted mutant matters:** it measures the deterministic/
  perceptual boundary. Measured twice against each validator: the Part 2
  VLM flags hard_to_read with a fabricated "clipped" mechanism; the
  final validator never accepts it but files it under wd/wc — tiny
  unclipped text is a residual blind spot of every grader in the stack,
  reported as such rather than claimed as a crossed boundary.
- **Why a per-task verifier can't be the course's grader:** it encodes
  one task's answer key; the private set has unseen tasks → no literals,
  no schema, no per-clause assertions to write.

## D14. Scores at each stage (seed / authored macro-MCC)

| stage | seed | authored |
| --- | ---: | ---: |
| released baseline | 0.0268 | — |
| Part 2 (two fixes) | 0.4475 | 0.1047 |
| campaign champion (e09) | 0.480–0.494 | 0.621–0.731 |
| shipped (+D9c, D10) | **0.5002 / 0.5093** | **0.6210 / 0.6416** |

Final per-family (designated seed): exec 1.000, wd 0.355, wc 0.306,
hr 0.340. Known open limitations: re-derivation/misbinding
hallucinations on correct charts (dominant FP channel), non-clipping
readability recall (25 seed misses), sub-gate dual-filings, tiny
unclipped text.
