"""CP9 Step 9: isolated, no-AWS tests for the unapproved cloud candidate stage."""

import importlib.util
import json
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "Project12_CP9_stage_cloud_candidate.py"
spec = importlib.util.spec_from_file_location("cp9_stage_module", MODULE)
cloud = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cloud)


def fixture_root(tmp_path, monkeypatch, *, status="candidate_not_promoted"):
    root = tmp_path
    src = root / "artifacts" / "cp7_container_model"
    src.mkdir(parents=True)
    blob = b"unit-test-model-bytes-NOT-a-real-joblib"
    digest = cloud.hashlib.sha256(blob).hexdigest()
    monkeypatch.setattr(cloud, "PINNED_SHA", digest)
    (src / cloud.MODEL_NAME).write_bytes(blob)
    base = {
        "format": "project12_verified_local_joblib_v1",
        "model_name": "p09-attrition-gb",
        "model_version": "1",
        "source_mlflow_run_id": cloud.RUN_ID,
        "candidate_status": status,
        "synthetic_data_only": True,
        "operating_threshold": 0.125,
        "candidate_model_sha256": digest,
        "source_model_sha256": cloud.SOURCE_SHA,
        "model_filename": cloud.MODEL_NAME,
        "feature_list": list(cloud.FEATURES),
        "test_records": 507,
        "candidate_frozen_max_difference": 1.11e-16,
        "registry_frozen_max_difference": 1.11e-16,
    }
    (src / cloud.INPUT_MANIFEST_NAME).write_text(json.dumps(base), encoding="utf-8")
    (root / ".gitignore").write_text("artifacts/*\n", encoding="utf-8")
    (root / ".dockerignore").write_text("artifacts/\n", encoding="utf-8")
    tf = root / "infrastructure" / "terraform"
    tf.mkdir(parents=True)
    (tf / "public_https_ecs_service.tf").write_text("# fixture", encoding="utf-8")
    return root


def test_successful_staging_is_pending_review_and_idempotent(tmp_path, monkeypatch):
    root = fixture_root(tmp_path, monkeypatch)
    assert cloud.stage(root) == "NEW UNAPPROVED CANDIDATE STAGED"
    stage_dir = root / "artifacts/cp9_cloud_candidate"
    staged = cloud.read_json(stage_dir / cloud.OUTPUT_MANIFEST_NAME)
    assert staged["cloud_deployable"] is False
    assert staged["cloud_runtime_verified"] is False
    assert staged["approval_status"] == "pending_review"
    assert staged["approved_image_digest"] is None
    assert staged["release_approval_reference"] is None
    assert cloud.checksum(stage_dir / cloud.MODEL_NAME) == cloud.PINNED_SHA
    assert cloud.stage(root) == "EXISTING CANDIDATE VERIFIED; NO OVERWRITE"


def test_rejects_status_claiming_approval(tmp_path, monkeypatch):
    root = fixture_root(tmp_path, monkeypatch, status="production_approved")
    with pytest.raises(ValueError, match="candidate_status"):
        cloud.stage(root)


def test_rejects_modified_source_bytes(tmp_path, monkeypatch):
    root = fixture_root(tmp_path, monkeypatch)
    (root / "artifacts/cp7_container_model" / cloud.MODEL_NAME).write_bytes(b"altered")
    with pytest.raises(ValueError, match="pinned hash"):
        cloud.stage(root)


def test_rejects_wrong_feature_order(tmp_path, monkeypatch):
    root = fixture_root(tmp_path, monkeypatch)
    p = root / "artifacts/cp7_container_model" / cloud.INPUT_MANIFEST_NAME
    d = json.loads(p.read_text());d["feature_list"].reverse()
    p.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(ValueError, match="feature_list"):
        cloud.stage(root)


def test_rejects_invalid_frozen_prediction_evidence(tmp_path, monkeypatch):
    root = fixture_root(tmp_path, monkeypatch)
    p = root / "artifacts/cp7_container_model" / cloud.INPUT_MANIFEST_NAME
    d = json.loads(p.read_text());d["registry_frozen_max_difference"] = 0.2
    p.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(ValueError, match="parity"):
        cloud.stage(root)


def test_rejects_changed_existing_candidate(tmp_path, monkeypatch):
    root = fixture_root(tmp_path, monkeypatch)
    cloud.stage(root)
    model = root / "artifacts/cp9_cloud_candidate" / cloud.MODEL_NAME
    model.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="Existing staged model"):
        cloud.stage(root)


def test_rejects_missing_build_exclusions(tmp_path, monkeypatch):
    root = fixture_root(tmp_path, monkeypatch)
    (root / ".dockerignore").write_text(".venv/\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Docker build exclusion"):
        cloud.stage(root)


def test_never_loads_or_deserializes_joblib(tmp_path, monkeypatch):
    root = fixture_root(tmp_path, monkeypatch)
    assert cloud.stage(root).startswith("NEW")
    assert cloud.stage(root).startswith("EXISTING")


def test_output_manifest_is_deterministic(tmp_path, monkeypatch):
    root = fixture_root(tmp_path, monkeypatch)
    cloud.stage(root)
    man = root / "artifacts/cp9_cloud_candidate" / cloud.OUTPUT_MANIFEST_NAME
    before = man.read_bytes()
    cloud.stage(root)
    assert man.read_bytes() == before
