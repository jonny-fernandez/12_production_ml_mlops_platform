"""CP5 read-only regression tests for real FastAPI -> MLflow inference.

Save as tests/test_live_inference.py in Project 12.

Run from Project 12 root:
    .\\.venv\\Scripts\\python.exe -m pytest -p no:cacheprovider -q

The real-model integration tests skip when the local MLflow database is absent
(e.g. a clean CI runner). When a local registry exists, missing evidence, wrong
model versions, or prediction changes FAIL rather than silently skip.

No training, MLflow registration, model mutation, external API, or server startup.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from mlops_platform.api.main import app
from mlops_platform.schemas import FEATURE_NAMES

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "09_ai_attrition_prediction"
REGISTRY_DB = ROOT / "mlflow_tracking.db"
MODEL_NAME = "p09-attrition-gb"
MODEL_VERSION = "1"
THRESHOLD = 0.125
CATEGORICAL = {
    "department", "job_family", "job_level", "location", "employment_type"
}


def _payload(data: pd.DataFrame, saved_row: pd.Series) -> dict[str, object]:
    rows = data.loc[
        (data["employee_id"] == saved_row["employee_id"])
        & (data["snapshot_date"] == saved_row["snapshot_date"])
    ]
    assert len(rows) == 1, "Test prediction must identify exactly one source record"
    original = rows.iloc[0]
    result: dict[str, object] = {}
    for feature in FEATURE_NAMES:
        value = original[feature]
        assert pd.notna(value), f"Source feature is unexpectedly null: {feature}"
        if feature in CATEGORICAL:
            result[feature] = str(value)
        elif pd.api.types.is_integer_dtype(data[feature].dtype):
            result[feature] = int(value)
        else:
            result[feature] = float(value)
    return result


@pytest.fixture(scope="module")
def real_model_context():
    """Require verified local evidence; skip only if local registry is absent."""
    if not REGISTRY_DB.is_file():
        pytest.skip("CP5 integration requires local mlflow_tracking.db (absent in CI)")
    assert Path.cwd().resolve() == ROOT.resolve(), (
        "Run tests from the Project 12 repository root to select the intended MLflow DB"
    )

    metadata_path = SOURCE / "artifacts/model_metadata.json"
    dataset_path = SOURCE / "data/raw/employee_attrition_snapshots_synthetic.csv"
    predictions_path = SOURCE / "outputs/final_test_predictions.csv"
    for path in (metadata_path, dataset_path, predictions_path):
        assert path.is_file(), f"Local MLflow registry exists but required source evidence is missing: {path}"

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert tuple(metadata["feature_list"]) == FEATURE_NAMES
    assert len(FEATURE_NAMES) == 19
    assert float(metadata["operating_threshold"]) == THRESHOLD

    data = pd.read_csv(dataset_path, parse_dates=["snapshot_date"])
    saved = pd.read_csv(predictions_path, parse_dates=["snapshot_date"])
    assert len(saved) == 507, "Project 9 frozen final test should have 507 records"

    samples = {}
    for label in (0, 1):
        matching = saved.loc[saved["predicted_class"].astype(int) == label]
        assert not matching.empty, f"No frozen predictions for class {label}"
        example = matching.iloc[0]
        samples[label] = (example, _payload(data, example))

    with TestClient(app) as client:
        yield client, samples


def test_real_service_health_and_model_identity(real_model_context) -> None:
    client, _ = real_model_context
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    info = client.get("/model/info")
    assert info.status_code == 200
    assert info.json() == {"model_name": MODEL_NAME, "model_version": MODEL_VERSION}


@pytest.mark.parametrize("expected_class", [0, 1], ids=["negative", "positive"])
def test_real_registered_model_matches_frozen_predictions(real_model_context, expected_class: int) -> None:
    client, samples = real_model_context
    frozen_row, payload = samples[expected_class]
    response = client.post("/predict", json={"features": payload})
    assert response.status_code == 200, response.text
    actual = response.json()
    probability = float(actual["probability"])
    expected_probability = float(frozen_row["predicted_probability"])
    assert math.isfinite(probability) and 0.0 <= probability <= 1.0
    assert abs(probability - expected_probability) <= 1e-8
    assert actual["prediction"] == int(frozen_row["predicted_class"])
    assert actual["prediction"] == int(probability >= THRESHOLD)
    assert actual["model_name"] == MODEL_NAME
    assert actual["model_version"] == MODEL_VERSION


@pytest.mark.parametrize("invalid_kind", [
    "missing_feature", "extra_feature", "unknown_category", "numeric_string",
    "null_value", "invalid_ratio",
])
def test_real_api_rejects_invalid_payloads(real_model_context, invalid_kind: str) -> None:
    client, samples = real_model_context
    invalid = dict(samples[0][1])
    if invalid_kind == "missing_feature":
        invalid.pop("age")
    elif invalid_kind == "extra_feature":
        invalid["employee_id"] = "synthetic-id"
    elif invalid_kind == "unknown_category":
        invalid["department"] = "Invalid"
    elif invalid_kind == "numeric_string":
        invalid["age"] = "42"
    elif invalid_kind == "null_value":
        invalid["age"] = None
    elif invalid_kind == "invalid_ratio":
        invalid["remote_work_ratio"] = 2.0
    response = client.post("/predict", json={"features": invalid})
    assert response.status_code == 422, response.text


def test_real_registry_model_is_still_unpromoted(real_model_context) -> None:
    # Read-only check: do not assign aliases or update registered versions.
    from mlflow.tracking import MlflowClient

    client = MlflowClient(
        tracking_uri="sqlite:///mlflow_tracking.db",
        registry_uri="sqlite:///mlflow_tracking.db",
    )
    version = client.get_model_version(MODEL_NAME, MODEL_VERSION)
    assert version.status == "READY"
    assert version.tags["candidate_status"] == "candidate_not_promoted"
    assert float(version.tags["operating_threshold"]) == THRESHOLD
    registered = client.get_registered_model(MODEL_NAME)
    assert not registered.aliases, "CP5 must not attach production aliases"
