"""Run a candidate validator on the fixed diagnostic subset and score it.

    uv run python -m experiments.harness --solution <module> --out <pred.json>
        [--manifest experiments/diagnostic_subset.json] [--diag-dir DIR]

Loads the manifest's runs with the released ``Run.load`` (original
artifact_root paths intact), calls the candidate module's ``validate``,
validates the ``PredictionFile`` schema, writes a matching subset label file
next to the predictions, and scores with the official scorer. Labels are
used here, in the harness, only; candidate code never sees them.

Failures are retried once; a run that still fails is reported and the
harness exits non-zero (a partial file is not a completed sweep).
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import time
from pathlib import Path

from validator.prediction import Prediction, PredictionFile
from validator.runner import Run
from workflow.evaluate import score

RELEASE = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solution", required=True)
    parser.add_argument("--manifest", type=Path,
                        default=RELEASE / "experiments/diagnostic_subset.json")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--diag-dir", default=None)
    arguments = parser.parse_args()

    if arguments.diag_dir:
        os.environ["HW2_DIAG_DIR"] = str(arguments.diag_dir)
    validate = importlib.import_module(arguments.solution).validate

    manifest = json.loads(arguments.manifest.read_text())
    label_sources = {
        "artifacts": {l["run_id"]: l for l in
                      json.loads((RELEASE / "seed_labels.json").read_text())["labels"]},
        "runs": {l["run_id"]: l for l in
                 json.loads((RELEASE / "labels.json").read_text())["labels"]},
    }

    runs, labels = [], []
    for entry in manifest["runs"]:
        root = entry["root"]
        runs.append(Run.load(RELEASE / root / entry["id"], RELEASE))
        labels.append(label_sources[root][entry["id"]])

    predictions: dict[str, Prediction] = {}
    failures: dict[str, str] = {}
    started = time.time()
    for attempt in range(2):
        pending = [r for r in runs if r.run_id not in predictions]
        if not pending:
            break
        for run in pending:
            try:
                errors = validate(run)
            except Exception as error:  # noqa: BLE001 - recorded, then retried
                failures[run.run_id] = f"{type(error).__name__}: {error}"
                print(f"ERROR {run.run_id}: {failures[run.run_id]}")
                continue
            failures.pop(run.run_id, None)
            predictions[run.run_id] = Prediction(run_id=run.run_id, errors=errors)
            print(f"  {run.run_id}: "
                  f"{[e.family.value for e in errors] or 'acceptable'}")

    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    ordered = [predictions[r.run_id] for r in runs if r.run_id in predictions]
    arguments.out.write_text(
        PredictionFile(predictions=ordered).model_dump_json(indent=2) + "\n")
    labels_path = arguments.out.with_name(arguments.out.stem + "_labels.json")
    labels_path.write_text(json.dumps({"labels": labels}, indent=2) + "\n")
    print(f"wrote {len(ordered)} predictions in {time.time() - started:.0f}s")

    if failures:
        raise SystemExit(f"{len(failures)} run(s) failed: {failures}")

    report = score(labels_path, arguments.out)
    scores_path = arguments.out.with_name(arguments.out.stem + "_scores.json")
    scores_path.write_text(json.dumps(report, indent=2) + "\n")
    for family in ("execution_failure", "wrong_data", "wrong_chart", "hard_to_read"):
        row = report[family]
        print(f"{family:20} MCC={row['mcc']:.4f}  TP={row['tp']} TN={row['tn']} "
              f"FP={row['fp']} FN={row['fn']}")
    print(f"{'macro_mcc':20} {report['macro_mcc']:.4f}")


if __name__ == "__main__":
    main()
