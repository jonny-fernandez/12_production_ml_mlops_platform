"""CP9 offline regression tests: release fail-closed and exact artifact checks.

Never creates an approved model artifact, contacts AWS, or calls joblib.load.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from mlops_platform.config import settings
from mlops_platform.serving import cloud_release, realtime
from mlops_platform.serving.cloud_candidate import VerifiedCandidate


@pytest.fixture
def sample(tmp_path, monkeypatch):
    base = tmp_path / "release"
    c = base / "candidate"
    c.mkdir(parents=True)
    model = c / "candidate_model_pipeline.joblib"
    manifest = c / "cloud_candidate_manifest.json"
    model.write_bytes(b"test-no-pickle-deserialization")
    manifest.write_text('{"fixture": true}', encoding="utf-8")
    fake = VerifiedCandidate(model_path=model, manifest_path=manifest,
                             model_sha256=cloud_release.MODEL_SHA256,
                             model_name="p09-attrition-gb", model_version="1",
                             feature_names=tuple(realtime.FEATURE_NAMES), threshold=0.125)
    monkeypatch.setattr(cloud_release, "inspect_candidate", lambda _: fake)
    reference = "REVIEW-2026-001"
    record = {
        "format": cloud_release.APPROVAL_FORMAT,
        "approved": True,
        "release_target": cloud_release.TARGET,
        "model_name": "p09-attrition-gb",
        "model_version": "1",
        "model_sha256": cloud_release.MODEL_SHA256,
        "candidate_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "release_approval_reference": reference,
        "approved_by": "Independent Reviewer",
        "approved_on_utc": "2026-10-14",
        "synthetic_data_only": True,
    }
    release = base / cloud_release.APPROVAL_FILE
    release.write_text(json.dumps(record), encoding="utf-8")
    return base, reference, record


def test_valid_release_record_parsed_without_deserializing(sample):
    base, reference, _ = sample
    assert cloud_release.verify_cloud_release(base, reference).model_version == "1"


@pytest.mark.parametrize("field,bad", [
    ("approved", False),
    ("release_target", "local"),
    ("model_sha256", "0" * 64),
    ("candidate_manifest_sha256", "0" * 64),
    ("synthetic_data_only", False),
    ("release_approval_reference", "OTHER-REVIEW"),
    ("approved_by", "placeholder"),
    ("approved_on_utc", "unknown"),
])
def test_invalid_release_record_rejected(sample, field, bad):
    base, reference, record = sample
    record[field] = bad
    (base / cloud_release.APPROVAL_FILE).write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(cloud_release.CloudReleaseError):
        cloud_release.verify_cloud_release(base, reference)


def test_missing_release_ref_rejected(sample):
    base, _, _ = sample
    with pytest.raises(cloud_release.CloudReleaseError):
        cloud_release.verify_cloud_release(base, "")


def test_extra_release_directory_file_rejected(sample):
    base, reference, _ = sample
    (base / ".env").write_text("TEST_ONLY", encoding="utf-8")
    with pytest.raises(cloud_release.CloudReleaseError, match="unexpected"):
        cloud_release.verify_cloud_release(base, reference)


def test_no_approval_cloud_serve_fails_closed(monkeypatch, sample):
    base, reference, _ = sample
    monkeypatch.setattr(settings, "app_env", "cloud")
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "model_bundle_dir", str(base))
    monkeypatch.setattr(settings, "model_release_approved", False)
    monkeypatch.setattr(settings, "model_release_approval_reference", reference)
    realtime._load_model.cache_clear()
    try:
        with pytest.raises(realtime.ModelUnavailableError, match="Unpromoted candidate"):
            realtime._load_model()
    finally:
        realtime._load_model.cache_clear()


def test_wrong_ref_cloud_serve_fails_closed(monkeypatch, sample):
    base, _, _ = sample
    monkeypatch.setattr(settings, "app_env", "cloud")
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "model_bundle_dir", str(base))
    monkeypatch.setattr(settings, "model_release_approved", True)
    monkeypatch.setattr(settings, "model_release_approval_reference", "REVIEW-WRONG-01")
    realtime._load_model.cache_clear()
    try:
        with pytest.raises(realtime.ModelUnavailableError, match="verification failed"):
            realtime._load_model()
    finally:
        realtime._load_model.cache_clear()


def test_cloud_disabled_without_authentication(monkeypatch, sample):
    base, reference, _ = sample
    monkeypatch.setattr(settings, "app_env", "cloud")
    monkeypatch.setattr(settings, "auth_required", False)
    monkeypatch.setattr(settings, "model_bundle_dir", str(base))
    monkeypatch.setattr(settings, "model_release_approved", True)
    monkeypatch.setattr(settings, "model_release_approval_reference", reference)
    realtime._load_model.cache_clear()
    try:
        with pytest.raises(realtime.ModelUnavailableError, match="Unpromoted"):
            realtime._load_model()
    finally:
        realtime._load_model.cache_clear()
