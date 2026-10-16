"""CP9 Step 9: stage a *non-deployable* portable model candidate for later review.

Run from Project 12's repository root:
    .\\.venv\\Scripts\\python.exe .\\Project12_CP9_stage_cloud_candidate.py

This copies the previously verified CP7 synthetic model to an ignored, local
staging folder with a deterministic provenance manifest. It is NOT a cloud
runtime, model approval, release image, AWS operation, or promotion mechanism.
The existing APP_ENV=cloud serving rejection remains untouched.

The model file is pickle-based: this tool never deserializes it. Only the
previously pinned, locally generated SHA-256 is accepted.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "artifacts" / "cp7_container_model"
OUTPUT = ROOT / "artifacts" / "cp9_cloud_candidate"
MODEL_NAME = "candidate_model_pipeline.joblib"
INPUT_MANIFEST_NAME = "model_bundle_manifest.json"
OUTPUT_MANIFEST_NAME = "cloud_candidate_manifest.json"
PINNED_SHA = "27585a4b8443be29a7cf41a5a2bfd3227ae4a66d8dd947afd88d38111f404d43"
SOURCE_SHA = "12f9c529ecaffe70f8c1ad401ab398e25b135d8a5ecab6edd71584d65a126755"
RUN_ID = "0a2731b4c9c64abfb373166e22b1f97e"
FEATURES = (
    "department", "job_family", "job_level", "location", "employment_type",
    "age", "tenure_months", "monthly_salary_annualized", "overtime_hours_90d",
    "absences_90d", "performance_score", "engagement_score", "manager_changes_12m",
    "months_since_promotion", "commute_minutes", "training_hours_12m",
    "remote_work_ratio", "salary_change_pct_12m", "internal_moves_24m",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    require(type(data) is dict, f"Invalid JSON object: {path.name}")
    return data


def safe_regular(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def validate_source(root: Path) -> tuple[Path, Path, dict[str, Any]]:
    source = root / "artifacts" / "cp7_container_model"
    model = source / MODEL_NAME
    manifest_path = source / INPUT_MANIFEST_NAME
    require(safe_regular(model) and safe_regular(manifest_path), "CP7 model/manifest missing or unsafe")
    manifest = read_json(manifest_path)
    required: dict[str, Any] = {
        "format": "project12_verified_local_joblib_v1",
        "model_name": "p09-attrition-gb",
        "model_version": "1",
        "source_mlflow_run_id": RUN_ID,
        "candidate_status": "candidate_not_promoted",
        "synthetic_data_only": True,
        "operating_threshold": 0.125,
        "candidate_model_sha256": PINNED_SHA,
        "source_model_sha256": SOURCE_SHA,
        "model_filename": MODEL_NAME,
        "feature_list": list(FEATURES),
        "test_records": 507,
    }
    for key, expected in required.items():
        require(type(manifest.get(key)) is type(expected) and manifest[key] == expected,
                f"CP7 metadata mismatch: {key}")
    for name in ("candidate_frozen_max_difference", "registry_frozen_max_difference"):
        value = manifest.get(name)
        require(type(value) in (int, float) and 0 <= value <= 1e-8,
                f"CP7 parity evidence missing or invalid: {name}")
    require(checksum(model) == PINNED_SHA, "CP7 model bytes differ from the pinned hash")
    return model, manifest_path, manifest


def build_candidate_manifest(source_manifest_sha: str, source: dict[str, Any]) -> dict[str, Any]:
    """Create the immutable candidate inventory. Never claim release approval."""
    return {
        "format": "project12_cloud_candidate_staging_v1",
        "model_name": "p09-attrition-gb",
        "model_version": "1",
        "model_filename": MODEL_NAME,
        "model_sha256": PINNED_SHA,
        "source_model_sha256": SOURCE_SHA,
        "source_mlflow_run_id": RUN_ID,
        "cp7_manifest_sha256": source_manifest_sha,
        "feature_list": list(FEATURES),
        "operating_threshold": 0.125,
        "synthetic_data_only": True,
        "frozen_test_records": 507,
        "candidate_frozen_max_difference": source["candidate_frozen_max_difference"],
        "registry_frozen_max_difference": source["registry_frozen_max_difference"],
        "approval_status": "pending_review",
        "cloud_deployable": False,
        "release_approval_reference": None,
        "approved_image_digest": None,
        "cloud_runtime_verified": False,
        "cloud_target": "aws_ecs_fargate",
    }


def secure_defaults_present(root: Path) -> None:
    dockerignore = root / ".dockerignore"
    gitignore = root / ".gitignore"
    require(safe_regular(dockerignore) and safe_regular(gitignore), "Missing Git/Docker exclusions")
    require("artifacts/" in dockerignore.read_text(encoding="utf-8"),
            "Docker build exclusion for artifacts/ missing")
    require("artifacts/*" in gitignore.read_text(encoding="utf-8"),
            "Git exclusion for generated model artifacts missing")
    require(safe_regular(root / "infrastructure" / "terraform" / "public_https_ecs_service.tf"),
            "Expected CP9 ECS blueprint missing")


def stage(root: Path) -> str:
    """Create or verify a local candidate folder; never overwrite mismatched files."""
    secure_defaults_present(root)
    model, original_manifest, meta = validate_source(root)
    planned_manifest = build_candidate_manifest(checksum(original_manifest), meta)
    output = root / "artifacts" / "cp9_cloud_candidate"
    output_model = output / MODEL_NAME
    output_manifest = output / OUTPUT_MANIFEST_NAME

    if output.exists() or output.is_symlink():
        require(output.is_dir() and not output.is_symlink(), "Existing staging path is unsafe")
        require(safe_regular(output_model) and safe_regular(output_manifest),
                "Existing staging bundle is incomplete or unsafe")
        require(checksum(output_model) == PINNED_SHA, "Existing staged model has changed")
        require(read_json(output_manifest) == planned_manifest,
                "Existing staging manifest differs; refusing overwrite")
        return "EXISTING CANDIDATE VERIFIED; NO OVERWRITE"

    parent = output.parent
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".cp9_cloud_candidate_", dir=parent) as temp:
        temp_dir = Path(temp)
        shutil.copyfile(model, temp_dir / MODEL_NAME)
        require(checksum(temp_dir / MODEL_NAME) == PINNED_SHA, "Staged model copy changed")
        (temp_dir / OUTPUT_MANIFEST_NAME).write_text(
            json.dumps(planned_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temp_dir, output)
    return "NEW UNAPPROVED CANDIDATE STAGED"


def main() -> None:
    require(Path.cwd().resolve() == ROOT.resolve(), "Run from Project 12 repository root")
    print("PROJECT 12 — CP9 PORTABLE CLOUD CANDIDATE STAGING")
    print("=" * 56)
    result = stage(ROOT)
    print("Status:", result)
    print("Model name: p09-attrition-gb / version 1")
    print("Model SHA-256:", PINNED_SHA)
    print("Staging directory:", OUTPUT)
    print("Approval status: pending_review")
    print("Cloud deployable: NO")
    print("Cloud runtime verified: NO")
    print("RESULT: CP9 CLOUD CANDIDATE STAGED — RELEASE BLOCKED AS INTENDED")
    print("No AWS access, image build, model load, registry changes or approvals occurred.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("RESULT: CP9 CLOUD CANDIDATE STAGING FAILED:", type(exc).__name__, str(exc), file=sys.stderr)
        raise SystemExit(1)
