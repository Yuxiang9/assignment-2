"""Deterministic DPI requirement check (candidate component).

Extracts an explicit DPI requirement from task instructions and compares it
with the PNG's own metadata. Conservative by design:

* no DPI mention in the instructions -> no finding;
* missing/withheld PNG DPI metadata -> unknown, no finding;
* "at least N dpi" is a minimum: only a measured value clearly below N
  fails; an exact request fails only outside a small tolerance.

The figure's pixel size is never converted back to inches: a tightly
cropped PNG says nothing reliable about the original canvas.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

from PIL import Image

#: Accept small metadata rounding (matplotlib writes 99.9998 for 100).
RELATIVE_TOLERANCE = 0.05

_MIN_PATTERN = re.compile(
    r"at\s+least\s+(\d{2,4})\s*dpi|minimum\s+(?:of\s+)?(\d{2,4})\s*dpi",
    re.IGNORECASE)
_EXACT_PATTERN = re.compile(
    r"(?:\bat\b|\bof\b|\bto\b|=|:)?\s*(\d{2,4})\s*dpi|dpi\s*(?:of|=|:)?\s*(\d{2,4})",
    re.IGNORECASE)


def requested_dpi(instructions: str) -> tuple[int, bool] | None:
    """(value, is_minimum) for an explicit DPI request, else None."""
    minimum = _MIN_PATTERN.search(instructions)
    if minimum:
        value = next(g for g in minimum.groups() if g)
        return int(value), True
    exact = _EXACT_PATTERN.search(instructions)
    if exact:
        value = next(g for g in exact.groups() if g)
        return int(value), False
    return None


def measured_dpi(figure_bytes: bytes) -> float | None:
    try:
        with Image.open(io.BytesIO(figure_bytes)) as image:
            dpi = image.info.get("dpi")
    except Exception:  # noqa: BLE001 - unreadable image is judged elsewhere
        return None
    if not dpi:
        return None
    try:
        value = float(dpi[0])
    except (TypeError, ValueError, IndexError):
        return None
    return value if value > 0 else None


def dpi_violation(instructions: str, figure: Path | None) -> str | None:
    """Evidence text for a DPI violation, or None when compliant/unknown."""
    request = requested_dpi(instructions)
    if request is None or figure is None:
        return None
    measured = measured_dpi(figure.read_bytes())
    if measured is None:
        return None
    value, is_minimum = request
    if is_minimum:
        if measured < value * (1 - RELATIVE_TOLERANCE):
            return (f"the instructions ask for at least {value} dpi, but "
                    f"figure.png's metadata records about {measured:.0f} dpi")
        return None
    if abs(measured - value) > value * RELATIVE_TOLERANCE:
        return (f"the instructions ask for {value} dpi, but figure.png's "
                f"metadata records about {measured:.0f} dpi")
    return None


if __name__ == "__main__":
    import json

    failures = []
    # positive fixtures: the three diagnostic-subset runs
    for rid, expect in [("046", True), ("060", True), ("130", True)]:
        record = json.load(open(f"artifacts/{rid}/result.json"))
        evidence = dpi_violation(record["task"]["instructions"],
                                 Path(f"artifacts/{rid}/figure.png"))
        if bool(evidence) != expect:
            failures.append(f"{rid}: expected violation={expect}, got {evidence!r}")
        else:
            print(f"{rid}: {evidence}")
    # extraction unit cases
    assert requested_dpi("Save the figure at 120 dpi.") == (120, False)
    assert requested_dpi("Use a DPI of 150 for the export.") == (150, False)
    assert requested_dpi("save at a dpi: 90") == (90, False)
    assert requested_dpi("at least 100 dpi") == (100, True)
    assert requested_dpi("high-resolution figure, no dots-per-inch named") is None
    # comparison unit cases
    assert dpi_violation("at least 100 dpi", None) is None
    ok_png = io.BytesIO()
    image = Image.new("RGB", (50, 50)); image.save(ok_png, "PNG", dpi=(100, 100))
    tmp = Path("/tmp/hw2_dpi_fixture.png"); tmp.write_bytes(ok_png.getvalue())
    assert dpi_violation("Save the figure at 100 dpi.", tmp) is None       # exact ok
    assert dpi_violation("Save the figure at 120 dpi.", tmp)               # exact fail
    assert dpi_violation("Save at least 100 dpi.", tmp) is None            # min ok
    assert dpi_violation("Save at least 144 dpi.", tmp)                    # min fail
    no_meta = io.BytesIO(); Image.new("RGB", (50, 50)).save(no_meta, "PNG")
    tmp.write_bytes(no_meta.getvalue())
    assert dpi_violation("Save the figure at 120 dpi.", tmp) is None       # unknown
    tmp.unlink()
    if failures:
        raise SystemExit("\n".join(failures))
    print("all dpi_check unit cases pass")
