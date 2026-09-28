"""One-shot evaluation of a solution module on the reserved holdout suite."""
import importlib, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validator.prediction import Prediction, PredictionFile
from validator.runner import Run
from workflow.evaluate import score

RELEASE = Path(__file__).resolve().parents[1]
module_name, out_path = sys.argv[1], Path(sys.argv[2])
validate = importlib.import_module(module_name).validate
runs_dir = RELEASE / "experiments/holdout/runs"
runs = [Run.load(d, RELEASE) for d in sorted(runs_dir.iterdir())
        if (d / "result.json").exists()]
predictions, failures = {}, {}
start = time.time()
for attempt in range(2):
    for run in [r for r in runs if r.run_id not in predictions]:
        try:
            errors = validate(run)
        except Exception as e:
            failures[run.run_id] = f"{type(e).__name__}: {e}"; continue
        failures.pop(run.run_id, None)
        predictions[run.run_id] = Prediction(run_id=run.run_id, errors=errors)
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(PredictionFile(predictions=[predictions[r.run_id] for r in runs
    if r.run_id in predictions]).model_dump_json(indent=2) + "\n")
if failures:
    raise SystemExit(f"failures: {failures}")
report = score(RELEASE / "experiments/holdout/labels.json", out_path)
out_path.with_suffix(".scores.json").write_text(json.dumps(report, indent=2))
for f in ["execution_failure", "wrong_data", "wrong_chart", "hard_to_read"]:
    d = report[f]
    print(f"{f:20} MCC={d['mcc']:+.4f} TP{d['tp']} TN{d['tn']} FP{d['fp']} FN{d['fn']}")
print(f"{'macro':20} {report['macro_mcc']:+.4f}  ({module_name}, {time.time()-start:.0f}s)")
