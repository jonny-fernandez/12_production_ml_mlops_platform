"""Read-only CP9 cloud-candidate verification, NOT a cloud-serving approval.

This module validates the portable model bytes and their evidence manifest
without deserializing pickle/joblib. Only a separately reviewed release process
may enable cloud serving. Importing this module never loads the model.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MODEL_FILENAME = "candidate_model_pipeline.joblib"
MANIFEST_FILENAME = "cloud_candidate_manifest.json"
MODEL_SHA256 = "27585a4b8443be29a7cf41a5a2bfd3227ae4a66d8dd947afd88d38111f404d43"
SOURCE_SHA256 = "12f9c529ecaffe70f8c1ad401ab398e25b135d8a5ecab6edd71584d65a126755"
MLFLOW_RUN_ID = "0a2731b4c9c64abfb373166e22b1f97e"
FEATURE_NAMES = (
    "department", "job_family", "job_level", "location", "employment_type",
    "age", "tenure_months", "monthly_salary_annualized", "overtime_hours_90d",
    "absences_90d", "performance_score", "engagement_score", "manager_changes_12m",
    "months_since_promotion", "commute_minutes", "training_hours_12m",
    "remote_work_ratio", "salary_change_pct_12m", "internal_moves_24m",
)


class CandidateVerificationError(ValueError):
    """Unapproved cloud candidate is malformed, unsafe, or altered."""


@dataclass(frozen=True)
class VerifiedCandidate:
    model_path: Path
    manifest_path: Path
    model_sha256: str
    model_name: str
    model_version: str
    feature_names: tuple[str, ...]
    threshold: float


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CandidateVerificationError(message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _equal_type_and_value(value: Any, expected: Any) -> bool:
    return type(value) is type(expected) and value == expected


def inspect_candidate(directory: str | Path) -> VerifiedCandidate:
    """Validate portable candidate without loading executable model bytes.

    Safe to run on Windows or Linux. Explicitly refuses staged candidates with
    approval/deployment claims and any unexpected files or symbolic links.
    """
    folder = Path(directory)
    _require(folder.is_absolute() and folder.is_dir() and not folder.is_symlink(),
             "Expected an existing, absolute, non-symlink candidate directory")
    entries = list(folder.iterdir())
    _require({p.name for p in entries} == {MODEL_FILENAME, MANIFEST_FILENAME},
             "Candidate directory must contain exactly the model and manifest")
    _require(all(p.is_file() and not p.is_symlink() for p in entries),
             "Candidate files must be regular files, not symbolic links")
    model = folder / MODEL_FILENAME
    manifest_file = folder / MANIFEST_FILENAME
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise CandidateVerificationError("Unreadable cloud candidate manifest") from exc
    _require(type(manifest) is dict, "Manifest is not a JSON object")

    required = {
        "format": "project12_cloud_candidate_staging_v1",
        "model_name": "p09-attrition-gb",
        "model_version": "1",
        "model_filename": MODEL_FILENAME,
        "model_sha256": MODEL_SHA256,
        "source_model_sha256": SOURCE_SHA256,
        "source_mlflow_run_id": MLFLOW_RUN_ID,
        "feature_list": list(FEATURE_NAMES),
        "operating_threshold": 0.125,
        "synthetic_data_only": True,
        "frozen_test_records": 507,
        "approval_status": "pending_review",
        "cloud_deployable": False,
        "release_approval_reference": None,
        "approved_image_digest": None,
        "cloud_runtime_verified": False,
        "cloud_target": "aws_ecs_fargate",
    }
    for name, expected in required.items():
        _require(_equal_type_and_value(manifest.get(name), expected),
                 f"Cloud candidate manifest mismatch: {name}")
    for name in ("candidate_frozen_max_difference", "registry_frozen_max_difference"):
        value = manifest.get(name)
        _require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1e-8,
                 f"Invalid recorded parity evidence: {name}")
    _require(bool(re.fullmatch(r"[0-9a-f]{64}", str(manifest.get("cp7_manifest_sha256", "")))),
             "Invalid CP7 provenance checksum")
    _require(_sha256(model) == MODEL_SHA256, "Model SHA-256 differs from locked source")

    return VerifiedCandidate(model_path=model, manifest_path=manifest_file,
                             model_sha256=MODEL_SHA256, model_name="p09-attrition-gb",
                             model_version="1", feature_names=FEATURE_NAMES,
                             threshold=0.125)
