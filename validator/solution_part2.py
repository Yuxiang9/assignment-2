"""Frozen Part 2 validator, kept verbatim for reproducibility.

The submitted validator is validator/solution.py (the Part 4 version).
Re-running the Part 2 numbers:
    uv run python -m validator.runner --solution validator.solution_part2 ...

Original docstring follows.

Design (see report for the motivating error analysis):

1. `execution_failure` is decided deterministically from the artifact itself:
   a run with no decodable, non-empty `figure.png` produced no valid figure,
   and a run with one did. This removes the judge model from a family it does
   not need to answer and is model-agnostic by construction.
2. The three remaining families are each judged by one focused question to the
   fixed VLM. Every question carries the family's full rubric from
   ASSIGNMENT.md, an explicit instruction to check only what the task actually
   requested, and a fixed `VERDICT:`/`EVIDENCE:` answer format that is parsed
   structurally rather than by hoping the reply starts with "YES".
3. The model sees the task verbatim, the input files, a digest of the
   trajectory that keeps every executed command (the plotting code is the
   evidence) while truncating prose and tool output, and the final figure.
   If the request still exceeds the model context, the text is compacted
   toward a budget read from the server and the image is downscaled, keeping
   the beginnings and ends of the trajectory and inputs.

Each function evaluates a single run object and returns the errors it finds.
An empty list means that no errors were found. `validator/runner.py` defines
what a run object contains, and `ASSIGNMENT.md` defines the four error
families you may report.
"""

from __future__ import annotations

import io
import base64
import json
import re
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
  reversed or shuffled, panels showing data they were not assigned).

Do NOT report here: chart type, axis labels or titles, styling, legends, or
readability problems. Those belong to other families. Judge only whether the
drawn data matches the requested data. Derive the expected data from the task
and the input files, and use the agent's plotting code to resolve anything the
image alone leaves ambiguous. Being correct but drawn with an unrequested
style is NOT wrong_data."""

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
  wrong colour for a named series; areas not filled when asked; whiskers,
  medians, connectors, or boxes missing; polygons not closed; requested line
  offsets not applied.
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
        "List every explicit design requirement in the instructions (type, "
        "layout, axes, labels, legend, style); check each one against the "
        "figure.",
    ),
    ErrorFamily.HARD_TO_READ: (
        _HARD_TO_READ_RUBRIC,
        "Inspect each text element and data mark in the image for clipping, "
        "overlap, occlusion, contrast, distinguishability, and squeezing.",
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


def _ask(run: Run, family: ErrorFamily) -> list[Error]:
    rubric, steps = _RUBRICS[family]
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
Report YES only when you are confident an explicit requirement is violated;
when the evidence is ambiguous or the task left the choice open, answer NO.

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
                sent_image = smaller
    answer = response["choices"][0]["message"]["content"] or ""
    if not _VERDICT_PATTERN.search(answer) and \
            response["choices"][0].get("finish_reason") == "length":
        # The reasoning ran past the token budget before reaching the verdict.
        # Re-ask the request that succeeded for the conclusion alone rather
        # than mis-reading the missing verdict as NO.
        followup = ask(
            sent_prompt
            + "\nReply with ONLY the two final lines (VERDICT and EVIDENCE), "
              "no other text.",
            sent_image,
        )
        answer = followup["choices"][0]["message"]["content"] or answer
    positive, evidence = _parse_verdict(answer)
    if not positive:
        return []
    return [Error(family=family, evidence=evidence)]


# --------------------------------------------------------------------------
# The four family judgments
# --------------------------------------------------------------------------

def judge_data_and_chart(run: Run) -> list[Error]:
    """Whether the figure plots the requested data, built the requested way."""
    return _ask(run, ErrorFamily.WRONG_DATA) + _ask(run, ErrorFamily.WRONG_CHART)


def judge_readability(run: Run) -> list[Error]:
    """Whether the figure can be read."""
    return _ask(run, ErrorFamily.HARD_TO_READ)


def validate(run: Run) -> list[Error]:
    """Everything wrong with one run."""
    execution = judge_execution(run)
    if execution:
        # With no valid figure there is nothing for the other three families
        # to judge; ground truth treats execution_failure as terminal.
        return execution
    families = (ErrorFamily.WRONG_DATA, ErrorFamily.WRONG_CHART,
                ErrorFamily.HARD_TO_READ)
    with ThreadPoolExecutor(max_workers=len(families)) as pool:
        results = list(pool.map(lambda family: _ask(run, family), families))
    return [error for errors in results for error in errors]
