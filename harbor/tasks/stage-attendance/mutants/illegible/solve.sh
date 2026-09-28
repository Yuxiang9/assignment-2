#!/bin/bash
# MUTANT (must score 1.0): every number is right, the sidecar is right, the
# script re-runs, and every deterministically checkable design clause is
# satisfied -- the canvas is the required 14x6 inches, the tick labels are
# the full stage names, rotated 45 degrees and right-anchored, and all text
# lies inside the saved image. What is wrong is purely perceptual: every
# piece of text is set at 2pt, far too small for a person to read at any
# reasonable zoom. A verifier that checks files, values, sizes, and even
# matplotlib's artist tree waves this through; only perceptual judging (the
# VLM validator's hard_to_read family) can see what is wrong with it.
set -euo pipefail

cat > /app/plot.py <<'PY'
"""Peak attendance per festival stage (correct data, 2pt unreadable text)."""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

STAGES = [
    ("Whispering Pines Amphitheater", 4200),
    ("Golden Meadow Pavilion", 3100),
    ("Riverbend Acoustic Grove", 2650),
    ("Starlight Terrace", 5300),
    ("Thundering Falls Main Stage", 8900),
    ("Lantern District Bandshell", 1900),
    ("Cedar Hollow Sessions Tent", 2300),
    ("Aurora Fields Dance Dome", 6100),
    ("Harborlight Jazz Corner", 1450),
    ("Mossy Knoll Folk Circle", 990),
    ("Ironworks Underground Hall", 3750),
    ("Sunset Dunes Beach Stage", 4800),
]

names = [name for name, _ in STAGES]
values = [value for _, value in STAGES]

fig, ax = plt.subplots(figsize=(14, 6))
ax.bar(names, values, color="#4C78A8")
ax.set_xticks(range(len(names)))
ax.set_xticklabels(names, rotation=45, ha="right", rotation_mode="anchor",
                   fontsize=2)
ax.tick_params(axis="y", labelsize=2)
ax.set_ylim(0, max(values) * 1.1)
ax.set_title("Peak attendance by stage", fontsize=2)
ax.set_xlabel("Stage", fontsize=2)
ax.set_ylabel("Peak attendance", fontsize=2)
fig.tight_layout()
fig.savefig("figure.png", dpi=100)

with open("plotted_values.json", "w") as handle:
    json.dump(dict(STAGES), handle, indent=2)
PY

cd /app && python plot.py
