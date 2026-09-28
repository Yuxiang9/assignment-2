# Candidate design notes (pre-registration drafts)

## e04 — checklist wrong_chart prompt (plan step 4, candidate B)

Hypothesis: the broad "check each explicit design requirement" instruction
lets the judge skim; an enumerated per-requirement checklist with a
pass/fail/unknown status per clause forces it to actually visit each
requirement, raising wrong_chart recall (48/71 seed FNs, 34-35
never-detected on the subset).

Change (wrong_chart _ask only): replace the reasoning `steps` with:
extract at most 12 explicit design requirements as numbered lines
  REQ n: "<short quote>" | expected | observed | source: image|code |
  status: pass|fail|unknown
plus: judge visible properties (presence, order, placement, clipping) from
the IMAGE; code only proves what the agent attempted -- a property set in
code but absent from the saved image is absent (targets the
sensor-share__ministral mechanism). VERDICT: YES iff any status is fail;
EVIDENCE quotes the failing requirement(s). Existing VERDICT/EVIDENCE
parsing and truncation re-ask unchanged; MAX_OUTPUT_TOKENS stays 500 (a
bounded token increase would be its own candidate per plan).

Expected regression: more text per reply -> more truncation re-asks
(measure via diagnostics); possible new FPs from over-literal readings of
open choices (rubric keeps the "do not invent requirements" rule).

## e05 — readability-specific prompt (plan step 5, first half)

Hypothesis: the shared confidence gate "Report YES only when you are
confident an EXPLICIT REQUIREMENT is violated" suppresses hard_to_read,
whose defects (overlap, contrast, occlusion) are rarely explicit
requirements; this drives much of the 29-FN seed recall hole and the
"clipped" hallucinations are the model reaching for the one legibility
word the prompt family rewards.

Change (hard_to_read _ask only): family-specific closing instruction
replacing the explicit-requirement gate: report YES only when you can name
(1) the affected element, (2) where it sits in the figure, and (3) the
visible mechanism (partly cut off at an image edge / overlapping another
element / covered by a legend or box / too low contrast / indistinguishable
from another series / squeezed). An element that is entirely absent is NOT
clipped -- absence belongs to another family. Ask for one CHECK line per
text element group (title, axis labels, tick labels, legend, annotations,
series distinguishability) with status ok|problem|unknown before the
verdict.

Expected regression: recall up may bring FPs up; the named-mechanism
requirement is the counterweight. Gate per plan: authored clean
stage-attendance charts must not be called clipped.

## e06 (later, separate) — whole image + targeted crops for readability
## e07 (later) — structured data derivation for wrong_data
