r"""CP5 manual integration check: real MLflow registry model through FastAPI.

Run from the Project 12 repository root with its virtual environment:
    .\.venv\Scripts\python.exe .\Project12_CP5_live_inference_check.py

Read-only: no model training, registry writes, server, cloud, or API keys.
Requires neighboring Project 9 source repository and CP4 local MLflow database.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PROJECT_ROOT.parent / "09_ai_attrition_prediction"
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _features_for_row(
    original_data: pd.DataFrame,
    saved_prediction: pd.Series,
    feature_names: list[str],
    categorical_features: set[str],
) -> dict[str, str | int | float]:
    selected = original_data.loc[
        (original_data["employee_id"] == saved_prediction["employee_id"])
        & (original_data["snapshot_date"] == saved_prediction["snapshot_date"])
    ]
    _check(len(selected) == 1, "Test prediction must match exactly one source record")
    record = selected.iloc[0]
    payload: dict[str, str | int | float] = {}
    for feature in feature_names:
        value = record[feature]
        _check(not pd.isna(value), f"Unexpected missing source feature: {feature}")
        if feature in categorical_features:
            payload[feature] = str(value)
        elif pd.api.types.is_integer_dtype(original_data[feature].dtype):
            payload[feature] = int(value)
        else:
            payload[feature] = float(value)
    return payload


def main() -> None:
    _check(Path.cwd().resolve() == PROJECT_ROOT.resolve(),
           "Run this script from the Project 12 repository root")

    from mlops_platform.api.main import app
    from mlops_platform.schemas import FEATURE_NAMES

    source_metadata_file = SOURCE_ROOT / "artifacts" / "model_metadata.json"
    raw_dataset_file = (
        SOURCE_ROOT / "data" / "raw" / "employee_attrition_snapshots_synthetic.csv"
    )
    saved_predictions_file = SOURCE_ROOT / "outputs" / "final_test_predictions.csv"

    for file in (source_metadata_file, raw_dataset_file, saved_predictions_file):
        _check(file.is_file(), f"Missing source file: {file}")
    _check((PROJECT_ROOT / "mlflow_tracking.db").is_file(),
           "Local CP4 mlflow_tracking.db not found")

    metadata = json.loads(source_metadata_file.read_text(encoding="utf-8"))
    features = list(metadata["feature_list"])
    _check(tuple(features) == FEATURE_NAMES, "API feature order differs from source model")
    _check(len(features) == 19, "Expected exactly 19 model input features")
    threshold = float(metadata["operating_threshold"])
    _check(threshold == 0.125, "Locked operating threshold changed")

    categorical = {
        "department", "job_family", "job_level", "location", "employment_type"
    }
    data = pd.read_csv(raw_dataset_file, parse_dates=["snapshot_date"])
    saved = pd.read_csv(saved_predictions_file, parse_dates=["snapshot_date"])
    _check(len(saved) == 507, "Original Project 9 test set is not 507 rows")
    _check({0, 1}.issubset(set(saved["predicted_class"].astype(int))),
           "Original test predictions must contain both predicted classes")

    samples = [
        ("negative prediction", saved.loc[saved["predicted_class"] == 0].iloc[0]),
        ("positive prediction", saved.loc[saved["predicted_class"] == 1].iloc[0]),
    ]

    print("\nPROJECT 12 — CP5 REAL MLFLOW INFERENCE CHECK")
    print("=" * 55)
    print("Requests: in-process FastAPI TestClient (real MLflow model)")
    print("Registered model: p09-attrition-gb / version 1")
    print("Locked threshold:", threshold)

    with TestClient(app) as client:
        health = client.get("/health")
        _check(health.status_code == 200 and health.json() == {"status": "ok"},
               "GET /health failed")
        print("GET /health: PASS")

        info = client.get("/model/info")
        _check(info.status_code == 200, f"GET /model/info failed: {info.text}")
        _check(info.json() == {"model_name": "p09-attrition-gb", "model_version": "1"},
               "GET /model/info returned wrong model identity")
        print("GET /model/info: PASS")

        sample_payload = None
        for label, saved_row in samples:
            inputs = _features_for_row(data, saved_row, features, categorical)
            _check(list(inputs) == features, "Input feature ordering mismatch")
            response = client.post("/predict", json={"features": inputs})
            _check(response.status_code == 200,
                   f"POST /predict failed ({label}): HTTP {response.status_code}; "
                   f"response={response.text[:600]}")
            result = response.json()
            probability = float(result["probability"])
            expected_probability = float(saved_row["predicted_probability"])
            expected_class = int(saved_row["predicted_class"])
            difference = abs(probability - expected_probability)
            _check(math.isfinite(probability) and 0 <= probability <= 1,
                   f"Invalid predicted probability ({label})")
            _check(difference <= 1e-8,
                   f"Probability parity failed ({label}), difference={difference}")
            _check(result["prediction"] == expected_class,
                   f"Class parity failed ({label})")
            _check(result["prediction"] == int(probability >= threshold),
                   f"Classification threshold mismatch ({label})")
            _check(result["model_name"] == "p09-attrition-gb", "Wrong model name")
            _check(result["model_version"] == "1", "Wrong model version")
            print(f"POST /predict ({label}): PASS")
            print(f"  Probability: {probability:.12f}; expected: {expected_probability:.12f}")
            print(f"  Predicted class: {result['prediction']}; absolute difference: {difference:.3g}")
            if sample_payload is None:
                sample_payload = inputs

        assert sample_payload is not None
        for label, invalid in (
            ("missing feature", {k: v for k, v in sample_payload.items() if k != "age"}),
            ("unexpected feature", {**sample_payload, "employee_id": "SYNTHETIC"}),
            ("unknown category", {**sample_payload, "department": "Invalid"}),
        ):
            response = client.post("/predict", json={"features": invalid})
            _check(response.status_code == 422,
                   f"{label} should return HTTP 422, got {response.status_code}")
            print(f"POST /predict ({label}): PASS (HTTP 422)")

    print("\nRESULT: CP5 REAL MODEL INFERENCE AND VALIDATION PASSED")
    print("No files or registered model versions were changed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nRESULT: CP5 LIVE INFERENCE FAILED: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        sys.exit(1)
