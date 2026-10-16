"""Fail-closed cloud model-release verification for Project 12.

The portable CP9 candidate is never approval by itself. Cloud serving additionally
requires an independently reviewed release_approval.json, an exact deployment
reference, and the locked SHA-256 model bytes. The approval record is a process
control (not a cryptographic signature). Only the pinned joblib is deserialized.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from mlops_platform.serving.cloud_candidate import (
    MODEL_SHA256,
    CandidateVerificationError,
    VerifiedCandidate,
    inspect_candidate,
)

APPROVAL_FILE = "release_approval.json"
CANDIDATE_DIR = "candidate"
APPROVAL_FORMAT = "project12_model_release_approval_v1"
TARGET = "public_https_aws_ecs_fargate"


class CloudReleaseError(RuntimeError):
    """Cloud release lacks required, verifiable review evidence."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_cloud_release(root: str | Path, expected_reference: str) -> VerifiedCandidate:
    """Validate review record and pinned candidate before any joblib.load.

    Does NOT make a promotion decision, create approvals, or load model bytes.
    """
    folder = Path(root)
    if not folder.is_absolute() or not folder.is_dir() or folder.is_symlink():
        raise CloudReleaseError("Cloud model directory must be an absolute real directory")
    if {p.name for p in folder.iterdir()} != {CANDIDATE_DIR, APPROVAL_FILE}:
        raise CloudReleaseError("Approved image model directory has unexpected files")
    approval_path = folder / APPROVAL_FILE
    candidate_path = folder / CANDIDATE_DIR
    if approval_path.is_symlink() or not approval_path.is_file() or candidate_path.is_symlink():
        raise CloudReleaseError("Release approval files must be regular, non-symlink paths")
    if (not expected_reference or len(expected_reference) < 8
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{7,127}", expected_reference)):
        raise CloudReleaseError("Missing independently reviewed release reference")
    try:
        verified = inspect_candidate(candidate_path)
    except (CandidateVerificationError, OSError, ValueError) as exc:
        raise CloudReleaseError("Pinned cloud candidate verification failed") from exc
    try:
        record: Any = json.loads(approval_path.read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeError) as exc:
        raise CloudReleaseError("Release approval manifest unavailable") from exc
    if type(record) is not dict:
        raise CloudReleaseError("Invalid release approval manifest")

    required = {
        "format": APPROVAL_FORMAT,
        "approved": True,
        "release_target": TARGET,
        "model_name": "p09-attrition-gb",
        "model_version": "1",
        "model_sha256": MODEL_SHA256,
        "candidate_manifest_sha256": _sha256(verified.manifest_path),
        "release_approval_reference": expected_reference,
        "synthetic_data_only": True,
    }
    for key, value in required.items():
        if type(record.get(key)) is not type(value) or record[key] != value:
            raise CloudReleaseError(f"Invalid release approval field: {key}")
    reviewer = record.get("approved_by")
    date = record.get("approved_on_utc")
    if not isinstance(reviewer, str) or len(reviewer.strip()) < 3 or reviewer.lower() in {"tbd", "placeholder", "example"}:
        raise CloudReleaseError("Release reviewer not documented")
    if not isinstance(date, str) or not re.fullmatch(r"20\d\d-\d\d-\d\d", date):
        raise CloudReleaseError("Release approval date missing")
    # Stronger assurance against counterfeit approvals will be added in CP16.
    return verified


def load_approved_cloud_model(root: str | Path, approval_reference: str):
    """Load the single known, already-reviewed model only after verification."""
    checked = verify_cloud_release(root, approval_reference)
    try:
        import joblib
        model = joblib.load(checked.model_path)  # SHA pinned before pickle load
    except Exception as exc:
        raise CloudReleaseError("Verified model failed to deserialize") from exc
    return model
