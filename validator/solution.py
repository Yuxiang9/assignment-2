"""The validator you write. This is the only file you need to modify.

Design, in pipeline order (each stage was measured separately against a
fixed diagnostic subset before inclusion; see report Parts 2 and 4):

1. `execution_failure` is decided deterministically from the artifact: a
   run with no decodable, non-empty `figure.png` produced no valid figure.
2. The three content families are each judged by one focused question to
   the fixed VLM, carrying that family's rubric from ASSIGNMENT.md, the
   task verbatim, the input files, a trajectory digest that keeps every
   executed command, and the figure. `wrong_chart` uses an enumerated
   requirement checklist (quote | expected | observed | source | status);
   `hard_to_read` uses per-element-group CHECK lines and a
   readability-specific confidence rule (a legibility defect needs a named
   element, location, and visible mechanism -- not an explicit task
   clause). Replies end in structured VERDICT/EVIDENCE lines, parsed
   robustly, with a bounded re-ask when a reply truncates before its
   verdict and reactive context compaction / image downscaling on
   overflow.
3. Findings are re-filed deterministically into the family ASSIGNMENT.md
   assigns (drawn order -> wrong_data; missing/wrong title, label, legend,
   colormap, scale -> wrong_chart; partial clipping -> hard_to_read) and
   deduplicated to one error per family. A model arbitration pass was
   measured here and removed: replaying identical findings showed it
   erased more true positives than it repaired.
4. Deterministic verification and facts: a hard_to_read claim that text is
   cut off at an image edge is kept only if ink actually reaches that edge
   of the PNG; an explicit DPI request is compared against the PNG's own
   metadata; literal number series in the instructions are compared with
   literal lists in the last successful figure-writing command. Each was
   audited offline (zero false positives on all labelled development runs)
   before inclusion.

Optional diagnostics: setting HW2_DIAG_DIR writes one JSON record per
model call and per run for offline analysis; it reads no labels, changes
no decisions, and is disabled by default.

Each function evaluates a single run object and returns the errors it
finds. An empty list means that no errors were found. `validator/runner.py`
defines what a run object contains, and `ASSIGNMENT.md` defines the four
error families you may report.
"""

from __future__ import annotations

import hashlib
import io
import base64
import json
import os
import re
import time
import uuid
import warnings
from concurrent.futures import ThreadPoolExecutor

from openai import BadRequestError
from PIL import Image, UnidentifiedImageError

from validator.model import complete, detokenize, tokenize
from validator.prediction import Error, ErrorFamily
from validator.runner import Run

MAX_OUTPUT_TOKENS = 500
#: Fraction of the server context budgeted for text when a request overflows.
#: The remainder absorbs the image, chat template, and tokenizer differences.
CONTEXT_FRACTION = 0.5
OMISSION = "\n[... omitted to fit model context ...]\n"
COMPACTION_NOTE = "\nSome evidence may be omitted. Do not treat omissions as agent errors.\n"
#: Shrink the figure's longest side by this factor per retry once text
#: compaction alone still overflows; stop at the readability floor below.
IMAGE_DOWNSCALE_FACTOR = 0.7
MIN_IMAGE_LONG_SIDE = 64
#: Per-message caps for the trajectory digest. Commands are kept whole: the
#: code that drew the figure is the primary trajectory evidence.
PROSE_CAP = 500
TOOL_OUTPUT_CAP = 700
#: Cap on each input file excerpt shown proactively (head and tail kept).
INPUT_FILE_CAP = 6000


# --------------------------------------------------------------------------
# Optional local diagnostics
# --------------------------------------------------------------------------
# When the HW2_DIAG_DIR environment variable names a directory, each model
# call and each validate() writes one JSON record there for offline
# analysis. Disabled by default; reads no labels; never changes a decision;
# never raises. One file per record, so concurrent family calls cannot
# overwrite one another. Never logs credentials.


def _diag(run_id: str, stage: str, payload: dict) -> None:
    directory = os.environ.get("HW2_DIAG_DIR")
    if not directory:
        return
    try:
        os.makedirs(directory, exist_ok=True)
        name = f"{run_id}__{stage}__{uuid.uuid4().hex[:8]}.json"
        path = os.path.join(directory, name.replace(os.sep, "_"))
        with open(path, "w") as handle:
            json.dump(payload, handle, indent=1, default=str)
    except Exception:  # noqa: BLE001 - observability must never break judging
        pass


def _prompt_digest(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()[:16]


def _image_info(image: bytes | None) -> dict:
    if image is None:
        return {"present": False}
    info: dict = {"present": True, "bytes": len(image)}
    try:
        with Image.open(io.BytesIO(image)) as opened:
            info["size"] = list(opened.size)
    except Exception:  # noqa: BLE001
        info["size"] = None
    return info


# --------------------------------------------------------------------------
# Deterministic execution check
# --------------------------------------------------------------------------

def _decodable_figure(run: Run) -> bool:
    """True when the run left a figure an image reader can actually open."""
    if run.figure is None:
        return False
    try:
        data = run.figure.read_bytes()
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
        return width > 0 and height > 0
    except (UnidentifiedImageError, OSError, ValueError):
        return False


def _final_step_note(run: Run) -> str:
    """A short citation of how the run ended, for execution-failure evidence."""
    for message in reversed(run.messages):
        role = message.get("role")
        content = str(message.get("content") or "").strip()
        if role in ("exit", "tool", "assistant") and content:
            return f"final {role} message: {content[:300]}"
    return "the trajectory records no final message"


def judge_execution(run: Run) -> list[Error]:
    """Whether the run produced a figure to judge at all."""
    if _decodable_figure(run):
        return []
    if run.figure is None:
        reason = "the run directory contains no figure.png"
    else:
        reason = "figure.png exists but is not a decodable, non-empty image"
    return [Error(
        family=ErrorFamily.EXECUTION_FAILURE,
        evidence=f"No valid figure was produced: {reason}; {_final_step_note(run)}",
    )]


# --------------------------------------------------------------------------
# Evidence assembly
# --------------------------------------------------------------------------

def _clip(text: str, cap: int) -> str:
    """Keep the head and tail of over-long text; both ends carry evidence."""
    if len(text) <= cap:
        return text
    head = cap * 2 // 3
    tail = cap - head
    return text[:head] + OMISSION + text[-tail:]


def _trajectory_digest(run: Run) -> str:
    """The trajectory with commands kept whole and everything else truncated.

    The executed commands contain the code that produced the figure, which is
    the evidence the judge needs to check data handling; assistant prose and
    tool output mostly repeat it, so they are clipped per message.
    """
    lines: list[str] = []
    for message in run.messages:
        role = message.get("role")
        if role == "system":
            continue
        if role == "user":
            # The user turn restates the task instructions shown separately.
            continue
        if role == "assistant":
            content = str(message.get("content") or "").strip()
            if content:
                lines.append(f"[assistant] {_clip(content, PROSE_CAP)}")
            for call in message.get("tool_calls") or []:
                try:
                    arguments = json.loads(call["function"]["arguments"])
                    command = arguments.get("command", call["function"]["arguments"])
                except (KeyError, TypeError, ValueError):
                    command = str(call)
                lines.append(f"[command] {command}")
        elif role == "tool":
            raw = str(message.get("content") or "")
            try:
                payload = json.loads(raw)
                text = (f"returncode={payload.get('returncode')} "
                        f"output={payload.get('output', '')}")
            except (TypeError, ValueError):
                text = raw
            lines.append(f"[result] {_clip(text.strip(), TOOL_OUTPUT_CAP)}")
        elif role == "exit":
            content = str(message.get("content") or "").strip()
            lines.append(f"[run ended] {_clip(content, PROSE_CAP)}")
    return "\n".join(lines)


def _inputs_text(run: Run) -> str:
    parts = []
    for name, path in run.inputs.items():
        body = path.read_text(errors="replace")
        parts.append(f"--- {name} ---\n{_clip(body, INPUT_FILE_CAP)}")
    return "\n".join(parts)


# --------------------------------------------------------------------------
# Context-overflow fallback (adapted from validator/baseline.py)
# --------------------------------------------------------------------------

def _excerpt(text: str, tokens: list[int], limit: int) -> str:
    if len(tokens) <= limit:
        return text
    head = limit // 2
    tail = limit - head
    return (
        (detokenize(tokens[:head]) if head else "")
        + OMISSION
        + (detokenize(tokens[-tail:]) if tail else "")
    )


def _compact(trajectory: str, inputs: str, fixed_prompt: str) -> tuple[str, str]:
    trajectory_info = tokenize(trajectory)
    context = trajectory_info.get("max_model_len")
    if type(context) is not int or context <= 0:
        raise RuntimeError("Validator server did not report a valid max_model_len")
    trajectory_tokens = trajectory_info["tokens"]
    input_tokens = tokenize(inputs)["tokens"]
    fixed_tokens = tokenize(fixed_prompt + COMPACTION_NOTE + OMISSION * 2)["tokens"]
    budget = int(context * CONTEXT_FRACTION) - len(fixed_tokens) - MAX_OUTPUT_TOKENS
    if budget < 0:
        raise RuntimeError("Task instructions exceed the validator's context budget")
    total = len(trajectory_tokens) + len(input_tokens)
    trajectory_budget = budget * len(trajectory_tokens) // max(total, 1)
    return (
        _excerpt(trajectory, trajectory_tokens, trajectory_budget),
        _excerpt(inputs, input_tokens, budget - trajectory_budget),
    )


def _downscale(data: bytes) -> bytes | None:
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            width, height = image.size
            mode = image.mode
    except (UnidentifiedImageError, OSError, ValueError):
        return None
    longest = max(width, height)
    if longest <= MIN_IMAGE_LONG_SIDE:
        return None
    scale = max(MIN_IMAGE_LONG_SIDE / longest, IMAGE_DOWNSCALE_FACTOR)
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    if new_size == (width, height):
        return None
    with Image.open(io.BytesIO(data)) as image:
        if mode not in ("RGB", "RGBA", "L"):
            image = image.convert("RGB")
        resized = image.resize(new_size, Image.LANCZOS)
    buffer = io.BytesIO()
    resized.save(buffer, format="PNG")
    return buffer.getvalue()


def _context_overflow(error: BadRequestError) -> bool:
    message = str(error).lower()
    return any(phrase in message for phrase in (
        "context_length_exceeded",
        "maximum context length",
        "maximum model length",
        "maximum input length",
    ))


# --------------------------------------------------------------------------
# Family rubrics and the shared question machinery
# --------------------------------------------------------------------------

_WRONG_DATA_RUBRIC = """\
You must decide ONE question: is the data drawn in the figure NOT the data the
task instructions asked for? This family is called `wrong_data` and covers only:
- Wrong values: plotted numbers, positions, or derived quantities differ from
  the requested data or formula (wrong aggregation, scaling, normalisation, a
  function sampled over the wrong range or grid, a bubble size or colour value
  or error bar that should encode the data but does not).
- Missing data: a requested series, category, group, panel's data, or data
  point is not drawn, or a whole dimension of the data is dropped.
- Wrong selection: the wrong subset, column, or filter was used, or series
  that were not requested are mixed in with the requested ones.
- Wrong order: points, bars, categories, or sequences appear in an order
  different from the one requested (unsorted when sorting was asked for,
  reversed or shuffled, panels showing data they were not assigned). When the
  task specifies an order, read the ACTUAL drawn order off the figure element
  by element and compare it with the requested one, including its direction:
  left-to-right for vertical bars, and TOP-TO-BOTTOM for horizontal bars
  (matplotlib's barh draws the first item at the BOTTOM unless inverted, a
  common mistake).

Do NOT report here: chart type, axis labels or titles, styling, legends, or
readability problems. Those belong to other families. Judge only whether the
drawn data matches the requested data. Derive the expected data from the task
and the input files, and use the agent's plotting code to resolve anything the
image alone leaves ambiguous. Being correct but drawn with an unrequested
style is NOT wrong_data. Colour names cannot be verified beyond their hue:
matplotlib's default palette IS the "tab:" palette, so a line drawn in
standard blue satisfies a request for "tab:blue"; never report a colour error
of the form "the colour is X but should be tab:X"."""

_WRONG_CHART_RUBRIC = """\
You must decide ONE question: does the figure violate the chart DESIGN that the
task instructions explicitly requested? This family is called `wrong_chart` and
counts a violation ONLY when the instruction actually asked for the thing:
- Chart type and projection: wrong chart type, grouped vs stacked bars,
  vertical vs horizontal, 3D vs 2D, polar projection, contour or surface,
  twin axes, zoomed insets and their connectors.
- Layout: number or arrangement of subplots, figure size or DPI, shared axes.
- Axes: missing or wrong x/y/z axis label; wrong exact title or label text;
  wrong axis limits (not starting from zero when asked, wrong range, limits
  that cut off requested data); wrong axis scale (linear where log was asked);
  ticks or tick labels shown when asked hidden; wrong tick labels or rotation;
  spines visible when asked hidden; a requested grid missing.
- Legend, colour bar, annotations: a requested legend or colour bar missing or
  not matching the data; a requested annotation, marked point, function label,
  bar value label, or formula missing or in the wrong place; the wrong region
  shaded.
- Style: a wrong or forbidden colormap; wrong line style; wrong marker shape;
  wrong colour for a named series (only when the drawn HUE clearly differs
  from the requested one -- matplotlib's default palette IS the "tab:"
  palette, so standard blue satisfies "tab:blue"; never report "X instead of
  tab:X"); areas not filled when asked; whiskers, medians, connectors, or
  boxes missing; polygons not closed; requested line offsets not applied.
- A required text element (title, axis label) that lies ENTIRELY outside the
  saved image counts as missing, and belongs here.

Do NOT report design choices the instructions left open, and do NOT report
wrong plotted values (that is a different family) or mere readability problems
such as overlapping or clipped-in-half text. Check each explicit design
requirement in the instructions one by one against the figure."""

_HARD_TO_READ_RUBRIC = """\
You must decide ONE question: is the figure, as rendered, difficult or
impossible for a person to read? This family is called `hard_to_read` and
covers only rendering problems visible in the image:
- Clipped text: a title, axis label, tick label, or annotation partly cut off
  by the image edge (text cut in half counts here; text entirely absent does
  not).
- Overlapping text: tick labels, annotations, titles, or labels overlapping
  one another, or markers drawn on top of the text that labels them.
- Elements covering content: a legend, annotation, or text box hiding data,
  labels, or other text. A legend over empty space is fine.
- Low contrast or invisible content: text or value labels with contrast below
  roughly 2.5:1 against their background; a series drawn in the background
  colour, with zero width, or otherwise invisible.
- Indistinguishable data: two series or groups that must be told apart drawn
  with the same or nearly the same colour, line style, and marker; a colormap
  that merges values that should look different.
- Squeezed layout: data, boxes, or panels crushed into an unreadable sliver by
  axis limits or by axes overlapping each other.

Do NOT report whether the data or the chart design is correct; judge only
whether a reader can read what was drawn. Minor imperfections that leave every
element still readable are NOT errors. Inspect the attached image itself,
element by element: title, axis labels, tick labels, legend, data marks."""

_RUBRICS: dict[ErrorFamily, tuple[str, str]] = {
    ErrorFamily.WRONG_DATA: (
        _WRONG_DATA_RUBRIC,
        "List the data the task requests (values, series, ordering, filters); "
        "compare each against what the figure shows and what the plotting code "
        "computes.",
    ),
    ErrorFamily.WRONG_CHART: (
        _WRONG_CHART_RUBRIC,
        "Extract every explicit design requirement stated in the "
        "instructions -- chart type/projection, subplot arrangement, axis "
        "scales and limits, exact title and label texts, tick labels and "
        "their rotation, legend or colour bar, annotations, markers, line "
        "styles, explicit colours -- as a checklist of at most 12 items "
        "(the most load-bearing ones if there are more). Output one line "
        "per item, exactly:\n"
        "REQ <n>: \"<short quote from the instructions>\" | expected: "
        "<property> | observed: <what the saved image shows> | source: "
        "image or code | status: pass, fail, or unknown\n"
        "Judge visible properties (presence, placement, order, text) from "
        "the IMAGE; use the code only for what the image cannot show -- a "
        "property set in code but absent from the saved image is absent. "
        "Do not invent requirements the instructions leave open. Answer "
        "VERDICT: YES if any item's status is fail, and quote the failing "
        "requirement(s) in the EVIDENCE line.",
    ),
    ErrorFamily.HARD_TO_READ: (
        _HARD_TO_READ_RUBRIC,
        "Go through the figure's element groups one by one -- title, axis "
        "labels, tick labels, legend, annotations, and the data series -- "
        "and output one line per group, exactly:\n"
        "CHECK <group>: <status ok, problem, or unknown> -- <one clause on "
        "what you see>\n"
        "A problem must name the affected element, where it sits in the "
        "figure, and the visible mechanism: partly cut off at an image "
        "edge, overlapping another element, covered by a legend or box, "
        "too low contrast against its background, indistinguishable from "
        "another series, or squeezed into a sliver. An element that is "
        "entirely absent is NOT clipped and does not belong here. Answer "
        "VERDICT: YES only if some CHECK line is a problem, and restate "
        "that element, location, and mechanism in the EVIDENCE line.",
    ),
}

_VERDICT_PATTERN = re.compile(
    r"VERDICT\s*\**\s*[:\-]?\s*\**\s*(YES|NO)", re.IGNORECASE)
_EVIDENCE_PATTERN = re.compile(
    r"EVIDENCE\s*\**\s*[:\-]?\s*\**\s*(.+)", re.IGNORECASE | re.DOTALL)


def _parse_verdict(answer: str) -> tuple[bool, str]:
    """The model's decision and its cited evidence, robust to formatting."""
    verdicts = _VERDICT_PATTERN.findall(answer)
    if verdicts:
        positive = verdicts[-1].upper() == "YES"
    else:
        # Fallback for replies that ignore the format: a leading yes/no.
        positive = bool(re.match(r"\s*[*#>\s]*yes\b", answer, re.IGNORECASE))
    evidence_match = _EVIDENCE_PATTERN.search(answer)
    evidence = (evidence_match.group(1) if evidence_match else answer).strip()
    evidence = re.sub(r"\s+", " ", evidence)[:600]
    return positive, evidence or answer.strip()[:600] or "unspecified"


def _figure_note(image: bytes | None) -> str:
    if image is None:
        return "No figure image is attached."
    try:
        with Image.open(io.BytesIO(image)) as opened:
            width, height = opened.size
        return (f"The attached image is the final figure the agent saved "
                f"({width}x{height} pixels).")
    except (UnidentifiedImageError, OSError, ValueError):
        return "The attached image is the final figure the agent saved."


_EXPLICIT_RULE = (
    "Report YES only when you are confident an explicit requirement is "
    "violated;\nwhen the evidence is ambiguous or the task left the choice "
    "open, answer NO.")
_READABILITY_RULE = (
    "Report YES only when you can name the affected element, its location, "
    "and a\nvisible mechanism; readability does not require the task to "
    "have asked for\nit explicitly. When you cannot point at the element "
    "and mechanism, answer NO.")


def _ask(run: Run, family: ErrorFamily) -> list[Error]:
    rubric, steps = _RUBRICS[family]
    confidence_rule = (_READABILITY_RULE
                      if family is ErrorFamily.HARD_TO_READ
                      else _EXPLICIT_RULE)
    trajectory = _trajectory_digest(run)
    inputs = _inputs_text(run)
    image_bytes = run.figure.read_bytes() if run.figure else None

    def make_prompt(shown_trajectory: str, shown_inputs: str) -> str:
        return f"""You are auditing one run of a data-visualization agent.

{rubric}

TASK INSTRUCTIONS (the specification to check against):
<<<
{run.instructions}
>>>

INPUT FILES available to the agent:
<<<
{shown_inputs or '(none; all data is in the instructions)'}
>>>

AGENT TRAJECTORY (commands the agent ran and their results, may be truncated):
<<<
{shown_trajectory}
>>>

{_figure_note(image_bytes)}

Work through this before answering: {steps}
{confidence_rule}

End your reply with exactly two lines:
VERDICT: YES or NO
EVIDENCE: one or two sentences naming the specific violation, or "none"."""

    def ask(prompt: str, image: bytes | None) -> dict:
        content: list[dict] = [{"type": "text", "text": prompt}]
        if image is not None:
            encoded = base64.b64encode(image).decode()
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{encoded}"},
            })
        return complete([{"role": "user", "content": content}],
                        max_tokens=MAX_OUTPUT_TOKENS)

    started = time.time()
    record = {"run_id": run.run_id, "family": family.value,
              "compacted": False, "downscale_retries": 0,
              "truncation_reask": False}
    sent_prompt = make_prompt(trajectory, inputs)
    sent_image = image_bytes
    try:
        response = ask(sent_prompt, sent_image)
    except BadRequestError as error:
        if not _context_overflow(error):
            raise
        warnings.warn(
            f"Run {run.run_id} ({family.value}): model context exceeded; "
            f"retrying with text capped at {CONTEXT_FRACTION:.0%} of server context.",
            stacklevel=2,
        )
        record["compacted"] = True
        shown_trajectory, shown_inputs = _compact(trajectory, inputs, make_prompt("", ""))
        sent_prompt = make_prompt(shown_trajectory, shown_inputs) + COMPACTION_NOTE
        while True:
            try:
                response = ask(sent_prompt, sent_image)
                break
            except BadRequestError as retry_error:
                if not _context_overflow(retry_error):
                    raise
                smaller = _downscale(sent_image) if sent_image is not None else None
                if smaller is None:
                    raise
                record["downscale_retries"] += 1
                sent_image = smaller
    answer = response["choices"][0]["message"]["content"] or ""
    if not _VERDICT_PATTERN.search(answer) and \
            response["choices"][0].get("finish_reason") == "length":
        # The reasoning ran past the token budget before reaching the verdict.
        # Re-ask the request that succeeded for the conclusion alone rather
        # than mis-reading the missing verdict as NO.
        record["truncation_reask"] = True
        followup = ask(
            sent_prompt
            + "\nReply with ONLY the two final lines (VERDICT and EVIDENCE), "
              "no other text.",
            sent_image,
        )
        answer = followup["choices"][0]["message"]["content"] or answer
    positive, evidence = _parse_verdict(answer)
    record.update(
        prompt_sha=_prompt_digest(sent_prompt), prompt_chars=len(sent_prompt),
        image=_image_info(sent_image),
        finish_reason=response["choices"][0].get("finish_reason"),
        usage=response.get("usage"), raw_answer=answer,
        verdict_parsed=bool(_VERDICT_PATTERN.search(answer)),
        positive=positive, evidence=evidence if positive else None,
        elapsed_s=round(time.time() - started, 2),
    )
    _diag(run.run_id, f"ask_{family.value}", record)
    if not positive:
        return []
    return [Error(family=family, evidence=evidence)]


# --------------------------------------------------------------------------
# Cross-family arbitration
# --------------------------------------------------------------------------
# The three family questions are answered independently, so a real defect can
# be filed under the wrong family (a title-text violation reported as
# wrong_data) and an ungrounded claim can slip through. When any question
# answered YES, one arbitration call re-files each finding into the family
# the definitions assign and drops findings that are not grounded.

_JUDGED_FAMILIES = (ErrorFamily.WRONG_DATA, ErrorFamily.WRONG_CHART,
                    ErrorFamily.HARD_TO_READ)

_ARBITRATION_PROMPT = """You are the final arbiter for one audited run of a
data-visualization agent. Independent reviewers proposed the findings below.
Your job is to (1) re-file each finding into the correct family and (2) drop
findings that are not grounded.

Family definitions:
- wrong_data: what is DRAWN is not the requested data -- wrong values or
  derived quantities, missing or extra series/points, wrong subset or
  columns, or elements in a different ORDER than requested.
- wrong_chart: the data is right but an explicitly requested DESIGN element
  is not followed -- chart type, layout/subplots, axis labels/title text,
  axis limits or scale, tick labels, legend or colour bar presence and
  placement, annotations, or style (colormap, line style, marker, colour).
- hard_to_read: the figure as rendered is hard for a person to read --
  clipped or overlapping text, a legend or box covering data, invisible or
  low-contrast elements, indistinguishable series, squeezed layout.

Rules:
- File each underlying defect in exactly ONE family, the one its definition
  names; two genuinely different defects may support two families. For
  example, a wrong or missing TITLE, axis label, tick label, legend, or
  colormap is wrong_chart, never wrong_data, even if a reviewer proposed it
  as wrong_data; report it under wrong_chart instead.
- Drop a finding that is self-contradictory or not grounded in the figure or
  instructions. In particular, drop colour complaints of the form "the
  colour is X but should be tab:X": matplotlib's default palette IS the
  "tab:" palette, so such a claim describes no visible difference.
- Only discard when the finding is clearly ungrounded; when in doubt, keep
  it, re-filed into the right family.
- Do not invent new defects that no reviewer proposed.

TASK INSTRUCTIONS:
<<<
{instructions}
>>>

PROPOSED FINDINGS:
{findings}
{context}
The attached image is the figure under review.

Reply with exactly these six lines:
WRONG_DATA: YES or NO
WRONG_DATA_EVIDENCE: one sentence, or "none"
WRONG_CHART: YES or NO
WRONG_CHART_EVIDENCE: one sentence, or "none"
HARD_TO_READ: YES or NO
HARD_TO_READ_EVIDENCE: one sentence, or "none"
"""


#: Colour words the filter can treat as concrete. Deliberately broad: a
#: mismatch claim naming two DIFFERENT tokens from this set (or two hex
#: codes) is checkable and must survive the filter.
_COLOR_WORD = (
    r"blue|orange|green|red|purple|brown|pink|gr[ae]y|olive|cyan|black|"
    r"white|yellow|magenta|teal|navy|maroon|lime|aqua|silver|gold|indigo|"
    r"violet|turquoise|salmon|coral|khaki|crimson|plum|orchid|beige|tan|"
    r"chocolate|ivory|azure|lavender"
)
_HEX_COLOR = r"#[0-9a-fA-F]{3,8}\b"


def _drop_tab_alias_claims(findings: list[Error]) -> list[Error]:
    """Deterministically remove unverifiable colour pseudo-defects.

    matplotlib's default cycle draws the Tableau ("tab:") colours, so a
    claim that a series is "X instead of tab:X" for the same colour word X
    describes no difference a figure can show; the judge model nevertheless
    produces it with conviction, so the rule lives here rather than in a
    prompt. Struck, sentence by sentence, from wrong_data and wrong_chart
    evidence only:

    * a clause contrasting tab:X with the SAME bare word X ("blue instead
      of tab:blue"). The match is scoped to one clause so that "the
      requested tab:blue series is red, while the other series is blue"
      -- a genuine, checkable defect -- survives;
    * a colour complaint naming fewer than two concrete colours ("uses
      incorrect line colors"), where concrete means a known colour word or
      a hex code; colormap complaints are exempt;
    * a colour "complaint" whose annotations affirm correctness ("Aluna is
      blue (correct), Brinport is orange (correct), ...").

    hard_to_read findings pass through untouched: their colour language is
    about visibility and contrast, which is judged perceptually. A finding
    whose evidence loses every sentence is dropped entirely.
    """
    kept: list[Error] = []
    for error in findings:
        if error.family == ErrorFamily.HARD_TO_READ:
            kept.append(error)
            continue
        sentences = re.split(r"(?<=[.;])\s+", error.evidence)

        def alias(sentence: str) -> bool:
            """True when the sentence's colour talk is all X-vs-tab:X pairs.

            A colour word is "paired" when both its bare form and its tab:
            form appear in the sentence ("orange ... tab:orange"), in any
            phrasing or order. The sentence is an alias pseudo-claim when at
            least one pair exists and NO unpaired concrete colour remains:
            "blue instead of tab:blue, orange instead of tab:orange" names
            nothing but pairs and is struck, while "the requested tab:blue
            series is red, while the other series is blue" names the
            unpaired red -- a checkable defect -- and survives.
            """
            tabbed = {m.group(1).lower() for m in
                      re.finditer(r"tab:(\w+)", sentence, re.IGNORECASE)}
            bare = {m.group(0).lower() for m in
                    re.finditer(rf"(?<!tab:)\b(?:{_COLOR_WORD})\b",
                                sentence, re.IGNORECASE)}
            hexes = re.findall(_HEX_COLOR, sentence)
            paired = tabbed & bare
            unpaired = (bare - tabbed) | {h.lower() for h in hexes}
            return bool(paired) and not unpaired

        def vague_color_complaint(sentence: str) -> bool:
            if re.search(r"colou?r\s*map|cmap", sentence, re.IGNORECASE):
                return False
            if not re.search(r"colou?r", sentence, re.IGNORECASE):
                return False
            # "incorrect" must not count toward the affirmations below.
            affirmations = len(re.findall(r"(?<!in)correct", sentence.lower()))
            negated = bool(re.search(
                r"incorrect|wrong|should|instead|mismatch|violat|issue|"
                r"not match|rather than|requir", sentence, re.IGNORECASE))
            if not negated:
                # A colour sentence that only affirms correctness ("Brinport
                # is orange, which is correct") is not evidence of a defect.
                return affirmations >= 1
            concrete = {m.group(0).lower().removeprefix("tab:")
                        for m in re.finditer(
                            rf"(?:tab:)?\b(?:{_COLOR_WORD})\b|{_HEX_COLOR}",
                            sentence, re.IGNORECASE)}
            if len(concrete) < 2:
                return True
            # A complaint that annotates the colours it lists as correct
            # affirms the opposite of its own verdict.
            return affirmations >= max(2, len(concrete))

        remaining = [s for s in sentences
                     if not alias(s) and not vague_color_complaint(s)]
        if not remaining:
            continue
        if len(remaining) != len(sentences):
            error = Error(family=error.family,
                          evidence=" ".join(remaining).strip()[:600])
        kept.append(error)
    return kept


def _arbitrate(run: Run, findings: list[Error]) -> list[Error]:
    listed = "\n".join(
        f"- proposed family {error.family.value}: {error.evidence}"
        for error in findings
    )
    trajectory = _trajectory_digest(run)
    inputs = _inputs_text(run)

    def make_prompt(shown_trajectory: str, shown_inputs: str) -> str:
        context = ""
        if shown_trajectory or shown_inputs:
            context = (
                "\nAGENT TRAJECTORY (commands the agent ran, may be "
                "truncated):\n<<<\n" + shown_trajectory + "\n>>>\n\n"
                "INPUT FILES:\n<<<\n"
                + (shown_inputs or "(none; all data is in the instructions)")
                + "\n>>>\n"
            )
        return _ARBITRATION_PROMPT.format(
            instructions=run.instructions, findings=listed, context=context)

    def ask(prompt: str, image: bytes | None) -> dict:
        content: list[dict] = [{"type": "text", "text": prompt}]
        if image is not None:
            encoded = base64.b64encode(image).decode()
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{encoded}"},
            })
        return complete([{"role": "user", "content": content}],
                        max_tokens=MAX_OUTPUT_TOKENS)

    started = time.time()
    record = {"run_id": run.run_id,
              "findings_in": [[e.family.value, e.evidence] for e in findings],
              "context_shed": False, "downscale_retries": 0,
              "truncation_reask": False}
    image_bytes = run.figure.read_bytes() if run.figure else None
    sent_prompt = make_prompt(trajectory, inputs)
    try:
        response = ask(sent_prompt, image_bytes)
    except BadRequestError as error:
        if not _context_overflow(error):
            raise
        # Shed the auxiliary context first, then shrink the image; the
        # findings and instructions always stay.
        record["context_shed"] = True
        sent_prompt = make_prompt("", "")
        while True:
            try:
                response = ask(sent_prompt, image_bytes)
                break
            except BadRequestError as retry_error:
                if not _context_overflow(retry_error):
                    raise
                smaller = _downscale(image_bytes) if image_bytes else None
                if smaller is None:
                    raise
                record["downscale_retries"] += 1
                image_bytes = smaller
    answer = response["choices"][0]["message"]["content"] or ""

    def verdicts(text: str) -> dict[ErrorFamily, str | None]:
        found: dict[ErrorFamily, str | None] = {}
        for family in _JUDGED_FAMILIES:
            name = family.value.upper()
            match = re.search(
                rf"{name}\s*\**\s*:\s*\**\s*(YES|NO)", text, re.IGNORECASE)
            found[family] = match.group(1).upper() if match else None
        return found

    parsed = verdicts(answer)
    if (None in parsed.values()
            and response["choices"][0].get("finish_reason") == "length"):
        # The reply truncated mid-verdict; a partial parse must not silently
        # drop the unanswered families, so ask for the six lines alone.
        record["truncation_reask"] = True
        followup = ask(
            sent_prompt + "\nReply with ONLY the six lines requested above, "
                          "no other text.",
            image_bytes,
        )
        retry_answer = followup["choices"][0]["message"]["content"] or ""
        if None not in verdicts(retry_answer).values():
            answer, parsed = retry_answer, verdicts(retry_answer)

    arbitrated: list[Error] = []
    for family in _JUDGED_FAMILIES:
        if parsed[family] is None:
            # No verdict for this family: preserve its original findings
            # rather than losing them to a malformed or truncated reply.
            arbitrated.extend(e for e in findings if e.family == family)
            continue
        if parsed[family] != "YES":
            continue
        name = family.value.upper()
        evidence_match = re.search(
            rf"{name}_EVIDENCE\s*\**\s*:\s*\**\s*(.+)", answer, re.IGNORECASE)
        evidence = (evidence_match.group(1).strip().splitlines()[0]
                    if evidence_match else "")
        if not evidence or evidence.lower() == "none":
            # Fall back to the strongest proposed evidence for this family.
            # A YES for a family that no reviewer proposed, with no evidence
            # of its own, would be an invented defect: drop it rather than
            # fabricate grounds for it.
            proposed = [e.evidence for e in findings if e.family == family]
            if not proposed:
                continue
            evidence = proposed[0]
        arbitrated.append(Error(family=family, evidence=evidence[:600]))
    record.update(
        prompt_sha=_prompt_digest(sent_prompt),
        image=_image_info(image_bytes),
        finish_reason=response["choices"][0].get("finish_reason"),
        usage=response.get("usage"), raw_answer=answer,
        parsed_verdicts={f.value: v for f, v in parsed.items()},
        findings_out=[[e.family.value, e.evidence] for e in arbitrated],
        elapsed_s=round(time.time() - started, 2),
    )
    _diag(run.run_id, "arbitrate", record)
    return arbitrated


# --------------------------------------------------------------------------
# The four family judgments
# --------------------------------------------------------------------------

def judge_data_and_chart(run: Run) -> list[Error]:
    """Whether the figure plots the requested data, built the requested way."""
    return _ask(run, ErrorFamily.WRONG_DATA) + _ask(run, ErrorFamily.WRONG_CHART)


def judge_readability(run: Run) -> list[Error]:
    """Whether the figure can be read."""
    return _ask(run, ErrorFamily.HARD_TO_READ)


_ORDER_LANGUAGE = re.compile(
    r"\border(?:ed|ing)?\b|\bsorted\b|\bsequence\b|\breversed\b|"
    r"\balphabetical|\bdescending\b|\bascending\b", re.IGNORECASE)
_CHART_PRESENCE_LANGUAGE = re.compile(
    r"\btitle\b|\baxis label|\bx-?label|\by-?label|\blegend\b|"
    r"\bcolou?r ?bar\b|\bcolou?rmap\b|\bcmap\b|\baxis scale\b|"
    r"\blog(?:arithmic)? scale|\bprojection\b|\btick label", re.IGNORECASE)
_CLIPPING_LANGUAGE = re.compile(
    r"\bclipp|\bcut off\b|\bcut in half\b|"
    r"\bpartially (?:cut|hidden|outside)", re.IGNORECASE)
_ENTIRELY_OUTSIDE_LANGUAGE = re.compile(
    r"entirely outside|completely outside|not (?:present|visible) in the "
    r"saved image", re.IGNORECASE)


def _remap_family(family: ErrorFamily, evidence: str) -> ErrorFamily:
    """File a finding under the family ASSIGNMENT.md assigns its defect."""
    if family is ErrorFamily.WRONG_CHART \
            and _ORDER_LANGUAGE.search(evidence) \
            and not _CHART_PRESENCE_LANGUAGE.search(evidence):
        return ErrorFamily.WRONG_DATA
    if family is ErrorFamily.WRONG_DATA \
            and _CHART_PRESENCE_LANGUAGE.search(evidence) \
            and not _ORDER_LANGUAGE.search(evidence):
        return ErrorFamily.WRONG_CHART
    if family in (ErrorFamily.WRONG_DATA, ErrorFamily.WRONG_CHART) \
            and _CLIPPING_LANGUAGE.search(evidence) \
            and not _ENTIRELY_OUTSIDE_LANGUAGE.search(evidence) \
            and not _CHART_PRESENCE_LANGUAGE.search(evidence) \
            and not _ORDER_LANGUAGE.search(evidence):
        return ErrorFamily.HARD_TO_READ
    return family


def _remap_and_dedup(findings: list[Error]) -> list[Error]:
    kept: dict[ErrorFamily, Error] = {}
    for error in findings:
        family = _remap_family(error.family, error.evidence)
        kept.setdefault(family, Error(family=family, evidence=error.evidence))
    return list(kept.values())




# --------------------------------------------------------------------------
# Deterministic verification and fact layer
# --------------------------------------------------------------------------
# Three model-free components, each audited offline before inclusion:
# (1) edge verification for clipping claims -- a claim that text is cut off
#     at an image edge is checkable: real clipping leaves ink in the outer
#     pixel rows of that edge (audited on the diagnostic subset: 1 of 19
#     clipping claims was physically real);
# (2) an explicit DPI request compared with the PNG's own metadata
#     (fires on exactly the three true violations across all 125 dev runs);
# (3) literal number series from the instructions compared with literal
#     lists in the last successful figure-writing command (fires on exactly
#     one true wrong-order run across all 125; sorting requests suppress
#     the order rule).

_CLIP_EDGE_PATTERN = re.compile(
    r"(?:cut off|clipp\w*)[^.]{0,60}?(top|bottom|left|right)|"
    r"(top|bottom|left|right)[^.]{0,60}?(?:cut off|clipp\w*)", re.IGNORECASE)
_CLIP_ANY_PATTERN = re.compile(r"cut off|clipp\w*", re.IGNORECASE)


def _edge_ink(figure_bytes: bytes) -> dict[str, bool] | None:
    """Whether any non-background ink touches each image edge (3px strips)."""
    try:
        with Image.open(io.BytesIO(figure_bytes)) as image:
            gray = image.convert("L")
            width, height = gray.size
            corners = [gray.getpixel((0, 0)), gray.getpixel((width - 1, 0)),
                       gray.getpixel((0, height - 1)),
                       gray.getpixel((width - 1, height - 1))]
            background = max(set(corners), key=corners.count)

            def has_ink(box) -> bool:
                strip = gray.crop(box)
                low, high = strip.getextrema()
                return (background - low > 40) or (high - background > 40)

            return {
                "top": has_ink((0, 0, width, 3)),
                "bottom": has_ink((0, height - 3, width, height)),
                "left": has_ink((0, 0, 3, height)),
                "right": has_ink((width - 3, 0, width, height)),
            }
    except Exception:  # noqa: BLE001 - unverifiable image: keep the claim
        return None


def _verify_clipping_claims(findings: list[Error], run: Run) -> list[Error]:
    """Strike hard_to_read clipping sentences whose claimed edge has no ink."""
    if run.figure is None:
        return findings
    ink = _edge_ink(run.figure.read_bytes())
    if ink is None:
        return findings
    kept: list[Error] = []
    for error in findings:
        if error.family is not ErrorFamily.HARD_TO_READ \
                or not _CLIP_ANY_PATTERN.search(error.evidence):
            kept.append(error)
            continue
        sentences = []
        for sentence in re.split(r"(?<=[.;])\s+", error.evidence):
            match = _CLIP_EDGE_PATTERN.search(sentence)
            if match:
                edge = (match.group(1) or match.group(2)).lower()
                if not ink[edge]:
                    continue
            elif _CLIP_ANY_PATTERN.search(sentence) and not any(ink.values()):
                continue
            sentences.append(sentence)
        remaining = " ".join(sentences).strip()
        if remaining:
            kept.append(Error(family=error.family, evidence=remaining[:600]))
    return kept


_DPI_MIN_PATTERN = re.compile(
    r"at\s+least\s+(\d{2,4})\s*dpi|minimum\s+(?:of\s+)?(\d{2,4})\s*dpi",
    re.IGNORECASE)
_DPI_EXACT_PATTERN = re.compile(
    r"(?:\bat\b|\bof\b|\bto\b|=|:)?\s*(\d{2,4})\s*dpi|"
    r"dpi\s*(?:of|=|:)?\s*(\d{2,4})", re.IGNORECASE)
_DPI_TOLERANCE = 0.05


def _dpi_violation(run: Run) -> str | None:
    minimum = _DPI_MIN_PATTERN.search(run.instructions)
    exact = None if minimum else _DPI_EXACT_PATTERN.search(run.instructions)
    if not minimum and not exact:
        return None
    if run.figure is None:
        return None
    try:
        with Image.open(io.BytesIO(run.figure.read_bytes())) as image:
            recorded = image.info.get("dpi")
        measured = float(recorded[0]) if recorded else None
    except Exception:  # noqa: BLE001
        return None
    if not measured or measured <= 0:
        return None
    if minimum:
        value = int(next(g for g in minimum.groups() if g))
        if measured < value * (1 - _DPI_TOLERANCE):
            return (f"the instructions ask for at least {value} dpi, but "
                    f"figure.png's metadata records about {measured:.0f} dpi")
        return None
    value = int(next(g for g in exact.groups() if g))
    if abs(measured - value) > value * _DPI_TOLERANCE:
        return (f"the instructions ask for {value} dpi, but figure.png's "
                f"metadata records about {measured:.0f} dpi")
    return None


_NUMBER_PATTERN = r"-?\d+(?:\.\d+)?"
_SERIES_IN_TEXT = re.compile(
    rf"{_NUMBER_PATTERN}(?:\s*,\s*{_NUMBER_PATTERN}){{3,}}")
_SERIES_IN_CODE = re.compile(
    rf"[\[(]\s*({_NUMBER_PATTERN}(?:\s*,\s*{_NUMBER_PATTERN}){{3,}})\s*[\])]")
_REORDER_REQUEST = re.compile(
    r"\bsort(?:ed|ing)?\b|\bdescending\b|\bascending\b|\balphabetical",
    re.IGNORECASE)


def _series_numbers(text: str) -> tuple[float, ...]:
    return tuple(float(n) for n in re.findall(_NUMBER_PATTERN, text))


def _final_plot_code(messages: list[dict]) -> str | None:
    results: dict[str, int | None] = {}
    for message in messages:
        if message.get("role") == "tool":
            try:
                payload = json.loads(str(message.get("content")))
                results[message.get("tool_call_id")] = payload.get("returncode")
            except (TypeError, ValueError):
                continue
    last = None
    for message in messages:
        for call in (message.get("tool_calls") or []):
            try:
                command = json.loads(call["function"]["arguments"]).get("command", "")
            except (KeyError, TypeError, ValueError):
                continue
            if "savefig" not in command:
                continue
            if results.get(call.get("id")) == 0:
                last = command
    return last


def _literal_array_violation(run: Run) -> str | None:
    wanted_series = [s for s in
                     (_series_numbers(m.group(0))
                      for m in _SERIES_IN_TEXT.finditer(run.instructions))
                     if len(s) >= 4]
    if not wanted_series:
        return None
    code = _final_plot_code(run.messages)
    if code is None:
        return None
    code_series = [_series_numbers(m.group(1))
                   for m in _SERIES_IN_CODE.finditer(code)]
    if not code_series:
        return None
    reordering = bool(_REORDER_REQUEST.search(run.instructions))
    for wanted in wanted_series:
        if any(found == wanted for found in code_series):
            continue
        permuted = [found for found in code_series
                    if len(found) == len(wanted)
                    and sorted(found) == sorted(wanted)]
        if permuted and not reordering:
            return ("the instructions give the series "
                    f"{list(wanted)} in a fixed order, but the plotting "
                    f"code uses the same numbers re-ordered as "
                    f"{list(permuted[0])}")
        for found in code_series:
            if len(found) != len(wanted) or sorted(found) == sorted(wanted):
                continue
            diffs = [i for i, (a, b) in enumerate(zip(wanted, found)) if a != b]
            if 0 < len(diffs) <= max(1, len(wanted) // 3):
                positions = ", ".join(str(i + 1) for i in diffs)
                return ("the plotting code alters the series "
                        f"{list(wanted)} from the instructions at "
                        f"position(s) {positions}: it uses {list(found)}")
    return None


def _add_deterministic_facts(findings: list[Error], run: Run) -> list[Error]:
    """Merge model-free findings, keeping one error per family."""
    by_family = {error.family: error for error in findings}
    for family, evidence in ((ErrorFamily.WRONG_CHART, _dpi_violation(run)),
                             (ErrorFamily.WRONG_DATA,
                              _literal_array_violation(run))):
        if not evidence:
            continue
        present = by_family.get(family)
        if present is None:
            by_family[family] = Error(family=family, evidence=evidence)
        elif evidence.split(",")[0] not in present.evidence:
            by_family[family] = Error(
                family=family,
                evidence=(present.evidence + "; also " + evidence)[:600])
    return list(by_family.values())


def validate(run: Run) -> list[Error]:
    """Everything wrong with one run."""
    execution = judge_execution(run)
    if execution:
        # With no valid figure there is nothing for the other three families
        # to judge; ground truth treats execution_failure as terminal.
        return execution
    with ThreadPoolExecutor(max_workers=len(_JUDGED_FAMILIES)) as pool:
        results = list(pool.map(lambda family: _ask(run, family),
                                _JUDGED_FAMILIES))
    raw = [error for errors in results for error in errors]
    # Family assignment is deterministic (see _remap_family): a model
    # arbitration pass measured here erased more true positives than it
    # repaired, so it was removed.
    mapped = _remap_and_dedup(raw)
    final = _add_deterministic_facts(
        _verify_clipping_claims(mapped, run), run)
    _diag(run.run_id, "validate", {
        "run_id": run.run_id,
        "raw_findings": [[e.family.value, e.evidence] for e in raw],
        "after_filter": [[e.family.value, e.evidence] for e in mapped],
        "final": [[e.family.value, e.evidence] for e in final],
    })
    return final
