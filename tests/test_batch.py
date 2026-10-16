"""CP6 batch contract, validation, vectorization, and failure-mode regression tests.

No MLflow server, model registration, or paid API calls are required.
"""

import numpy as np
import pytest
from fastapi.testclient import TestClient
from mlops_platform.api.main import app
from mlops_platform.schemas import MAX_BATCH_SIZE, PredictionRequest
from mlops_platform.serving import realtime
from mlops_platform.serving.batch import predict_batch
from test_api import VALID

client = TestClient(app)


class FakeBatchModel:
    def __init__(self, scores=None):
        self.calls = 0
        self.frames = []
        self.scores = scores

    def predict_proba(self, frame):
        self.calls += 1
        self.frames.append(frame.copy())
        scores = self.scores
        if scores is None:
            scores = [0.05 if i % 2 == 0 else 0.5 for i in range(len(frame))]
        return np.array([[1.0 - score, score] for score in scores])


def test_batch_valid_order_and_single_model_call(monkeypatch):
    model = FakeBatchModel()
    monkeypatch.setattr(realtime, "_load_model", lambda: model)
    b = dict(VALID)
    b["age"] = 43
    response = client.post("/predict/batch", json={"items": [
        {"features": VALID}, {"features": b}, {"features": VALID}
    ]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["count"] == 3
    assert [x["probability"] for x in body["predictions"]] == [0.05, 0.5, 0.05]
    assert [x["prediction"] for x in body["predictions"]] == [0, 1, 0]
    assert {x["model_name"] for x in body["predictions"]} == {"p09-attrition-gb"}
    assert {x["model_version"] for x in body["predictions"]} == {"1"}
    assert model.calls == 1
    assert list(model.frames[0].columns) == list(realtime.FEATURE_NAMES)
    assert list(model.frames[0]["age"]) == [35, 43, 35]


def test_batch_rejects_empty_body():
    assert client.post("/predict/batch", json={"items": []}).status_code == 422


def test_batch_rejects_too_many_items():
    payload = {"items": [{"features": VALID}] * (MAX_BATCH_SIZE + 1)}
    assert client.post("/predict/batch", json=payload).status_code == 422


@pytest.mark.parametrize("mutate", [
    lambda d: d.pop("age"),
    lambda d: d.update(employee_id="private"),
    lambda d: d.update(department="Invalid Department"),
    lambda d: d.update(age="35"),
    lambda d: d.update(absences_90d=None),
])
def test_batch_all_or_nothing_invalid_second_item(monkeypatch, mutate):
    model = FakeBatchModel()
    monkeypatch.setattr(realtime, "_load_model", lambda: model)
    bad = dict(VALID)
    mutate(bad)
    response = client.post("/predict/batch", json={"items": [
        {"features": VALID}, {"features": bad}
    ]})
    assert response.status_code == 422
    assert model.calls == 0


def test_batch_rejects_extra_envelope_field():
    response = client.post("/predict/batch", json={
        "items": [{"features": VALID}], "secret": "not permitted"
    })
    assert response.status_code == 422


def test_batch_returns_503_when_model_unavailable(monkeypatch):
    def broken():
        raise realtime.ModelUnavailableError("private registry location")
    monkeypatch.setattr(realtime, "_load_model", broken)
    response = client.post("/predict/batch", json={"items": [{"features": VALID}]})
    assert response.status_code == 503
    assert "private registry location" not in response.text


@pytest.mark.parametrize("scores", [
    [0.05],  # Incorrect number of result rows
    [float("nan"), 0.5],
    [-0.01, 0.5],
    [1.01, 0.5],
])
def test_bad_batch_model_output_fails_closed(monkeypatch, scores):
    model = FakeBatchModel(scores=scores)
    monkeypatch.setattr(realtime, "_load_model", lambda: model)
    response = client.post("/predict/batch", json={"items": [
        {"features": VALID}, {"features": VALID}
    ]})
    assert response.status_code == 503


def test_python_batch_keeps_empty_list_compatibility(monkeypatch):
    def should_not_load():
        raise AssertionError("Empty batch must not load the model")
    monkeypatch.setattr(realtime, "_load_model", should_not_load)
    assert predict_batch([]) == []


def test_python_batch_rejects_oversize_before_model_load(monkeypatch):
    def should_not_load():
        raise AssertionError("Too-large batch must not load the model")
    monkeypatch.setattr(realtime, "_load_model", should_not_load)
    item = PredictionRequest(features=VALID)
    with pytest.raises(ValueError):
        predict_batch([item] * (MAX_BATCH_SIZE + 1))
