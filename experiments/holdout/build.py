"""Build the reserved validation suite: 12 correct/faulty pairs + 2 crashes.

Each task gets a correct rendering (label []) and one controlled faulty
rendering (one intended defect, labelled with its family). Runs are written
in the released result.json format under experiments/holdout/runs/ with a
label file alongside. Labels come from construction and are then verified
by inspecting every figure; they are NOT human-reviewed course labels and
are never presented as the required fixed-agent runs.

Reserve: no validator may be scored on this suite until a finalist is
selected; scoring it converts it into development data.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"

FILMS_CSV = """title,gross,year
Starfall,412,2019
Iron Harvest,388,2021
Quiet Coast,205,2018
Midnight Freight,510,2022
Paper Lanterns,167,2020
The Long Thaw,478,2017
Gullwing,299,2023
Second Orchard,352,2016
Noon Eclipse,443,2024
Cinder Road,251,2015
"""

# ---------------------------------------------------------------- task specs
# Each spec: instructions, correct(ax-code str), faulty(ax-code str),
# faulty family + evidence, optional inputs {name: text}.

SPECS: dict[str, dict] = {}

SPECS["ho-quarterly-revenue"] = dict(
    instructions=(
        "Using matplotlib, draw a GROUPED (side-by-side) bar chart of quarterly "
        "revenue, in millions of dollars, for two products across Q1-Q4. Values: "
        "Alpha: Q1 12, Q2 15, Q3 9, Q4 18; Beta: Q1 8, Q2 11, Q3 14, Q4 10. One "
        "pair of bars per quarter with quarters Q1, Q2, Q3, Q4 left to right, a "
        "legend naming both products, y axis starting at zero, title exactly "
        "\"Quarterly revenue by product\", x axis labeled \"Quarter\", y axis "
        "labeled \"Revenue (USD millions)\". Save the figure as figure.png."),
    correct="""
alpha = [12, 15, 9, 18]; beta = [8, 11, 14, 10]
x = np.arange(4); w = 0.38
ax.bar(x - w/2, alpha, w, label="Alpha"); ax.bar(x + w/2, beta, w, label="Beta")
ax.set_xticks(x); ax.set_xticklabels(["Q1", "Q2", "Q3", "Q4"])
ax.set_ylim(0, 20); ax.legend()
ax.set_title("Quarterly revenue by product")
ax.set_xlabel("Quarter"); ax.set_ylabel("Revenue (USD millions)")
""",
    faulty="""
alpha = [12, 9, 15, 18]; beta = [8, 11, 14, 10]   # Q2 and Q3 of Alpha swapped
x = np.arange(4); w = 0.38
ax.bar(x - w/2, alpha, w, label="Alpha"); ax.bar(x + w/2, beta, w, label="Beta")
ax.set_xticks(x); ax.set_xticklabels(["Q1", "Q2", "Q3", "Q4"])
ax.set_ylim(0, 20); ax.legend()
ax.set_title("Quarterly revenue by product")
ax.set_xlabel("Quarter"); ax.set_ylabel("Revenue (USD millions)")
""",
    family="wrong_data",
    evidence="Alpha's Q2 and Q3 values are swapped: the chart shows Q2=9 and "
             "Q3=15 where the task specifies Q2=15 and Q3=9",
)

SPECS["ho-sem-errorbars"] = dict(
    instructions=(
        "Using matplotlib, plot the mean germination rate of four seed batches "
        "with error bars showing the STANDARD ERROR OF THE MEAN (standard "
        "deviation divided by the square root of the sample count). Batches, in "
        "this order: A mean 62 sd 12 n 16; B mean 71 sd 8 n 16; C mean 55 sd 20 "
        "n 25; D mean 68 sd 10 n 4. Draw one point per batch connected by a "
        "line, with symmetric vertical error bars, batches A-D left to right, y "
        "axis from 0 to 100, title exactly \"Germination rate by batch\", x "
        "axis labeled \"Batch\", y axis labeled \"Germination rate (%)\". Save "
        "the figure as figure.png."),
    correct="""
means = [62, 71, 55, 68]
sems = [12/4, 8/4, 20/5, 10/2]
ax.errorbar(["A", "B", "C", "D"], means, yerr=sems, marker="o", capsize=4)
ax.set_ylim(0, 100)
ax.set_title("Germination rate by batch")
ax.set_xlabel("Batch"); ax.set_ylabel("Germination rate (%)")
""",
    faulty="""
means = [62, 71, 55, 68]
sds = [12, 8, 20, 10]                      # sd plotted instead of sem
ax.errorbar(["A", "B", "C", "D"], means, yerr=sds, marker="o", capsize=4)
ax.set_ylim(0, 100)
ax.set_title("Germination rate by batch")
ax.set_xlabel("Batch"); ax.set_ylabel("Germination rate (%)")
""",
    family="wrong_data",
    evidence="the error bars show the raw standard deviation (e.g. 20 for "
             "batch C) instead of the requested standard error of the mean "
             "(sd/sqrt(n): 3, 2, 4, 5)",
)

SPECS["ho-cumulative-rainfall"] = dict(
    instructions=(
        "Using matplotlib, draw a line chart of CUMULATIVE rainfall over the "
        "months Jan-Jun. Monthly rainfall in mm: Jan 80, Feb 65, Mar 90, Apr "
        "40, May 25, Jun 10. Plot the running total (Jan 80, Feb 145, ..., Jun "
        "310) with circular markers, months on the x axis in calendar order, y "
        "axis starting at zero, title exactly \"Cumulative rainfall\", x axis "
        "labeled \"Month\", y axis labeled \"Cumulative rainfall (mm)\". Save "
        "the figure as figure.png."),
    correct="""
months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
cum = np.cumsum([80, 65, 90, 40, 25, 10])
ax.plot(months, cum, marker="o")
ax.set_ylim(0, 340)
ax.set_title("Cumulative rainfall")
ax.set_xlabel("Month"); ax.set_ylabel("Cumulative rainfall (mm)")
""",
    faulty="""
months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
raw = [80, 65, 90, 40, 25, 10]             # raw monthlies, not the running total
ax.plot(months, raw, marker="o")
ax.set_ylim(0, 340)
ax.set_title("Cumulative rainfall")
ax.set_xlabel("Month"); ax.set_ylabel("Cumulative rainfall (mm)")
""",
    family="wrong_data",
    evidence="the line plots the raw monthly values (ending at 10 mm in June) "
             "instead of the requested running total (ending at 310 mm)",
)

SPECS["ho-top-films"] = dict(
    instructions=(
        "Using matplotlib, read films.csv (columns title, gross, year) and draw "
        "a horizontal bar chart of the FIVE highest-grossing films only. Sort "
        "them by gross in descending order from top to bottom (highest at the "
        "top), x axis starting at zero and labeled \"Gross (USD millions)\", y "
        "axis labeled \"Film\", title exactly \"Top five films by gross\". Save "
        "the figure as figure.png."),
    inputs={"films.csv": FILMS_CSV},
    correct="""
import csv
with open("films.csv") as fh:
    rows = sorted(csv.DictReader(fh), key=lambda r: float(r["gross"]), reverse=True)[:5]
titles = [r["title"] for r in rows]; gross = [float(r["gross"]) for r in rows]
pos = range(len(titles))
ax.barh(pos, gross); ax.set_yticks(pos); ax.set_yticklabels(titles)
ax.invert_yaxis()
ax.set_xlim(0, 560)
ax.set_title("Top five films by gross")
ax.set_xlabel("Gross (USD millions)"); ax.set_ylabel("Film")
""",
    faulty="""
import csv
with open("films.csv") as fh:                       # sorted by year, not gross
    rows = sorted(csv.DictReader(fh), key=lambda r: float(r["year"]), reverse=True)[:5]
titles = [r["title"] for r in rows]; gross = [float(r["gross"]) for r in rows]
pos = range(len(titles))
ax.barh(pos, gross); ax.set_yticks(pos); ax.set_yticklabels(titles)
ax.invert_yaxis()
ax.set_xlim(0, 560)
ax.set_title("Top five films by gross")
ax.set_xlabel("Gross (USD millions)"); ax.set_ylabel("Film")
""",
    family="wrong_data",
    evidence="the five films shown are the five most recent by year (Noon "
             "Eclipse, Gullwing, Midnight Freight, Iron Harvest, Paper "
             "Lanterns), not the five highest-grossing; The Long Thaw (478) "
             "and Starfall (412) are missing",
)

SPECS["ho-log-decay"] = dict(
    instructions=(
        "Using matplotlib, plot the radioactive decay curve N(t) = 1000 * "
        "0.5**(t/8) for t from 0 to 80 in steps of 2, with the y axis on a "
        "LOGARITHMIC scale. Circular markers, x axis labeled \"Time (days)\", "
        "y axis labeled \"Activity (counts)\", title exactly \"Decay of sample "
        "X\". Save the figure as figure.png."),
    correct="""
t = np.arange(0, 82, 2)
ax.plot(t, 1000 * 0.5 ** (t / 8), marker="o", markersize=3)
ax.set_yscale("log")
ax.set_title("Decay of sample X")
ax.set_xlabel("Time (days)"); ax.set_ylabel("Activity (counts)")
""",
    faulty="""
t = np.arange(0, 82, 2)
ax.plot(t, 1000 * 0.5 ** (t / 8), marker="o", markersize=3)   # linear y axis
ax.set_title("Decay of sample X")
ax.set_xlabel("Time (days)"); ax.set_ylabel("Activity (counts)")
""",
    family="wrong_chart",
    evidence="the y axis is linear although the task requires a logarithmic "
             "scale; the curve hugs zero after t=40 instead of falling as a "
             "straight line",
)

SPECS["ho-subplot-pair"] = dict(
    instructions=(
        "Using matplotlib, make a figure with two SIDE-BY-SIDE panels (a 1x2 "
        "grid) sharing the y axis. Left panel: line of y = x**2 for x 0..10 "
        "titled \"Quadratic\". Right panel: line of y = 2**x for x 0..10 titled "
        "\"Exponential\". Label each panel's x axis \"x\" and the shared y axis "
        "\"y\". Save the figure as figure.png."),
    figure="fig, axes = plt.subplots(1, 2, sharey=True, figsize=(9, 4))",
    correct="""
x = np.arange(0, 11)
axes[0].plot(x, x**2); axes[0].set_title("Quadratic"); axes[0].set_xlabel("x")
axes[1].plot(x, 2.0**x); axes[1].set_title("Exponential"); axes[1].set_xlabel("x")
axes[0].set_ylabel("y")
""",
    faulty_figure="fig, axes = plt.subplots(2, 1, sharey=True, figsize=(6, 7))",
    faulty="""
x = np.arange(0, 11)
axes[0].plot(x, x**2); axes[0].set_title("Quadratic"); axes[0].set_xlabel("x")
axes[1].plot(x, 2.0**x); axes[1].set_title("Exponential"); axes[1].set_xlabel("x")
axes[0].set_ylabel("y")
""",
    family="wrong_chart",
    evidence="the panels are stacked vertically (a 2x1 grid) although the "
             "task requires two side-by-side panels in a 1x2 grid",
)

SPECS["ho-scatter-styled"] = dict(
    instructions=(
        "Using matplotlib, draw a scatter plot of reaction time against caffeine "
        "dose for these nine measurements: doses 0, 25, 50, 75, 100, 125, 150, "
        "175, 200 mg with reaction times 310, 300, 288, 279, 265, 262, 258, "
        "251, 249 ms. Use SQUARE red markers. X axis labeled \"Caffeine dose "
        "(mg)\", y axis labeled \"Reaction time (ms)\", title exactly "
        "\"Reaction time vs caffeine dose\". Save the figure as figure.png."),
    correct="""
doses = [0, 25, 50, 75, 100, 125, 150, 175, 200]
times = [310, 300, 288, 279, 265, 262, 258, 251, 249]
ax.scatter(doses, times, marker="s", color="red")
ax.set_title("Reaction time vs caffeine dose")
ax.set_xlabel("Caffeine dose (mg)"); ax.set_ylabel("Reaction time (ms)")
""",
    faulty="""
doses = [0, 25, 50, 75, 100, 125, 150, 175, 200]
times = [310, 300, 288, 279, 265, 262, 258, 251, 249]
ax.scatter(doses, times)                    # default round blue markers
ax.set_title("Reaction time vs caffeine dose")
ax.set_xlabel("Caffeine dose (mg)"); ax.set_ylabel("Reaction time (ms)")
""",
    family="wrong_chart",
    evidence="the markers are the default round blue points although the task "
             "requires square red markers",
)

SPECS["ho-hist-bins"] = dict(
    instructions=(
        "Using matplotlib, draw a histogram of 200 quality scores with exactly "
        "20 bins. Generate the scores as numpy.random.default_rng(7).normal(70, "
        "12, 200). Title exactly \"Distribution of quality scores\", x axis "
        "labeled \"Score\", y axis labeled \"Count\". Save the figure as "
        "figure.png."),
    correct="""
scores = np.random.default_rng(7).normal(70, 12, 200)
ax.hist(scores, bins=20)
ax.set_title("Distribution of quality scores")
ax.set_xlabel("Score"); ax.set_ylabel("Count")
""",
    faulty="""
scores = np.random.default_rng(7).normal(70, 12, 200)
ax.hist(scores, bins=20)
ax.set_title("Quality scores")             # wrong exact title text
ax.set_xlabel("Score"); ax.set_ylabel("Count")
""",
    family="wrong_chart",
    evidence="the title reads \"Quality scores\" although the task requires "
             "the exact text \"Distribution of quality scores\"",
)

SPECS["ho-hourly-ticks"] = dict(
    instructions=(
        "Using matplotlib, draw a line chart of server load for one day: 24 "
        "hourly samples 32, 30, 28, 27, 26, 28, 35, 48, 62, 70, 74, 76, 78, "
        "77, 75, 72, 70, 66, 58, 50, 45, 40, 36, 34 (percent, hours 00:00 to "
        "23:00). Show every hour label 00:00 through 23:00 on the x axis, "
        "rotated so neighbouring labels do not overlap and every label is "
        "readable. Y axis from 0 to 100 labeled \"Load (%)\", x axis labeled "
        "\"Hour\", title exactly \"Server load by hour\". Save the figure as "
        "figure.png."),
    figure="fig, ax = plt.subplots(figsize=(12, 4.5))",
    correct="""
load = [32, 30, 28, 27, 26, 28, 35, 48, 62, 70, 74, 76, 78, 77, 75, 72, 70,
        66, 58, 50, 45, 40, 36, 34]
hours = [f"{h:02d}:00" for h in range(24)]
ax.plot(hours, load, marker="o", markersize=3)
ax.set_xticks(range(24))
ax.set_xticklabels(hours, rotation=45, ha="right", rotation_mode="anchor")
ax.set_ylim(0, 100)
ax.set_title("Server load by hour")
ax.set_xlabel("Hour"); ax.set_ylabel("Load (%)")
""",
    faulty_figure="fig, ax = plt.subplots(figsize=(5, 4.5))",
    faulty="""
load = [32, 30, 28, 27, 26, 28, 35, 48, 62, 70, 74, 76, 78, 77, 75, 72, 70,
        66, 58, 50, 45, 40, 36, 34]
hours = [f"{h:02d}:00" for h in range(24)]
ax.plot(hours, load, marker="o", markersize=3)
ax.set_xticks(range(24))
ax.set_xticklabels(hours)                  # horizontal, on a narrow canvas
ax.set_ylim(0, 100)
ax.set_title("Server load by hour")
ax.set_xlabel("Hour"); ax.set_ylabel("Load (%)")
""",
    # Verified label (see labels.json): wrong_chart (rotation explicitly
    # requested, drawn horizontal) AND hard_to_read (labels merge into an
    # unreadable strip); the builder writes hard_to_read here and the
    # refinement pass in labels.json adds wrong_chart.
    family="hard_to_read",
    evidence="the 24 unrotated hour labels collide on the narrow canvas and "
             "merge into an unreadable strip along the x axis",
)

SPECS["ho-annotated-peak"] = dict(
    instructions=(
        "Using matplotlib, draw a line chart of weekly signups: 40, 55, 90, "
        "170, 240, 210, 150, 120 for weeks 1-8, with circular markers. "
        "Annotate the peak point with the text \"Launch week\" placed so it "
        "does not touch or cover the line. X axis labeled \"Week\", y axis "
        "from 0 labeled \"Signups\", title exactly \"Weekly signups\". Save "
        "the figure as figure.png."),
    correct="""
weeks = list(range(1, 9)); signups = [40, 55, 90, 170, 240, 210, 150, 120]
ax.plot(weeks, signups, marker="o")
ax.annotate("Launch week", xy=(5, 240), xytext=(6.4, 252),
            arrowprops=dict(arrowstyle="->"))
ax.set_ylim(0, 275)
ax.set_title("Weekly signups")
ax.set_xlabel("Week"); ax.set_ylabel("Signups")
""",
    faulty="""
weeks = list(range(1, 9)); signups = [40, 55, 90, 170, 240, 210, 150, 120]
ax.plot(weeks, signups, marker="o")
ax.annotate("Launch week", xy=(5, 240), xytext=(4.1, 195))  # box sits on the line
ax.set_ylim(0, 275)
ax.set_title("Weekly signups")
ax.set_xlabel("Week"); ax.set_ylabel("Signups")
""",
    family="hard_to_read",
    evidence="the annotation text \"Launch week\" is drawn directly on top of "
             "the rising segment of the line, covering the data between weeks "
             "4 and 6",
)

SPECS["ho-contrast-series"] = dict(
    instructions=(
        "Using matplotlib, draw a two-series line chart of monthly visitors for "
        "sites Alpha and Beta over Jan-Jun. Alpha: 120, 135, 150, 160, 172, "
        "185. Beta: 90, 98, 110, 125, 131, 140. Draw each series in a colour "
        "clearly distinguishable from the white background and from the other "
        "series, with a legend naming both. X axis labeled \"Month\", y axis "
        "from 0 labeled \"Visitors (thousands)\", title exactly \"Monthly "
        "visitors\". Save the figure as figure.png."),
    correct="""
months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
ax.plot(months, [120, 135, 150, 160, 172, 185], color="tab:blue", label="Alpha")
ax.plot(months, [90, 98, 110, 125, 131, 140], color="tab:red", label="Beta")
ax.legend(); ax.set_ylim(0, 200)
ax.set_title("Monthly visitors")
ax.set_xlabel("Month"); ax.set_ylabel("Visitors (thousands)")
""",
    faulty="""
months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
ax.plot(months, [120, 135, 150, 160, 172, 185], color="tab:blue", label="Alpha")
ax.plot(months, [90, 98, 110, 125, 131, 140], color="#fdfdf0", label="Beta")
ax.legend(); ax.set_ylim(0, 200)          # Beta nearly white on white
ax.set_title("Monthly visitors")
ax.set_xlabel("Month"); ax.set_ylabel("Visitors (thousands)")
""",
    family="hard_to_read",
    evidence="the Beta series is drawn in a near-white colour (#fdfdf0) on "
             "the white background and is effectively invisible",
)

SPECS["ho-clipped-xlabel"] = dict(
    instructions=(
        "Using matplotlib, draw a bar chart of items recycled by material: "
        "Glass 340, Paper 510, Plastic 425, Metal 280. Bars in the given "
        "order, y axis from 0 labeled \"Items recycled\", x axis labeled "
        "\"Material category\", title exactly \"Recycling by material\". All "
        "text must be fully visible in the saved image. Save the figure as "
        "figure.png."),
    correct="""
ax.bar(["Glass", "Paper", "Plastic", "Metal"], [340, 510, 425, 280])
ax.set_ylim(0, 560)
ax.set_title("Recycling by material")
ax.set_xlabel("Material category"); ax.set_ylabel("Items recycled")
fig.tight_layout()
""",
    faulty="""
ax.bar(["Glass", "Paper", "Plastic", "Metal"], [340, 510, 425, 280])
ax.set_ylim(0, 560)
ax.set_title("Recycling by material")
ax.set_xlabel("Material category"); ax.set_ylabel("Items recycled")
fig.subplots_adjust(bottom=0.06)           # x label half outside the canvas
""",
    family="hard_to_read",
    evidence="the x axis label \"Material category\" is cut in half by the "
             "bottom edge of the image",
    no_tight=True,
)

for _spec_id, _spec in SPECS.items():
    _spec.setdefault("inputs", {})

CRASH_RUNS = {
    "ho-crash-syntax": dict(
        instructions=(
            "Using matplotlib, draw a pie chart of budget shares: Rent 40, "
            "Food 25, Transit 15, Other 20 (percent), with each wedge "
            "labelled. Title exactly \"Budget shares\". Save the figure as "
            "figure.png."),
        commands=[
            ("python -c \"import matplotlib.pyplot as plt; sizes=[40,25,15,20; "
             "plt.pie(sizes)\"",
             1, "SyntaxError: closing parenthesis ']' does not match '['"),
            ("python plot.py", 1,
             "  File \"plot.py\", line 2\n    labels=['Rent','Food','Transit',"
             "'Other'\nSyntaxError: '[' was never closed"),
        ],
        exit="LimitsExceeded",
    ),
    "ho-crash-badimport": dict(
        instructions=(
            "Using matplotlib, draw a line chart of temperature readings 18, "
            "21, 25, 24, 20 for days Mon-Fri, with circular markers. Title "
            "exactly \"Temperatures this week\". Save the figure as "
            "figure.png."),
        commands=[
            ("python -c \"import plotly.express as px\"", 1,
             "ModuleNotFoundError: No module named 'plotly'"),
            ("pip install plotly", 1,
             "ERROR: No network access in this environment"),
            ("python -c \"import plotly.express as px\"", 1,
             "ModuleNotFoundError: No module named 'plotly'"),
        ],
        exit="LimitsExceeded",
    ),
}


def _render(spec: dict, code: str, figure_line: str, out: Path) -> str:
    """Execute one variant's plotting code; returns the full script text."""
    script = textwrap.dedent(f"""\
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        {figure_line}
        """) + textwrap.dedent(code).strip() + (
        "\n" + ("" if spec.get("no_tight") else "fig.tight_layout()\n")
        + 'fig.savefig("figure.png", dpi=100)\n')
    namespace: dict = {}
    import os
    cwd = os.getcwd()
    # Inputs are visible by bare filename in the agent's working directory;
    # mirror that for the render, then remove the bare copies (the canonical
    # copies live under inputs/).
    bare = []
    for name, text in spec.get("inputs", {}).items():
        (out / name).write_text(text)
        bare.append(out / name)
    os.chdir(out)
    try:
        exec(compile(script, "plot.py", "exec"), namespace)  # noqa: S102
    finally:
        os.chdir(cwd)
        for path in bare:
            path.unlink()
    return script


def _write_run(run_id: str, instructions: str, inputs: dict[str, str],
               script: str | None, commands=None, exit_status="Submitted"):
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    input_records = []
    if inputs:
        (run_dir / "inputs").mkdir(exist_ok=True)
        for name, text in inputs.items():
            (run_dir / "inputs" / name).write_text(text)
            input_records.append(
                {"name": name, "path": f"experiments/holdout/runs/{run_id}/inputs/{name}"})
    messages = [
        {"role": "system", "content":
            "You are a helpful assistant that can interact with a computer."},
        {"role": "user", "content": f"Please solve this issue:\n{instructions}"},
    ]
    if script is not None:
        messages += [
            {"role": "assistant", "content": "I will write plot.py and run it.",
             "tool_calls": [{"id": "call1", "type": "function", "function": {
                 "name": "bash", "arguments": json.dumps(
                     {"command": f"cat > plot.py <<'PY'\n{script}PY\npython plot.py"})}}]},
            {"role": "tool", "tool_call_id": "call1",
             "content": json.dumps({"returncode": 0, "output": ""})},
        ]
    for index, (cmd, returncode, output) in enumerate(commands or []):
        messages += [
            {"role": "assistant", "content": "",
             "tool_calls": [{"id": f"call{index + 2}", "type": "function",
                             "function": {"name": "bash",
                                          "arguments": json.dumps({"command": cmd})}}]},
            {"role": "tool", "tool_call_id": f"call{index + 2}",
             "content": json.dumps({"returncode": returncode, "output": output})},
        ]
    messages.append({"role": "exit", "content": exit_status})
    (run_dir / "result.json").write_text(json.dumps({
        "run_id": run_id, "task_id": run_id,
        "task": {"instructions": instructions, "inputs": input_records},
        "trajectory": {"messages": messages, "trajectory_format": "synthetic-holdout"},
    }, indent=1))


def main() -> None:
    labels = []
    for spec_id, spec in SPECS.items():
        for variant in ("ok", "bad"):
            run_id = f"{spec_id}__{variant}"
            run_dir = RUNS / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            if spec["inputs"]:
                (run_dir / "inputs").mkdir(exist_ok=True)
                for name, text in spec["inputs"].items():
                    (run_dir / "inputs" / name).write_text(text)
            figure_line = (spec.get("figure", "fig, ax = plt.subplots(figsize=(8, 5))")
                           if variant == "ok"
                           else spec.get("faulty_figure",
                                         spec.get("figure",
                                                  "fig, ax = plt.subplots(figsize=(8, 5))")))
            code = spec["correct"] if variant == "ok" else spec["faulty"]
            script = _render(spec, code, figure_line, run_dir)
            _write_run(run_id, spec["instructions"], spec["inputs"], script)
            errors = ([] if variant == "ok"
                      else [{"family": spec["family"], "evidence": spec["evidence"]}])
            labels.append({"run_id": run_id, "errors": errors})
    for run_id, crash in CRASH_RUNS.items():
        _write_run(run_id, crash["instructions"], {}, None,
                   commands=crash["commands"], exit_status=crash["exit"])
        labels.append({"run_id": run_id, "errors": [{
            "family": "execution_failure",
            "evidence": "no figure.png was produced; the trajectory ends with "
                        f"{crash['exit']} after repeated failing commands"}]})
    (HERE / "labels.json").write_text(json.dumps({"labels": labels}, indent=2) + "\n")
    print(f"built {len(labels)} holdout runs under {RUNS}")


if __name__ == "__main__":
    main()
