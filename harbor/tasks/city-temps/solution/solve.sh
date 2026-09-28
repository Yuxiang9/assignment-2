#!/bin/bash
# Reference solution: writes plot.py to disk, then executes it, because the
# task requires a re-runnable script and the verifier re-executes it.
set -euo pipefail

cat > /app/plot.py <<'PY'
"""Monthly mean temperature for six cities, data inline in the task."""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
CITIES = {
    "Aluna": [2, 3, 7, 12, 17, 21, 24, 23, 19, 13, 7, 3],
    "Brinport": [-5, -3, 2, 8, 14, 19, 22, 21, 15, 8, 1, -4],
    "Calder": [10, 11, 13, 16, 19, 23, 26, 26, 23, 18, 13, 10],
    "Dunmore": [16, 16, 17, 18, 20, 22, 24, 25, 24, 21, 18, 16],
    "Eastwick": [-12, -10, -4, 3, 10, 16, 19, 17, 11, 4, -4, -10],
    "Farrow": [21, 22, 22, 23, 23, 24, 25, 25, 24, 23, 22, 21],
}
COLORS = {
    "Aluna": "tab:blue",
    "Brinport": "tab:orange",
    "Calder": "tab:green",
    "Dunmore": "tab:red",
    "Eastwick": "tab:purple",
    "Farrow": "tab:brown",
}

fig, ax = plt.subplots(figsize=(11, 6))
for city, temperatures in CITIES.items():
    ax.plot(MONTHS, temperatures, marker="o", color=COLORS[city], label=city)
ax.set_xticks(range(len(MONTHS)))
ax.set_xticklabels(MONTHS)
ax.set_title("Monthly mean temperature by city")
ax.set_xlabel("Month")
ax.set_ylabel("Temperature (deg C)")
ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5))
fig.tight_layout()
fig.savefig("figure.png", dpi=100)

with open("plotted_values.json", "w") as handle:
    json.dump(CITIES, handle, indent=2)
PY

cd /app && python plot.py
