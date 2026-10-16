r"""Project 12 / CP9 Step 8: READ-ONLY cloud release safeguard inspection.

Run from Project 12 repository root:
    .\.venv\Scripts\python.exe .\Project12_CP9_cloud_release_preflight.py

This preflight is designed to PASS only when the locally verified, unpromoted
model remains blocked from public AWS deployment. It neither creates a cloud
image nor approves/promotes the model. No AWS credentials/API calls are needed.
It never reads or prints API key values, .env contents, or Terraform secrets.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TF = ROOT / "infrastructure" / "terraform"
MODEL = ROOT / "artifacts" / "cp7_container_model" / "candidate_model_pipeline.joblib"
MANIFEST = ROOT / "artifacts" / "cp7_container_model" / "model_bundle_manifest.json"
SERVING = ROOT / "src" / "mlops_platform" / "serving" / "realtime.py"
COMPOSE = ROOT / "docker-compose.yml"
DOCKERFILE = ROOT / "Dockerfile"
EXPECTED_SHA = "27585a4b8443be29a7cf41a5a2bfd3227ae4a66d8dd947afd88d38111f404d43"
EXPECTED_SOURCE_SHA = "12f9c529ecaffe70f8c1ad401ab398e25b135d8a5ecab6edd71584d65a126755"
EXPECTED_RUN = "0a2731b4c9c64abfb373166e22b1f97e"


def check(ok: bool, title: str) -> None:
    print(f"{'PASS' if ok else 'FAIL'}: {title}")
    if not ok:
        raise RuntimeError(f"Preflight security gate failed: {title}")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for data in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def tf_default(text: str, name: str) -> str | None:
    """Read a simple variable's declaration default, stopping at validation blocks."""
    m = re.search(r'\bvariable\s+"' + re.escape(name) + r'"\s*\{(.*?)(?:\bvalidation\s*\{|\n\})',
                  text, flags=re.S)
    if not m:
        return None
    match = re.search(r'\bdefault\s*=\s*(false|true|"[^"]*")', m.group(1))
    return match.group(1) if match else None


def main() -> None:
    print("PROJECT 12 — CP9 CLOUD RELEASE PREFLIGHT (READ ONLY)")
    print("=" * 56)
    check(Path.cwd().resolve() == ROOT.resolve(), "Run from Project 12 repository root")
    required = (MODEL, MANIFEST, SERVING, COMPOSE, DOCKERFILE,
                TF / "main.tf", TF / "public_https_variables.tf",
                TF / "public_https_ecs_variables.tf",
                TF / "public_https_ecs_service.tf")
    for path in required:
        check(path.is_file() and not path.is_symlink(), f"Required artifact exists: {path.relative_to(ROOT)}")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    check(isinstance(manifest, dict), "Model manifest is a JSON object")
    required_manifest = {
        "format": "project12_verified_local_joblib_v1",
        "model_name": "p09-attrition-gb",
        "model_version": "1",
        "source_mlflow_run_id": EXPECTED_RUN,
        "candidate_status": "candidate_not_promoted",
        "synthetic_data_only": True,
        "operating_threshold": 0.125,
        "candidate_model_sha256": EXPECTED_SHA,
        "source_model_sha256": EXPECTED_SOURCE_SHA,
        "model_filename": MODEL.name,
        "test_records": 507,
    }
    check(all(type(manifest.get(k)) is type(v) and manifest.get(k) == v
              for k, v in required_manifest.items()),
          "Local model identity, threshold, source and candidate-only status locked")
    check(sha256(MODEL) == EXPECTED_SHA,
          "Locally verified model bytes match pinned SHA-256")
    check(isinstance(manifest.get("feature_list"), list) and len(manifest["feature_list"]) == 19,
          "Bundle retains exactly 19 ordered model features")
    check(all(isinstance(manifest.get(k), (int, float)) and
              0 <= manifest[k] <= 1e-8
              for k in ("candidate_frozen_max_difference", "registry_frozen_max_difference")),
          "Stored frozen-prediction parity evidence is within tolerance")

    tf_text = "\n".join(p.read_text(encoding="utf-8") for p in TF.glob("*.tf"))
    for key in ("enable_aws_resources", "enable_public_https", "enable_ecs_deployment",
                "cloud_runtime_verified", "model_release_approved"):
        check(tf_default(tf_text, key) == "false", f"Terraform safety gate defaults false: {key}")

    for key in ("approved_image_digest", "release_approval_reference", "api_key_secret_arn",
                "api_domain_name", "acm_certificate_arn"):
        check(tf_default(tf_text, key) == '""', f"Release prerequisite not hard-coded: {key}")

    ecs_text = (TF / "public_https_ecs_service.tf").read_text(encoding="utf-8")
    check("var.cloud_runtime_verified && var.model_release_approved" in ecs_text,
          "ECS task definition enforces runtime verification and release approval")
    check('readonlyRootFilesystem = true' in ecs_text,
          "ECS task blueprint retains read-only root filesystem")
    check('"APP_ENV", value = "cloud"' in ecs_text,
          "ECS blueprint requests non-local cloud execution")
    check('approved_image_digest' in ecs_text and '@${var.approved_image_digest}' in ecs_text,
          "ECS blueprint requires an immutable image digest")
    check('valueFrom = var.api_key_secret_arn' in ecs_text,
          "ECS blueprint refers to a managed secret ARN, not a secret value")

    serving = SERVING.read_text(encoding="utf-8")
    check('settings.app_env.lower() != "local"' in serving and
          "Unpromoted candidate cannot serve outside local mode" in serving,
          "Current inference loader rejects non-local serving of candidate")
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    check("COPY --chown=10001:10001 src /app/src" in dockerfile and
          "COPY . ." not in dockerfile,
          "Current Dockerfile copies application code, not model bundle")
    compose = COMPOSE.read_text(encoding="utf-8")
    check('APP_ENV: "local"' in compose and 'read_only: true' in compose,
          "Local Docker remains local-only with read-only model mount")

    # Terraform can override variable defaults via *.tfvars, auto.tfvars,
    # environment TF_VAR_*, or CLI arguments. Never claim flags OFF if these
    # external overrides are detected. We neither read nor print their values.
    override_files = [p for p in TF.iterdir() if p.is_file() and
                      (p.name.endswith(".tfvars") or p.name.endswith(".tfvars.json"))]
    override_env = [k for k in os.environ if k.lower().startswith("tf_var_")]
    check(not override_files and not override_env,
          "No Terraform variable override files or TF_VAR environment overrides found")

    print("\nREQUIRED BEFORE ANY CLOUD RELEASE (NOT IMPLEMENTED HERE)")
    print("- Obtain and verify explicit model release approval (candidate is NOT approved)")
    print("- Define reproducible cloud model transport and a reviewed model release manifest")
    print("- Add a separate cloud runtime verification path; preserve checksum and approval gates")
    print("- Demonstrate parity/security tests under APP_ENV=cloud without public deployment")
    print("- Supply approved immutable image digest, domain/certificate, and secret ARN")
    print("- Review AWS IAM, task sizing, public exposure, budget and teardown plan")
    print("\nRESULT: CP9 PREFLIGHT PASSED — CLOUD RELEASE BLOCKED AS INTENDED")
    print("No files written, model loaded, Terraform applied or AWS contacted.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("RESULT: CP9 PREFLIGHT FAILED:", type(exc).__name__, str(exc), file=sys.stderr)
        raise SystemExit(1)
