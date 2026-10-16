r"""Project 12 / CP6: permanent read-only integration checks for real batch inference.

Install as ``tests/test_live_batch_inference.py`` in the Project 12 repository.
Run from repository root: .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider -q

Checks the registered MLflow model against Project 9's FROZEN 507 test-row
predictions, including ordering, the 1000-row boundary, and all-or-nothing
schema validation. No retraining, new registry versions, cloud calls or writes.

On CI runners with no local MLflow SQLite DB, integration cases are skipped.
If the local DB exists, missing source evidence or broken models FAIL tests.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from mlops_platform.api import main as api_module
from mlops_platform.schemas import FEATURE_NAMES, MAX_BATCH_SIZE

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT.parent / "09_ai_attrition_prediction"
DB_PATH = PROJECT_ROOT / "mlflow_tracking.db"
MODEL_NAME = "p09-attrition-gb"
MODEL_VERSION = "1"
THRESHOLD = 0.125
TOLERANCE = 1e-8
CATEGORICAL = {
    "department", "job_family", "job_level", "location", "employment_type"
}


@pytest.fixture(scope="module")
def frozen_cases() -> tuple[list[dict[str, Any]], pd.DataFrame]:
    """Recover rows in EXACT saved prediction order (not dataset order)."""
    if not DB_PATH.is_file():
        pytest.skip("Local MLflow registry absent; CI does not provision a model")

    assert Path.cwd().resolve() == PROJECT_ROOT.resolve(), (
        "Run pytest from Project 12 root so relative SQLite URIs resolve correctly"
    )
    evidence = {
        "metadata": SOURCE_ROOT / "artifacts/model_metadata.json",
        "dataset": SOURCE_ROOT / "data/raw/employee_attrition_snapshots_synthetic.csv",
        "frozen": SOURCE_ROOT / "outputs/final_test_predictions.csv",
    }
    for kind, path in evidence.items():
        assert path.is_file(), f"Local registry exists but {kind} evidence is missing: {path}"

    metadata = json.loads(evidence["metadata"].read_text(encoding="utf-8"))
    assert tuple(metadata["feature_list"]) == FEATURE_NAMES
    assert len(FEATURE_NAMES) == 19
    assert float(metadata["operating_threshold"]) == THRESHOLD
    assert MAX_BATCH_SIZE == 1000

    raw = pd.read_csv(evidence["dataset"], parse_dates=["snapshot_date"])
    frozen = pd.read_csv(evidence["frozen"], parse_dates=["snapshot_date"])
    keys = ["employee_id", "snapshot_date"]
    assert len(frozen) == 507
    assert not frozen.duplicated(keys).any()
    assert not raw.duplicated(keys).any()

    # Left merge + sort=False: row order must match frozen predictions, not raw CSV.
    joined = frozen.merge(
        raw, on=keys, how="left", validate="one_to_one", sort=False, indicator=True
    )
    assert len(joined) == len(frozen)
    assert joined["_merge"].eq("both").all()
    assert joined["actual_target"].eq(joined[metadata["target"]]).all()
    assert joined["operating_threshold"].eq(THRESHOLD).all()
    assert joined["predicted_class"].eq(
        (joined["predicted_probability"] >= THRESHOLD).astype(int)
    ).all()

    integer_features = {
        feature for feature in FEATURE_NAMES
        if pd.api.types.is_integer_dtype(raw[feature].dtype)
    }
    items: list[dict[str, Any]] = []
    for record in joined.to_dict(orient="records"):
        features: dict[str, Any] = {}
        for feature in FEATURE_NAMES:
            value = record[feature]
            assert pd.notna(value), f"Unexpected null in frozen record: {feature}"
            if feature in CATEGORICAL:
                features[feature] = str(value)
            elif feature in integer_features:
                features[feature] = int(value)
            else:
                features[feature] = float(value)
        items.append({"features": features})
    return items, joined


@pytest.fixture(scope="module")
def client(frozen_cases):
    # Uses TestClient, not a live server or cloud service.
    with TestClient(api_module.app) as test_client:
        yield test_client


def _post(client: TestClient, items: list[dict[str, Any]], status: int = 200):
    response = client.post("/predict/batch", json={"items": items})
    assert response.status_code == status, response.text[:500]
    return response.json()


def _compare(predictions: list[dict[str, Any]], expected: pd.DataFrame) -> float:
    assert len(predictions) == len(expected)
    largest = 0.0
    for index, (prediction, (_, record)) in enumerate(zip(predictions, expected.iterrows())):
        assert set(prediction) == {
            "prediction", "probability", "model_name", "model_version"
        }, index
        assert prediction["model_name"] == MODEL_NAME
        assert prediction["model_version"] == MODEL_VERSION
        probability = float(prediction["probability"])
        assert math.isfinite(probability) and 0 <= probability <= 1
        difference = abs(probability - float(record["predicted_probability"]))
        largest = max(largest, difference)
        assert difference <= TOLERANCE, (index, difference)
        assert prediction["prediction"] == int(record["predicted_class"])
        assert prediction["prediction"] == int(probability >= THRESHOLD)
    return largest


def test_batch_model_identity_and_health(client: TestClient):
    assert client.get("/health").json() == {"status": "ok"}
    info = client.get("/model/info")
    assert info.status_code == 200
    assert info.json() == {"model_name": MODEL_NAME, "model_version": MODEL_VERSION}


def test_all_507_frozen_predictions_match(client: TestClient, frozen_cases):
    items, expected = frozen_cases
    response = _post(client, items)
    assert response["count"] == 507
    assert _compare(response["predictions"], expected) <= TOLERANCE
    assert sum(x["prediction"] for x in response["predictions"]) == 118


def test_reversing_input_reverses_predictions(client: TestClient, frozen_cases):
    items, expected = frozen_cases
    response = _post(client, list(reversed(items)))
    assert response["count"] == 507
    assert _compare(response["predictions"], expected.iloc[::-1]) <= TOLERANCE


@pytest.mark.parametrize("predicted_class", [0, 1], ids=["negative", "positive"])
def test_single_record_batch_matches_realtime(client: TestClient, frozen_cases, predicted_class: int):
    items, saved = frozen_cases
    index = next(
        i for i, x in enumerate(saved["predicted_class"])
        if int(x) == predicted_class
    )
    batch = _post(client, [items[index]])
    single = client.post("/predict", json=items[index])
    assert single.status_code == 200, single.text
    assert batch == {"count": 1, "predictions": [single.json()]}
    assert _compare(batch["predictions"], saved.iloc[[index]]) <= TOLERANCE


def test_exactly_1000_records_accepted(client: TestClient, frozen_cases):
    items, _ = frozen_cases
    at_limit = (items * 2)[:MAX_BATCH_SIZE]
    assert len(at_limit) == 1000
    batch = _post(client, at_limit)
    assert batch["count"] == 1000
    assert len(batch["predictions"]) == 1000


def test_1001_records_rejected(client: TestClient, frozen_cases):
    items, _ = frozen_cases
    assert _post(client, (items * 2)[:MAX_BATCH_SIZE + 1], 422)


def test_empty_batch_rejected(client: TestClient):
    assert _post(client, [], 422)


@pytest.mark.parametrize("mutation", [
    "missing_feature",
    "extra_feature",
    "unknown_category",
    "numeric_string",
    "null_value",
    "bad_ratio",
], ids=["missing", "unexpected", "unknown-category", "wrong-type", "null", "out-of-range"])
def test_bad_second_record_rejected_before_inference(
    client: TestClient, frozen_cases, mutation: str, monkeypatch: pytest.MonkeyPatch
):
    items, _ = frozen_cases
    bad = dict(items[1]["features"])
    if mutation == "missing_feature":
        bad.pop("age")
    elif mutation == "extra_feature":
        bad["employee_id"] = "synthetic-test-only"
    elif mutation == "unknown_category":
        bad["department"] = "Unknown Department"
    elif mutation == "numeric_string":
        bad["age"] = "40"
    elif mutation == "null_value":
        bad["absences_90d"] = None
    elif mutation == "bad_ratio":
        bad["remote_work_ratio"] = 2.0

    # A rejected batch must never reach the inference function at all.
    inference_called = False

    def unexpected_inference(_items):
        nonlocal inference_called
        inference_called = True
        raise AssertionError("Invalid batch reached model inference")

    monkeypatch.setattr(api_module, "predict_batch", unexpected_inference)
    _post(client, [items[0], {"features": bad}], 422)
    assert inference_called is False


def test_extra_batch_envelope_field_rejected(client: TestClient, frozen_cases):
    items, _ = frozen_cases
    response = client.post("/predict/batch", json={"items": items[:1], "extra": "x"})
    assert response.status_code == 422, response.text


def test_registered_model_still_unpromoted(frozen_cases):
    from mlflow.tracking import MlflowClient

    registry = MlflowClient(
        tracking_uri="sqlite:///mlflow_tracking.db",
        registry_uri="sqlite:///mlflow_tracking.db",
    )
    version = registry.get_model_version(MODEL_NAME, MODEL_VERSION)
    assert version.status == "READY"
    assert version.tags["candidate_status"] == "candidate_not_promoted"
    assert float(version.tags["operating_threshold"]) == THRESHOLD
    assert version.tags["synthetic_data_only"] == "true"
    registered = registry.get_registered_model(MODEL_NAME)
    assert not registered.aliases, "CP6 must not promote or alias a model"
