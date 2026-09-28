#!/bin/bash
# Reference solution: writes plot.py to disk, then executes it, because the
# task requires a re-runnable script and the verifier re-executes it.
set -euo pipefail

cat > /app/plot.py <<'PY'
"""Peak attendance per festival stage, data inline in the task."""
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
ax.set_xticklabels(names, rotation=45, ha="right", rotation_mode="anchor")
ax.set_ylim(0, max(values) * 1.1)
ax.set_title("Peak attendance by stage")
ax.set_xlabel("Stage")
ax.set_ylabel("Peak attendance")
fig.tight_layout()
fig.savefig("figure.png", dpi=100)

with open("plotted_values.json", "w") as handle:
    json.dump(dict(STAGES), handle, indent=2)
PY

cd /app && python plot.py
