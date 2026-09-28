#!/bin/bash
# Reference solution: writes plot.py to disk, then executes it, because the
# task requires a re-runnable script and the verifier re-executes it.
set -euo pipefail

cat > /app/plot.py <<'PY'
"""Request-weighted mean latency per service, data inline in the task."""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# service -> ((requests_a, latency_a), (requests_b, latency_b))
REGIONS = {
    "auth": ((100, 120.0), (300, 80.0)),
    "search": ((250, 60.0), (250, 100.0)),
    "checkout": ((50, 200.0), (450, 40.0)),
    "media": ((400, 150.0), (100, 50.0)),
}
SERVICES = ["auth", "search", "checkout", "media"]     # fixed left-to-right order

weighted = {}
for service in SERVICES:
    (na, la), (nb, lb) = REGIONS[service]
    weighted[service] = (na * la + nb * lb) / (na + nb)

values = [weighted[service] for service in SERVICES]

fig, ax = plt.subplots(figsize=(7, 4.5))
bars = ax.bar(SERVICES, values, color="#4C78A8")
ax.bar_label(bars, fmt="%.1f")
ax.set_ylim(0, max(values) * 1.2)
ax.set_title("Request-weighted mean latency by service")
ax.set_xlabel("Service")
ax.set_ylabel("Latency (ms)")
fig.tight_layout()
fig.savefig("figure.png", dpi=100)

with open("plotted_values.json", "w") as handle:
    json.dump(weighted, handle, indent=2)
PY

cd /app && python plot.py
