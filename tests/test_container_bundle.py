"""CP7 bundle loader regression tests; no Docker or MLflow server required.

These tests do not register, promote, retrain, or modify a real model.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pytest
from fastapi.testclient import TestClient

from mlops_platform.api.main import app
from mlops_platform.schemas import FEATURE_NAMES
from mlops_platform.serving import realtime
from test_api import VALID


class FakePipeline:
    feature_names_in_ = np.array(FEATURE_NAMES)
    classes_ = np.array([0, 1])

    def predict_proba(self, frame):
        return np.tile(np.array([[0.8, 0.2]]), (len(frame), 1))


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    bundle_path = tmp_path / "bundle"
    bundle_path.mkdir()
    model_path = bundle_path / realtime.BUNDLE_MODEL_FILENAME
    joblib.dump(FakePipeline(), model_path)
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    monkeypatch.setattr(realtime, "EXPECTED_CANDIDATE_SHA256", digest)
    manifest = {
        "format": "project12_verified_local_joblib_v1",
        "model_name": realtime.EXPECTED_NAME,
        "model_version": realtime.EXPECTED_VERSION,
        "source_mlflow_run_id": realtime.EXPECTED_RUN_ID,
        "candidate_status": "candidate_not_promoted",
        "synthetic_data_only": True,
        "operating_threshold": realtime.EXPECTED_THRESHOLD,
        "candidate_model_sha256": digest,
        "source_model_sha256": realtime.EXPECTED_SOURCE_SHA256,
        "model_filename": realtime.BUNDLE_MODEL_FILENAME,
        "feature_list": list(FEATURE_NAMES),
        "test_records": 507,
        "candidate_frozen_max_difference": 0.0,
        "registry_frozen_max_difference": 0.0,
        "generated_utc": "2026-10-13T00:00:00+00:00",
    }
    manifest_path = bundle_path / realtime.BUNDLE_MANIFEST_FILENAME
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return bundle_path, model_path, manifest_path


def _rewrite_manifest(path, fn):
    doc = json.loads(path.read_text(encoding="utf-8"))
    fn(doc)
    path.write_text(json.dumps(doc), encoding="utf-8")


def test_bundle_loads_pinned_verified_candidate(bundle):
    path, _, _ = bundle
    model = realtime._load_verified_bundle(path)
    assert list(model.feature_names_in_) == list(FEATURE_NAMES)
    assert model.predict_proba([{}])[0, 1] == pytest.approx(0.2)


def test_bundle_disallows_relative_directory(bundle):
    with pytest.raises(realtime.ModelUnavailableError, match="absolute directory"):
        realtime._load_verified_bundle(Path("artifacts/cp7_container_model"))


def test_bundle_rejects_missing_manifest(bundle):
    path, _, manifest = bundle
    manifest.unlink()
    with pytest.raises(realtime.ModelUnavailableError, match="regular files"):
        realtime._load_verified_bundle(path)


def test_bundle_rejects_tampered_model_before_deserialize(bundle, monkeypatch):
    path, model, _ = bundle
    model.write_bytes(b"not trusted bytes")
    def unsafe_load(*args, **kwargs):
        raise AssertionError("Must never deserialize a failed checksum")
    monkeypatch.setattr(joblib, "load", unsafe_load)
    with pytest.raises(realtime.ModelUnavailableError, match="SHA-256"):
        realtime._load_verified_bundle(path)


@pytest.mark.parametrize("field,invalid", [
    ("candidate_status", "production"),
    ("model_version", "2"),
    ("operating_threshold", 0.5),
    ("synthetic_data_only", False),
    ("source_mlflow_run_id", "not-original"),
    ("source_model_sha256", "0" * 64),
    ("feature_list", list(reversed(FEATURE_NAMES))),
    ("model_filename", "../bad.joblib"),
    ("test_records", 506),
])
def test_bundle_rejects_manifest_inconsistency(bundle, field, invalid):
    path, _, manifest = bundle
    _rewrite_manifest(manifest, lambda doc: doc.update({field: invalid}))
    with pytest.raises(realtime.ModelUnavailableError, match="metadata mismatch"):
        realtime._load_verified_bundle(path)


def test_bundle_rejects_false_parity_evidence(bundle):
    path, _, manifest = bundle
    _rewrite_manifest(manifest, lambda doc: doc.update({"registry_frozen_max_difference": 0.9}))
    with pytest.raises(realtime.ModelUnavailableError, match="parity evidence"):
        realtime._load_verified_bundle(path)


def test_bundle_rejects_unexpected_pipeline_schema(bundle, monkeypatch):
    path, _, _ = bundle
    class BadModel:
        feature_names_in_ = ["age"]
        classes_ = [0, 1]
        predict_proba = lambda self, frame: [[0.8, 0.2]]
    monkeypatch.setattr(joblib, "load", lambda path: BadModel())
    with pytest.raises(realtime.ModelUnavailableError, match="feature ordering"):
        realtime._load_verified_bundle(path)


def test_bundle_loader_powers_both_api_paths(bundle, monkeypatch):
    path, _, _ = bundle
    monkeypatch.setattr(realtime.settings, "model_bundle_dir", str(path))
    realtime._load_model.cache_clear()
    try:
        with TestClient(app) as client:
            single = client.post("/predict", json={"features": VALID})
            batch = client.post("/predict/batch", json={"items": [{"features": VALID}] * 2})
        assert single.status_code == 200, single.text
        assert single.json()["prediction"] == 1
        assert single.json()["probability"] == pytest.approx(0.2)
        assert batch.status_code == 200, batch.text
        assert batch.json()["count"] == 2
        assert [x["prediction"] for x in batch.json()["predictions"]] == [1, 1]
    finally:
        realtime._load_model.cache_clear()


def test_real_exported_bundle_if_available():
    root = Path(__file__).resolve().parents[1]
    folder = root / "artifacts" / "cp7_container_model"
    if not folder.is_dir():
        pytest.skip("Exported CP7 bundle not available (e.g. clean CI)")
    model = realtime._load_verified_bundle(folder)
    assert list(model.feature_names_in_) == list(FEATURE_NAMES)
