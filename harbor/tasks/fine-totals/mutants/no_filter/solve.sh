#!/bin/bash
# MUTANT (must score 0): forgets step 1 of the instructions and sums every
# row, waived or not. A plausible dropped-clause agent error: the totals
# become {Central: 77.5, Eastside: 55.75, Harborview: 42.5, Northgate: 79.0}
# and even the descending bar order changes (Northgate first). The verifier's
# hand-derived sidecar literals reject it.
set -euo pipefail

cat > /app/plot.py <<'PY'
"""Total fines per branch, from fines.csv (missing the waived filter)."""
import csv
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

totals: dict[str, float] = {}
with open("fines.csv", newline="") as handle:
    for row in csv.DictReader(handle):
        totals[row["branch"]] = totals.get(row["branch"], 0.0) + float(row["amount"])

branches = sorted(totals, key=lambda branch: totals[branch], reverse=True)
values = [totals[branch] for branch in branches]

fig, ax = plt.subplots(figsize=(7, 4.5))
ax.bar(branches, values, color="#4C78A8")
ax.set_title("Collected fines by branch")
ax.set_xlabel("Branch")
ax.set_ylabel("Fines collected (USD)")
ax.set_ylim(0, max(values) * 1.15)
fig.tight_layout()
fig.savefig("figure.png", dpi=100)

with open("plotted_values.json", "w") as handle:
    json.dump({branch: totals[branch] for branch in branches}, handle, indent=2)
PY

cd /app && python plot.py
