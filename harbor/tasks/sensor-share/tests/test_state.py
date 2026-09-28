"""Verifier for sensor-share.

Strategy (see harbor/README.md): S1-style artifact checks, exact expected
values hand-derived from the task data and written as literals, and one
re-execution of the delivered script in a scrubbed copy of /app to prove the
script actually reproduces the deliverables. The PNG's pixels are never
graded: bar geometry, label placement, and legibility stay the VLM
validator's job, and that limitation is reported.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

APP = Path("/app")
FIGURE = APP / "figure.png"
SIDECAR = APP / "plotted_values.json"
SCRIPT_NAME = "plot.py"
PYTHON = "/usr/local/bin/python3"
REEXEC_TIMEOUT = 120

EXPECTED = {
    "Alder": 17.5,
    "Birch": 21.0,
    "Cedar": 31.5,
    "Dogwood": 30.0,
}
INPUT_SHA256 = "f22ef4fdd40b112d10f92143deda3fc5edbe2b0b8b1d535fd50adba601f93c55"

# The delivered files are snapshotted before any re-run: /app is writable at
# verify time, and a script that writes by absolute path would overwrite its
# own deliverables during the re-execution below.
DELIVERED_DIR = Path(tempfile.mkdtemp(prefix="delivered_"))
for _name in ("figure.png", "plotted_values.json"):
    if (APP / _name).exists():
        shutil.copy2(APP / _name, DELIVERED_DIR / _name)


def _delivered(name: str) -> Path:
    path = DELIVERED_DIR / name
    assert path.exists(), f"no /app/{name} was delivered; the task requires it"
    return path


def _find_script() -> Path:
    """plot.py, or any delivered script that saves a figure (lenient on name)."""
    named = APP / SCRIPT_NAME
    if named.exists():
        return named
    fallback = sorted(
        path for path in APP.rglob("*.py")
        if path.is_file() and "savefig" in path.read_text(errors="replace")
    )
    assert fallback, (
        f"no {SCRIPT_NAME} in /app and no other .py file there calls savefig; "
        "the task requires a re-runnable plotting script"
    )
    return fallback[0]


# ------------------------------------------------------------------ S1 checks
def test_figure_exists():
    assert FIGURE.exists(), f"no figure at {FIGURE}; the task requires one"


def test_figure_is_a_valid_nonblank_png():
    import numpy as np
    from PIL import Image

    delivered = _delivered("figure.png")
    size = delivered.stat().st_size
    assert size > 1000, f"figure.png is only {size} bytes, so it is not a real chart"
    with Image.open(delivered) as image:
        image.verify()
    with Image.open(delivered) as image:
        assert image.format == "PNG", f"figure.png is a {image.format}, not a PNG"
        assert min(image.size) > 100, f"figure.png is {image.size}, too small to read"
        pixels = np.asarray(image.convert("RGB")).reshape(-1, 3)
    distinct = len(np.unique(pixels, axis=0))
    assert distinct > 4, f"figure.png has {distinct} distinct colours: a blank canvas"


def test_input_file_was_not_modified():
    import hashlib

    path = APP / "readings.csv"
    assert path.exists(), "readings.csv is missing from /app"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == INPUT_SHA256, (
        f"readings.csv was modified (sha256 {digest}); the instructions forbid editing it"
    )


def test_plotting_script_was_left_behind():
    script = _find_script()
    assert script.stat().st_size > 0, f"{script} is empty"


# ------------------------------------------- the delivered numbers themselves
def test_sidecar_declares_exactly_the_expected_values():
    """The hand-derived answer key, as literals. Any wrong number fails here."""
    declared = json.loads(_delivered("plotted_values.json").read_text())
    assert isinstance(declared, dict), (
        f"plotted_values.json holds a {type(declared).__name__}, expected an object"
    )
    assert sorted(declared) == sorted(EXPECTED), (
        f"plotted_values.json keys are {sorted(declared)}, expected {sorted(EXPECTED)}"
    )
    for key, value in declared.items():
        assert isinstance(value, (int, float)) and not isinstance(value, bool), (
            f"plotted_values.json[{key!r}] is {value!r} ({type(value).__name__}); "
            "the schema requires a JSON number"
        )
    assert {key: float(value) for key, value in declared.items()} == pytest.approx(
        EXPECTED, rel=1e-6
    ), f"plotted_values.json declares {declared}, expected {EXPECTED}"


# ----------------------------------------------- the script reproduces it all
def test_rerunning_the_script_reproduces_figure_and_sidecar():
    """Re-execute the delivered script in a scrubbed copy of /app.

    Catches a script that crashes, one that was never runnable, and one whose
    outputs disagree with what was handed in. The copy is scrubbed of the
    deliverables first so nothing delivered can masquerade as re-run output.
    """
    script = _find_script()
    relative = script.relative_to(APP)
    workdir = Path(tempfile.mkdtemp(prefix="reexec_")) / "app"
    shutil.copytree(APP, workdir)
    for stale in (*workdir.rglob("*.png"), workdir / "plotted_values.json"):
        if stale.exists():
            stale.unlink()
    env = dict(os.environ, MPLBACKEND="Agg", HOME="/tmp", PYTHONDONTWRITEBYTECODE="1")
    try:
        completed = subprocess.run(
            [PYTHON, str(relative)], cwd=workdir, env=env,
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=REEXEC_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(f"re-running {relative} did not finish within {REEXEC_TIMEOUT}s")
    assert completed.returncode == 0, (
        f"re-running {relative} failed with exit {completed.returncode}.\n"
        f"stderr tail:\n{completed.stderr[-2000:]}"
    )
    assert (workdir / "figure.png").exists(), (
        "the re-run script wrote no figure.png in its working directory; "
        "plot.py must save its outputs by bare filename"
    )
    resaved = workdir / "plotted_values.json"
    assert resaved.exists(), (
        "the re-run script wrote no plotted_values.json in its working directory"
    )
    redeclared = json.loads(resaved.read_text())
    delivered = json.loads(_delivered("plotted_values.json").read_text())
    assert redeclared == delivered, (
        f"re-running the script declares {redeclared} but the delivered sidecar "
        f"says {delivered}; the deliverables do not come from this script"
    )
