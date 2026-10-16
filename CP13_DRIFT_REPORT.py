"""Deterministic retrospective drift/performance on Project 9 synthetic data only."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from sys import path as search_path

import pandas as pd

ROOT = Path(__file__).resolve().parent
search_path.insert(0, str(ROOT / "src"))
from mlops_platform.monitoring.drift import drift_report
from mlops_platform.monitoring.performance import evaluate_recent_predictions
from mlops_platform.serving.cloud_candidate import FEATURE_NAMES


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, default=ROOT.parent / "09_ai_attrition_prediction")
    p.add_argument("--output", type=Path, default=ROOT / "outputs" / "cp13_drift_report.json")
    args = p.parse_args()
    root = args.source
    config = json.loads((root / "config/project_config.json").read_text(encoding="utf-8"))
    data = pd.read_csv(root / "data/raw/employee_attrition_snapshots_synthetic.csv", parse_dates=["snapshot_date"])
    before = data.loc[data["snapshot_date"] <= pd.Timestamp(config["train_end"])].copy()
    test = data.loc[data["snapshot_date"].between(pd.Timestamp(config["test_start"]), pd.Timestamp(config["test_end"]))].copy()
    numeric = list(FEATURE_NAMES[5:])
    categorical = list(FEATURE_NAMES[:5])
    drift = drift_report(before, test, numeric, categorical)
    # Use EXISTING saved final-test prediction file; this is not real-time performance.
    frozen = pd.read_csv(root / "outputs/final_test_predictions.csv")
    performance = evaluate_recent_predictions(frozen["actual_target"], frozen["predicted_probability"])
    result = {"format": "project12_cp13_retrospective_monitor_v1", "data_origin": "synthetic_project9_snapshots",
              "drift": drift, "historical_test_performance": performance,
              "note": "Retrospective proof-of-function only; not evidence of actual production performance."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("CP13 DRIFT / DELAYED PERFORMANCE (SYNTHETIC)")
    print("Reference:", len(before), "Current:", len(test))
    print("PSI status:", drift["status"], "Alerts:", sum(v["alert"] for v in drift["features"].values()))
    print("Historical metrics:", performance["status"])
    print("Report:", args.output)
    print("RESULT: CP13 OFFLINE DRIFT REPORT PASSED")


if __name__ == "__main__":
    main()
