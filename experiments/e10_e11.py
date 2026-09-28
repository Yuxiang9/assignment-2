"""Candidate components e10 (dual-filing dedup) and e11 (contrast check).

Both are deterministic post-processing; this module holds the reference
implementations plus their offline audits. They are wired into the
validator only after the audits pass.
"""

from __future__ import annotations

import io
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from PIL import Image

# --------------------------------------------------------------------------
# e10: dual-filing dedup
# --------------------------------------------------------------------------
# One real defect sometimes gets filed by two family questions at once
# ("sd instead of sem" as both wrong_data and wrong_chart); each duplicate
# is a guaranteed false positive in one family. Two errors in different
# families whose evidence is near-duplicate are collapsed toward the family
# their combined language names. Distinct coexisting defects (rotation
# ignored + labels overlap) sit well below the similarity gate and survive.

_HR_LANGUAGE = re.compile(
    r"invisible|low contrast|blends? with|nearly indistinguishable|"
    r"indistinguishable|cut off|clipp|overlapp|covered by|obscur|squeez",
    re.IGNORECASE)
_ORDER_LANGUAGE = re.compile(
    r"\border(?:ed|ing)?\b|\bsorted\b|\breversed\b|\balphabetical|"
    r"\bdescending\b|\bascending\b", re.IGNORECASE)
_CHART_LANGUAGE = re.compile(
    r"\btitle\b|\baxis label|\bx-?label|\by-?label|\blegend\b|"
    r"\bcolou?r ?bar\b|\bcolou?rmap\b|\bcmap\b|\bscale\b|\bprojection\b|"
    r"\btick label|\bmarker|\bline style|\bchart type|"
    r"(?:instead of|not) (?:a|the required)?[a-zA-Z0-9 -]*"
    r"(?:plot|chart|diagram|heatmap|voxel|pie|sankey)\b",
    re.IGNORECASE)
_VALUE_LANGUAGE = re.compile(
    r"standard (?:deviation|error)|values? (?:differ|are (?:wrong|incorrect))|"
    r"wrong (?:values?|data|aggregat)|instead of the (?:requested|required) "
    r"(?:values?|data|series|running total|cumulative)", re.IGNORECASE)


def _dedup_target(text: str) -> str | None:
    """The family the combined duplicate language names, if any."""
    if _HR_LANGUAGE.search(text):
        return "hard_to_read"
    if _ORDER_LANGUAGE.search(text) and not _CHART_LANGUAGE.search(text):
        return "wrong_data"
    if _CHART_LANGUAGE.search(text):
        return "wrong_chart"
    if _VALUE_LANGUAGE.search(text):
        return "wrong_data"
    return None


def _similar(a: str, b: str) -> bool:
    ratio = SequenceMatcher(None, a.lower(), b.lower()).ratio()
    if ratio >= 0.45:
        return True
    ta, tb = set(a.lower().split()), set(b.lower().split())
    jaccard = len(ta & tb) / max(1, len(ta | tb))
    return ratio >= 0.35 and jaccard >= 0.25


def dedup_dual_filings(errors: list[dict]) -> list[dict]:
    """Collapse near-duplicate cross-family errors toward the language target.

    `errors` are {"family", "evidence"} dicts (at most one per family).
    Conservative: a pair with no language target, or whose target names
    neither member and no present third family, is left alone.
    """
    content = [e for e in errors if e["family"] != "execution_failure"]
    families_present = {e["family"] for e in content}
    drop: set[str] = set()
    for i in range(len(content)):
        for j in range(i + 1, len(content)):
            a, b = content[i], content[j]
            if a["family"] in drop or b["family"] in drop:
                continue
            if not _similar(a["evidence"], b["evidence"]):
                continue
            target = _dedup_target(a["evidence"] + " " + b["evidence"])
            if target is None:
                continue
            if target == a["family"]:
                drop.add(b["family"])
            elif target == b["family"]:
                drop.add(a["family"])
            elif target in families_present:
                # the defect's proper family already holds an error:
                # both copies here are misfiled duplicates of it
                drop.add(a["family"])
                drop.add(b["family"])
    return [e for e in errors if e["family"] not in drop]


# --------------------------------------------------------------------------
# e11: low-contrast / invisible-element check
# --------------------------------------------------------------------------
# Several hard_to_read truths share one mechanism: an element drawn in a
# colour too close to the rendered background, with the colour sitting in
# the agent's code as a literal. The check collects colour literals from
# drawing-call kwargs across every successful command, measures the
# rendered background from the figure's corners, and flags a WCAG-style
# contrast ratio below 2.5:1. facecolor/background kwargs are excluded
# (those SET the background).

_NAMED_COLORS = {
    "white": (255, 255, 255), "w": (255, 255, 255),
    "whitesmoke": (245, 245, 245), "snow": (255, 250, 250),
    "ivory": (255, 255, 240), "lightyellow": (255, 255, 224),
    "lightgray": (211, 211, 211), "lightgrey": (211, 211, 211),
    "gainsboro": (220, 220, 220), "beige": (245, 245, 220),
    "linen": (250, 240, 230), "azure": (240, 255, 255),
    "mintcream": (245, 255, 250), "aliceblue": (240, 248, 255),
    "ghostwhite": (248, 248, 255), "honeydew": (240, 255, 240),
    "seashell": (255, 245, 238), "lavenderblush": (255, 240, 245),
    "oldlace": (253, 245, 230), "floralwhite": (255, 250, 240),
    "cornsilk": (255, 248, 220), "lightcyan": (224, 255, 255),
    "black": (0, 0, 0), "k": (0, 0, 0),
    "dimgray": (105, 105, 105), "dimgrey": (105, 105, 105),
    "darkslategray": (47, 79, 79), "darkslategrey": (47, 79, 79),
    "midnightblue": (25, 25, 112), "navy": (0, 0, 128),
    "darkblue": (0, 0, 139), "darkgreen": (0, 100, 0),
    "maroon": (128, 0, 0), "darkred": (139, 0, 0),
}
_COLOR_KWARG = re.compile(
    r"(?<![_a-zA-Z])(?:color|c|fontcolor|textcolor|labelcolor)"
    r"\s*=\s*(?:['\"])(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3}|"
    r"[a-zA-Z]+)(?:['\"])")
#: Lines whose colour kwargs are idiomatically NOT data/text ink: legend
#: proxy handles, unlabeled reference lines, grids, and deliberately
#: translucent fills.
_NON_INK_LINE = re.compile(r"Line2D\s*\(|\bgrid\s*\(|alpha\s*=\s*0?\.[0-3]\b")
_REFERENCE_LINE = re.compile(r"ax[a-z]*\.(?:axvline|axhline)|plt\.(?:axvline|axhline)")
_HAS_LABEL = re.compile(r"label\s*=")
#: White/near-white patch shapes are masking idioms (e.g. the donut hole).
_PATCH_CONSTRUCTOR = re.compile(r"\b(?:Circle|Rectangle|Wedge|FancyBboxPatch)\s*\(")
#: A run that restyles its canvas DARK breaks the corners-are-the-ink-
#: background assumption; stay silent on those. Light restyling is fine.
_DARK_STYLE = re.compile(
    r"dark_background|seaborn-v?0?_?dark|set_style\(\s*['\"]dark",
    re.IGNORECASE)
_CANVAS_COLOR = re.compile(
    r"(?:set_facecolor\(|(?:subplots|figure|add_axes|add_subplot|rcParams)"
    r"[^\n]*?facecolor\s*=\s*)\(?\s*['\"]([^'\"]+)['\"]")


def _restyles_canvas_dark(code: str) -> bool:
    if _DARK_STYLE.search(code):
        return True
    for match in _CANVAS_COLOR.finditer(code):
        rgb = _to_rgb(match.group(1))
        if rgb is None or _luminance(rgb) < 0.5:
            return True                # dark or unparsable canvas colour
    return False
_BG_KWARG = re.compile(
    r"(?:facecolor|fc|set_facecolor|figure\.patch|axes\.facecolor|"
    r"figure\.facecolor)")
_CONTRAST_THRESHOLD = 2.5


def _to_rgb(token: str) -> tuple[int, int, int] | None:
    token = token.strip()
    if token.startswith("#"):
        digits = token[1:]
        if len(digits) == 3:
            digits = "".join(ch * 2 for ch in digits)
        try:
            return tuple(int(digits[k:k + 2], 16) for k in (0, 2, 4))
        except ValueError:
            return None
    return _NAMED_COLORS.get(token.lower())


def _luminance(rgb: tuple[int, int, int]) -> float:
    def channel(value: int) -> float:
        v = value / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _drawn_color_literals(messages: list[dict]) -> set[str]:
    """Colour tokens in drawing-call kwargs of successful commands."""
    results: dict[str, int | None] = {}
    for message in messages:
        if message.get("role") == "tool":
            try:
                payload = json.loads(str(message.get("content")))
                results[message.get("tool_call_id")] = payload.get("returncode")
            except (TypeError, ValueError):
                continue
    tokens: set[str] = set()
    all_code = []
    for message in messages:
        for call in (message.get("tool_calls") or []):
            if results.get(call.get("id")) == 0:
                try:
                    all_code.append(json.loads(
                        call["function"]["arguments"]).get("command", ""))
                except (KeyError, TypeError, ValueError):
                    pass
    if _restyles_canvas_dark("\n".join(all_code)):
        return tokens
    for message in messages:
        for call in (message.get("tool_calls") or []):
            if results.get(call.get("id")) != 0:
                continue
            try:
                command = json.loads(call["function"]["arguments"]).get("command", "")
            except (KeyError, TypeError, ValueError):
                continue
            for line in command.split("\n"):
                if _BG_KWARG.search(line):
                    continue                      # sets a background, not ink
                if _NON_INK_LINE.search(line):
                    continue
                if _REFERENCE_LINE.search(line) and not _HAS_LABEL.search(line):
                    continue                      # unlabeled reference line
                if _PATCH_CONSTRUCTOR.search(line):
                    continue                      # masking shape, not ink
                tokens.update(m.group(1) for m in _COLOR_KWARG.finditer(line))
    return tokens


def _background_rgb(figure_bytes: bytes) -> tuple[int, int, int] | None:
    try:
        with Image.open(io.BytesIO(figure_bytes)) as image:
            rgb = image.convert("RGB")
            width, height = rgb.size
            corners = [rgb.getpixel((2, 2)), rgb.getpixel((width - 3, 2)),
                       rgb.getpixel((2, height - 3)),
                       rgb.getpixel((width - 3, height - 3))]
    except Exception:  # noqa: BLE001
        return None
    return max(set(corners), key=corners.count)


def low_contrast_violation(messages: list[dict],
                           figure_bytes: bytes | None) -> str | None:
    if figure_bytes is None:
        return None
    background = _background_rgb(figure_bytes)
    if background is None:
        return None
    worst: tuple[float, str] | None = None
    for token in _drawn_color_literals(messages):
        rgb = _to_rgb(token)
        if rgb is None:
            continue
        ratio = contrast_ratio(rgb, background)
        if ratio < _CONTRAST_THRESHOLD and (worst is None or ratio < worst[0]):
            worst = (ratio, token)
    if worst is None:
        return None
    ratio, token = worst
    return (f"an element is drawn in {token} on a background of "
            f"rgb{background} (contrast ratio about {ratio:.1f}:1, below "
            f"2.5:1), making it effectively invisible or very hard to read")
