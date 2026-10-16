"""CP8 local security, readiness and privacy checks. No real secrets/API calls."""

from __future__ import annotations

import json
import logging
from io import StringIO

import pytest
import numpy as np
from fastapi.testclient import TestClient
from pydantic import SecretStr

from mlops_platform.api.main import app
from mlops_platform.api import security
from mlops_platform.config import settings
from mlops_platform.serving import realtime
from test_api import VALID


KEY = "test-fixture-" + "X" * 48  # Not a real credential.


@pytest.fixture
def secured(monkeypatch):
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "api_key_file", None)
    monkeypatch.setattr(settings, "api_key", SecretStr(KEY))
    with TestClient(app) as client:
        yield client


def test_unprotected_liveness_does_not_claim_model_available(secured):
    assert secured.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize("method,route,body", [
    ("GET", "/model/info", None),
    ("POST", "/predict", {"features": VALID}),
    ("POST", "/predict/batch", {"items": [{"features": VALID}]}),
])
def test_sensitive_routes_reject_missing_and_wrong_keys(secured, method, route, body):
    resp = secured.request(method, route, json=body)
    assert resp.status_code == 401
    assert KEY not in resp.text
    resp = secured.request(method, route, json=body, headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


def test_valid_key_preserves_prediction(monkeypatch, secured):
    class MockModel:
        def predict_proba(self, frame):
            assert len(frame) == 1
            return np.array([[0.8, 0.2]])
    monkeypatch.setattr(realtime, "_load_model", lambda: MockModel())
    response = secured.post("/predict", json={"features": VALID}, headers={"X-API-Key": KEY})
    assert response.status_code == 200
    assert response.json()["prediction"] == 1
    assert response.json()["probability"] == pytest.approx(0.2)


def test_config_missing_key_fails_closed(monkeypatch, secured):
    monkeypatch.setattr(settings, "api_key", None)
    resp = secured.post("/predict", json={"features": VALID})
    assert resp.status_code == 503
    assert secured.get("/ready").status_code == 503


def test_placeholder_key_fails_closed(monkeypatch, secured):
    monkeypatch.setattr(settings, "api_key", SecretStr("replace_me"))
    assert secured.get("/model/info", headers={"X-API-Key": "replace_me"}).status_code == 503


def test_file_based_key(monkeypatch, tmp_path, secured):
    secret_file = tmp_path / "api_key"
    secret_file.write_text(KEY + "\n", encoding="utf-8")
    monkeypatch.setattr(settings, "api_key_file", str(secret_file))
    monkeypatch.setattr(settings, "api_key", None)
    assert secured.get("/model/info", headers={"X-API-Key": KEY}).status_code == 200
    assert secured.get("/model/info", headers={"X-API-Key": KEY[:-1]}).status_code == 401


def test_non_local_mode_without_auth_is_blocked(monkeypatch):
    monkeypatch.setattr(settings, "auth_required", False)
    monkeypatch.setattr(settings, "app_env", "production")
    with TestClient(app) as client:
        assert client.get("/model/info").status_code == 503


def test_readiness_model_available(monkeypatch, secured):
    monkeypatch.setattr(realtime, "_load_model", lambda: object())
    assert secured.get("/ready").json() == {"status": "ready"}


def test_readiness_model_missing_fails_closed(monkeypatch, secured):
    def broken():
        raise realtime.ModelUnavailableError("C:/secret/private/model.joblib")
    monkeypatch.setattr(realtime, "_load_model", broken)
    response = secured.get("/ready")
    assert response.status_code == 503
    assert "secret" not in response.text


def test_audit_does_not_log_auth_or_payload(secured):
    from mlops_platform.api.observability import logger
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    try:
        response = secured.post(
            "/predict?employee_id=private-value",
            json={"features": {**VALID, "department": "secret-feature-value"}},
            headers={"X-API-Key": "wrong-secret-value"},
        )
    finally:
        logger.removeHandler(handler)
    assert response.status_code == 401
    line = stream.getvalue().strip()
    doc = json.loads(line)
    assert doc["route"] == "/predict"
    assert doc["status_code"] == 401
    assert len(doc["request_id"]) == 16
    assert "private-value" not in line
    assert "secret-feature-value" not in line
    assert "wrong-secret-value" not in line
    assert KEY not in line
    assert response.headers.get("X-Request-ID") == doc["request_id"]
