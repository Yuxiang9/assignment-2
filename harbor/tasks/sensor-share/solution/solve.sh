#!/bin/bash
# Reference solution: writes plot.py to disk, then executes it, because the
# task requires a re-runnable script and the verifier re-executes it.
set -euo pipefail

cat > /app/plot.py <<'PY'
"""Each site's percentage share of all readings, from readings.csv."""
import csv
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sums: dict[str, float] = {}
with open("readings.csv", newline="") as handle:
    for row in csv.DictReader(handle):
        sums[row["site"]] = sums.get(row["site"], 0.0) + float(row["reading"])

total = sum(sums.values())
sites = sorted(sums)                                   # alphabetical
shares = [sums[site] / total * 100.0 for site in sites]

fig, ax = plt.subplots(figsize=(7, 4.5))
positions = range(len(sites))
ax.barh(positions, shares, color="#4C78A8")
ax.set_yticks(positions)
ax.set_yticklabels(sites)
ax.invert_yaxis()                                      # Alder at the top
ax.set_xlim(0, max(shares) * 1.3)                      # starts at zero
ax.set_title("Share of readings by site")
ax.set_xlabel("Share of total readings (%)")
ax.set_ylabel("Site")
for position, share in zip(positions, shares):
    ax.text(share + 0.4, position, f"{share:.1f}%", va="center")
fig.tight_layout()
fig.savefig("figure.png", dpi=100)

with open("plotted_values.json", "w") as handle:
    json.dump(dict(zip(sites, shares)), handle, indent=2)
PY

cd /app && python plot.py
