r"""Project 12 | CP6 Step 2: verify real batch inference against Project 9.

Usage (PowerShell, from the Project 12 root):
    .\.venv\Scripts\python.exe .\Project12_CP6_live_batch_check.py

Read-only validation. Requires the adjacent Project 9 source project and the
local MLflow model registry created during CP4. No server, model updates,
registrations, retraining, network calls, or paid APIs.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PROJECT_ROOT.parent / "09_ai_attrition_prediction"
sys.path.insert(0, str(PROJECT_ROOT / "src"))

MODEL_NAME = "p09-attrition-gb"
MODEL_VERSION = "1"
TOLERANCE = 1e-8


def verify(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def build_payloads() -> tuple[list[dict[str, Any]], pd.DataFrame, float]:
    from mlops_platform.schemas import FEATURE_NAMES

    metadata_path = SOURCE_ROOT / "artifacts" / "model_metadata.json"
    raw_path = SOURCE_ROOT / "data" / "raw" / "employee_attrition_snapshots_synthetic.csv"
    frozen_path = SOURCE_ROOT / "outputs" / "final_test_predictions.csv"
    for path in (metadata_path, raw_path, frozen_path):
        verify(path.is_file(), f"Project 9 source file not found: {path}")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    features = list(metadata["feature_list"])
    verify(tuple(features) == FEATURE_NAMES, "API model features/order changed from Project 9")
    verify(len(features) == 19, "Unexpected source feature count")
    threshold = float(metadata["operating_threshold"])
    verify(threshold == 0.125, "Operating threshold must remain 0.125")

    data = pd.read_csv(raw_path, parse_dates=["snapshot_date"])
    frozen = pd.read_csv(frozen_path, parse_dates=["snapshot_date"])
    keys = ["employee_id", "snapshot_date"]
    verify(len(frozen) == 507, "Expected exactly 507 frozen Project 9 test records")
    verify(not frozen.duplicated(keys).any(), "Frozen predictions have duplicate row identifiers")
    verify(not data.duplicated(keys).any(), "Original dataset has duplicate row identifiers")
    verify(data[features].notna().all().all(), "Original dataset has missing model inputs")

    # Left-merge intentionally preserves Project 9's *saved prediction* row order.
    rows = frozen.merge(data, on=keys, how="left", validate="one_to_one", indicator=True, sort=False)
    verify(len(rows) == len(frozen), "Merge changed number of rows")
    verify(rows["_merge"].eq("both").all(), "Frozen prediction rows missing from raw dataset")
    verify((rows["actual_target"] == rows[metadata["target"]]).all(),
           "Original target labels differ from frozen test labels")
    verify((rows["operating_threshold"] == threshold).all(),
           "Frozen prediction thresholds differ from locked model threshold")
    verify((rows["predicted_class"] ==
            (rows["predicted_probability"] >= threshold).astype(int)).all(),
           "Frozen classifications disagree with locked threshold")

    categorical = {"department", "job_family", "job_level", "location", "employment_type"}
    integer_features = {feature for feature in features
                        if pd.api.types.is_integer_dtype(data[feature].dtype)}
    payloads: list[dict[str, Any]] = []
    for record in rows.to_dict(orient="records"):
        values: dict[str, Any] = {}
        for feature in features:
            value = record[feature]
            verify(not pd.isna(value), f"Missing input in test feature {feature}")
            if feature in categorical:
                values[feature] = str(value)
            elif feature in integer_features:
                values[feature] = int(value)
            else:
                values[feature] = float(value)
        payloads.append({"features": values})
    return payloads, rows, threshold


def check_predictions(predictions: list[dict[str, Any]],
                      expected: pd.DataFrame, threshold: float, label: str) -> float:
    verify(len(predictions) == len(expected), f"{label}: incorrect prediction count")
    max_difference = 0.0
    for index, (response, (_, frozen)) in enumerate(zip(predictions, expected.iterrows())):
        verify(set(response) == {"prediction", "probability", "model_name", "model_version"},
               f"{label}: unexpected output fields at row {index}")
        verify(response["model_name"] == MODEL_NAME and response["model_version"] == MODEL_VERSION,
               f"{label}: incorrect registry model identity at row {index}")
        probability = float(response["probability"])
        verify(math.isfinite(probability) and 0 <= probability <= 1,
               f"{label}: invalid probability at row {index}")
        difference = abs(probability - float(frozen["predicted_probability"]))
        max_difference = max(max_difference, difference)
        verify(difference <= TOLERANCE,
               f"{label}: probability mismatch at row {index}: {difference:.3g}")
        verify(response["prediction"] == int(frozen["predicted_class"]),
               f"{label}: classification mismatch at row {index}")
        verify(response["prediction"] == int(probability >= threshold),
               f"{label}: operating threshold mismatch at row {index}")
    return max_difference


def post_batch(client: TestClient, items: list[dict[str, Any]],
               *, expected_status: int = 200) -> dict[str, Any]:
    response = client.post("/predict/batch", json={"items": items})
    verify(response.status_code == expected_status,
           f"Expected HTTP {expected_status}; got {response.status_code}. "
           f"Response: {response.text[:500]}")
    return response.json()


def main() -> None:
    verify(Path.cwd().resolve() == PROJECT_ROOT.resolve(),
           "Run from the Project 12 repository root")
    verify((PROJECT_ROOT / "mlflow_tracking.db").is_file(),
           "Local MLflow registry missing (mlflow_tracking.db)")

    from mlops_platform.api.main import app
    from mlops_platform.schemas import MAX_BATCH_SIZE

    verify(MAX_BATCH_SIZE == 1000, "CP6 batch-size limit changed")
    payloads, expected, threshold = build_payloads()

    print("\nPROJECT 12 — CP6 LIVE BATCH INFERENCE CHECK")
    print("=" * 55)
    print("Model:", MODEL_NAME, "version", MODEL_VERSION)
    print("Frozen test records:", len(expected))
    print("Locked threshold:", threshold)
    print("Testing the real MLflow-backed FastAPI endpoint (no server needed).")

    with TestClient(app) as client:
        info = client.get("/model/info")
        verify(info.status_code == 200, "GET /model/info failed")
        verify(info.json() == {"model_name": MODEL_NAME, "model_version": MODEL_VERSION},
               "API configured model identity differs from CP2 lock")
        print("GET /model/info: PASS")

        response = post_batch(client, payloads)
        verify(response["count"] == 507, "Batch response count differs from 507")
        largest_difference = check_predictions(response["predictions"], expected,
                                              threshold, "All 507 test records")
        classes = [x["prediction"] for x in response["predictions"]]
        verify(classes.count(1) == 118 and classes.count(0) == 389,
               "Batch predicted class distribution differs from Project 9")
        print("POST /predict/batch (all 507 frozen test rows): PASS")
        print(f"  Max absolute probability difference: {largest_difference:.3g}")
        print("  Predicted positive/negative counts:", classes.count(1), "/", classes.count(0))

        # Check order using a reverse traversal where index-by-index equivalence matters.
        reversed_result = post_batch(client, list(reversed(payloads)))
        reversed_expected = expected.iloc[::-1]
        verify(reversed_result["count"] == 507, "Reversed batch count mismatch")
        difference_reversed = check_predictions(reversed_result["predictions"],
                                                reversed_expected, threshold,
                                                "Reverse-order batch")
        print("POST /predict/batch (reversed input order): PASS")
        print(f"  Max absolute probability difference: {difference_reversed:.3g}")

        # The exact upper limit must be accepted, beyond it must fail validation.
        at_limit = (payloads * 2)[:MAX_BATCH_SIZE]
        max_result = post_batch(client, at_limit)
        verify(max_result["count"] == MAX_BATCH_SIZE, "1000-row batch returned wrong count")
        print("POST /predict/batch (1000 records, inclusive limit): PASS")

        post_batch(client, at_limit + [payloads[0]], expected_status=422)
        print("POST /predict/batch (1001 records): PASS (HTTP 422)")
        post_batch(client, [], expected_status=422)
        print("POST /predict/batch (empty batch): PASS (HTTP 422)")

        bad = dict(payloads[1]["features"])
        bad["department"] = "Unknown Department"
        post_batch(client, [payloads[0], {"features": bad}], expected_status=422)
        print("POST /predict/batch (invalid second record): PASS (HTTP 422)")

        missing = dict(payloads[1]["features"])
        del missing["age"]
        post_batch(client, [payloads[0], {"features": missing}], expected_status=422)
        print("POST /predict/batch (missing second-row feature): PASS (HTTP 422)")

    print("\nRESULT: CP6 REAL BATCH INFERENCE AND PARITY PASSED")
    print("Validation was read-only: no training, registration, or promotion.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nRESULT: CP6 LIVE BATCH CHECK FAILED: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        raise SystemExit(1)
