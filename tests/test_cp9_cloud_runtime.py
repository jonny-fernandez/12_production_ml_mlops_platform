"""CP9 Step 11: no-AWS, no-serialization tests for candidate inspection."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from mlops_platform.serving import cloud_candidate as candidate
from mlops_platform.config import settings
from mlops_platform.serving import realtime


def fake_stage(tmp_path, monkeypatch):
    folder = tmp_path / "candidate"
    folder.mkdir()
    blob = b"unit-test-only-not-a-real-pickle"
    digest = hashlib.sha256(blob).hexdigest()
    monkeypatch.setattr(candidate, "MODEL_SHA256", digest)
    (folder / candidate.MODEL_FILENAME).write_bytes(blob)
    obj = {
        "format": "project12_cloud_candidate_staging_v1",
        "model_name": "p09-attrition-gb",
        "model_version": "1",
        "model_filename": candidate.MODEL_FILENAME,
        "model_sha256": digest,
        "source_model_sha256": candidate.SOURCE_SHA256,
        "source_mlflow_run_id": candidate.MLFLOW_RUN_ID,
        "cp7_manifest_sha256": "a" * 64,
        "feature_list": list(candidate.FEATURE_NAMES),
        "operating_threshold": 0.125,
        "synthetic_data_only": True,
        "frozen_test_records": 507,
        "candidate_frozen_max_difference": 1.11e-16,
        "registry_frozen_max_difference": 1.11e-16,
        "approval_status": "pending_review",
        "cloud_deployable": False,
        "release_approval_reference": None,
        "approved_image_digest": None,
        "cloud_runtime_verified": False,
        "cloud_target": "aws_ecs_fargate",
    }
    man = folder / candidate.MANIFEST_FILENAME
    man.write_text(json.dumps(obj), encoding="utf-8")
    return folder, man, obj


def test_valid_staged_candidate_is_inspected_without_loading(tmp_path, monkeypatch):
    folder, man, obj = fake_stage(tmp_path, monkeypatch)
    verified = candidate.inspect_candidate(folder)
    assert verified.model_sha256 == candidate.MODEL_SHA256
    assert len(verified.feature_names) == 19
    assert verified.threshold == 0.125
    assert json.loads(man.read_text()) == obj


@pytest.mark.parametrize("field,value", [
    ("approval_status", "approved"),
    ("cloud_deployable", True),
    ("cloud_runtime_verified", True),
    ("release_approval_reference", "CHANGE-12345"),
    ("approved_image_digest", "sha256:" + "a" * 64),
    ("feature_list", ["age"]),
    ("operating_threshold", 0.5),
    ("frozen_test_records", 506),
    ("synthetic_data_only", False),
    ("model_version", "2"),
    ("cp7_manifest_sha256", "not-a-hash"),
    ("candidate_frozen_max_difference", float("inf")),
    ("registry_frozen_max_difference", -1.0),
])
def test_modified_manifest_rejected(tmp_path, monkeypatch, field, value):
    folder, man, obj = fake_stage(tmp_path, monkeypatch)
    obj[field] = value
    man.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(candidate.CandidateVerificationError):
        candidate.inspect_candidate(folder)


def test_corrupted_model_rejected_before_deserialization(tmp_path, monkeypatch):
    folder, man, obj = fake_stage(tmp_path, monkeypatch)
    (folder / candidate.MODEL_FILENAME).write_bytes(b"tampered")
    with pytest.raises(candidate.CandidateVerificationError, match="SHA-256"):
        candidate.inspect_candidate(folder)


def test_extra_file_rejected(tmp_path, monkeypatch):
    folder, man, obj = fake_stage(tmp_path, monkeypatch)
    (folder / ".env").write_text("SECRET=must-not-be-there")
    with pytest.raises(candidate.CandidateVerificationError, match="exactly"):
        candidate.inspect_candidate(folder)


def test_symlink_manifest_rejected(tmp_path, monkeypatch):
    folder, man, obj = fake_stage(tmp_path, monkeypatch)
    other = tmp_path / "manifest.json"
    other.write_bytes(man.read_bytes())
    man.unlink()
    try:
        man.symlink_to(other)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks unavailable on this platform")
    with pytest.raises(candidate.CandidateVerificationError, match="symbolic links"):
        candidate.inspect_candidate(folder)


def test_relative_candidate_directory_is_rejected(tmp_path, monkeypatch):
    with pytest.raises(candidate.CandidateVerificationError, match="absolute"):
        candidate.inspect_candidate(Path("artifacts/cp9_cloud_candidate"))


def test_cloud_api_still_rejects_candidate(monkeypatch, tmp_path):
    folder, _, _ = fake_stage(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "app_env", "cloud")
    monkeypatch.setattr(settings, "model_bundle_dir", str(folder))
    realtime._load_model.cache_clear()
    try:
        with pytest.raises(realtime.ModelUnavailableError, match="Unpromoted candidate"):
            realtime._load_model()
    finally:
        realtime._load_model.cache_clear()
