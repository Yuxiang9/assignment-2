"""Step-7 ablation: replay recorded first-stage findings three ways.

    uv run python experiments/arbitration_ablation.py <diag_dir> <pred_json>

Configurations, all built from the SAME recorded raw findings (so no fresh
model variation enters the comparison):

  A. direct      -- raw first-stage findings, deduplicated by family;
  B. mapped      -- A plus a deterministic subtype re-file: evidence whose
                    defect language names drawn ORDER moves to wrong_data;
                    title/label/legend/colormap/scale presence language
                    filed as wrong_data moves to wrong_chart; partial
                    clipping language filed as wrong_data/wrong_chart moves
                    to hard_to_read, except "entirely outside the image",
                    which stays wrong_chart (ASSIGNMENT.md rule);
  C. arbitrated  -- the model arbiter's recorded output (the shipped path).

Replaying recorded findings is an ablation, not an end-to-end score; the
selected complete validator is rerun before any finalization.
"""

from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workflow.evaluate import score  # noqa: E402

ORDER = re.compile(
    r"\border(?:ed|ing)?\b|\bsorted\b|\bsequence\b|\breversed\b|"
    r"\balphabetical|\bdescending\b|\bascending\b", re.IGNORECASE)
CHART_PRESENCE = re.compile(
    r"\btitle\b|\baxis label|\bx-?label|\by-?label|\blegend\b|"
    r"\bcolou?r ?bar\b|\bcolou?rmap\b|\bcmap\b|\baxis scale\b|"
    r"\blog(?:arithmic)? scale|\bprojection\b|\btick label", re.IGNORECASE)
CLIPPING = re.compile(
    r"\bclipp|\bcut off\b|\bcut in half\b|\bpartially (?:cut|hidden|outside)",
    re.IGNORECASE)
ENTIRELY_OUTSIDE = re.compile(
    r"entirely outside|completely outside|not (?:present|visible) in the "
    r"saved image", re.IGNORECASE)


def remap(family: str, evidence: str) -> str:
    if family == "wrong_chart" and ORDER.search(evidence) \
            and not CHART_PRESENCE.search(evidence):
        return "wrong_data"
    if family == "wrong_data" and CHART_PRESENCE.search(evidence) \
            and not ORDER.search(evidence):
        return "wrong_chart"
    if family in ("wrong_data", "wrong_chart") and CLIPPING.search(evidence) \
            and not ENTIRELY_OUTSIDE.search(evidence) \
            and not CHART_PRESENCE.search(evidence) and not ORDER.search(evidence):
        return "hard_to_read"
    return family


def dedup(pairs: list[tuple[str, str]]) -> list[dict]:
    seen: dict[str, str] = {}
    for family, evidence in pairs:
        seen.setdefault(family, evidence)
    return [{"family": f, "evidence": e} for f, e in seen.items()]


def main() -> None:
    diag_dir, pred_path = sys.argv[1], sys.argv[2]
    base = {p["run_id"]: p for p in
            json.load(open(pred_path))["predictions"]}
    configs: dict[str, dict] = {"direct": {}, "mapped": {}, "arbitrated": {}}
    for rid, pred in base.items():
        # default: keep the shipped prediction (covers execution failures
        # and runs with no diagnostics)
        for cfg in configs.values():
            cfg[rid] = pred["errors"]
    for path in glob.glob(f"{diag_dir}/*__validate__*.json"):
        rec = json.load(open(path))
        rid = rec["run_id"]
        raw = [(f, e) for f, e in rec["raw_findings"]]
        configs["direct"][rid] = dedup(raw)
        configs["mapped"][rid] = dedup([(remap(f, e), e) for f, e in raw])
        configs["arbitrated"][rid] = dedup([(f, e) for f, e in rec["final"]])

    labels_path = Path(pred_path).with_name(
        Path(pred_path).stem + "_labels.json")
    for name, cfg in configs.items():
        out = Path(diag_dir).parent / f"ablation_{name}.json"
        out.write_text(json.dumps({"predictions": [
            {"run_id": rid, "errors": errors}
            for rid, errors in sorted(cfg.items())]}, indent=1))
        report = score(labels_path, out)
        cells = "  ".join(
            f"{f[:2]}={report[f]['mcc']:+.3f}"
            for f in ("execution_failure", "wrong_data", "wrong_chart",
                      "hard_to_read"))
        print(f"{name:12} macro={report['macro_mcc']:+.4f}  {cells}")


if __name__ == "__main__":
    main()
