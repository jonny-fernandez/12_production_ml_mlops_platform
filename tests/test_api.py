"""CP5 real-time API tests (model loading is injected to avoid MLflow in unit tests)."""

from fastapi.testclient import TestClient
import numpy as np
import pytest
from pydantic import ValidationError
from mlops_platform.schemas import PredictionRequest

from mlops_platform.api.main import app
from mlops_platform.serving import realtime

client = TestClient(app)

VALID = {
    "department": "Development",
    "job_family": "Data",
    "job_level": "L2",
    "location": "Chicago-North",
    "employment_type": "Full-Time",
    "age": 35,
    "tenure_months": 24,
    "monthly_salary_annualized": 70000.0,
    "overtime_hours_90d": 4.5,
    "absences_90d": 2,
    "performance_score": 4.1,
    "engagement_score": 72.0,
    "manager_changes_12m": 1,
    "months_since_promotion": 13,
    "commute_minutes": 25,
    "training_hours_12m": 20.0,
    "remote_work_ratio": 0.4,
    "salary_change_pct_12m": 0.04,
    "internal_moves_24m": 1,
}


class FakeModel:
    def predict_proba(self, frame):
        assert list(frame.columns) == list(realtime.FEATURE_NAMES)
        assert len(frame) == 1
        return np.array([[0.8, 0.2]])


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_model_info():
    response = client.get("/model/info")
    assert response.status_code == 200
    assert response.json()["model_name"] == "p09-attrition-gb"
    assert response.json()["model_version"] == "1"


def test_predict_contract(monkeypatch):
    monkeypatch.setattr(realtime, "_load_model", lambda: FakeModel())
    response = client.post("/predict", json={"features": VALID})
    assert response.status_code == 200
    assert response.json() == {
        "prediction": 1,
        "probability": 0.2,
        "model_name": "p09-attrition-gb",
        "model_version": "1",
    }


def test_predict_rejects_missing_feature():
    invalid = dict(VALID)
    invalid.pop("age")
    assert client.post("/predict", json={"features": invalid}).status_code == 422


def test_predict_rejects_extra_feature():
    invalid = {**VALID, "employee_id": "secret"}
    assert client.post("/predict", json={"features": invalid}).status_code == 422


def test_predict_rejects_unknown_category():
    invalid = {**VALID, "department": "Unexpected"}
    assert client.post("/predict", json={"features": invalid}).status_code == 422


def test_predict_rejects_numeric_string():
    invalid = {**VALID, "age": "35"}
    assert client.post("/predict", json={"features": invalid}).status_code == 422


def test_predict_rejects_null():
    invalid = {**VALID, "absences_90d": None}
    assert client.post("/predict", json={"features": invalid}).status_code == 422


def test_predict_rejects_infinite_or_nan():
    invalid = {**VALID, "performance_score": float("inf")}
    with pytest.raises(ValidationError):
        PredictionRequest(features=invalid)


def test_predict_returns_503_when_model_missing(monkeypatch):
    def unavailable():
        raise realtime.ModelUnavailableError("sensitive local model path")
    monkeypatch.setattr(realtime, "_load_model", unavailable)
    response = client.post("/predict", json={"features": VALID})
    assert response.status_code == 503
    assert "sensitive" not in response.text
