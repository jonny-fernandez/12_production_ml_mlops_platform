# Project 12 — CP15–CP17 Consolidated Engineering Handoff

## Scope and limits

This package extends the existing project without touching the fitted Project 9 model, MLflow Registry, secure local Docker loader, or live AWS infrastructure. It implements **offline CI/CD safety checks, local failure and recovery exercises, documentation, repository hygiene checks, and screenshot assembly**. The pending live AWS deployment (CP11), genuine production monitoring (CP12–13), and approved promotion/rollback (CP14) are **NOT completed by running this package**.

## Installation / path

Extract the ZIP contents into the existing root folder:

`C:\Users\Jonny Fernandez\Documents\github files\12_production_ml_mlops_platform`

Replace only `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`, `docs/MODEL_CARD.md`, `docs/INCIDENT_RESPONSE.md`, and `docs/SCREENSHOT_PLAN.md`; other contents are new. Do not overwrite `.env`, `.venv`, MLflow databases, any real Docker secret, or models.

## One-command local validation (Windows PowerShell 5.1)

```powershell
cd "C:\Users\Jonny Fernandez\Documents\github files\12_production_ml_mlops_platform"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\CP15_17_VALIDATE_ALL.ps1
```

The script runs the full pytest suite, CP15 CI/release safety, CP16 synthetic in-process reliability/security/recovery tests, CP17 evidence inventory, Terraform format/init/validate. It **does not run** AWS commands, `terraform apply`, ECR push, model promotion, or GitHub commits.

Expected terminal line:

`RESULT: CP15-CP17 OFFLINE VALIDATION PASSED - LIVE AWS RELEASE AND GITHUB PUBLICATION BLOCKED`

### CP15 deliverables

- `.github/workflows/ci.yml`: read-only GitHub Actions jobs for Python tests, local-only reliability, Terraform static verification, Docker build.
- `.github/workflows/deploy.yml`: manually triggered **review only**. No AWS credentials, no deployment, no promotion.
- `CP15_RELEASE_GATE.py`: safety-control report at `outputs/cp15_release_gate.json`.

CI is **not verified running on GitHub** until a real workflow is executed in a GitHub repository. GitHub Actions service and runner costs/quotas vary by account. Python dependencies currently have top-level pins but not a fully resolved transitive lock; production-grade reproducibility should later record resolved SBOM and digest-pinned base images. Current third-party GitHub Actions tags are version tags, not SHA-locked, and should be hardened before release.

### CP16 deliverables

- `CP16_REPOSITORY_AUDIT.py`: optional tracked-file review, ignored-secret checks, dependency pin check, and explicitly deferred Git audit when no repository exists.
- `CP16_RELIABILITY_AUDIT.py`: bounded 40-request in-process test using fake model input and fake API credential. Verifies auth rejection, invalid-input failure, `/ready` outage and recovery, structured log privacy, and p95 fixture latency. Writes `outputs/cp16_reliability_audit.json`.
- `tests/test_cp15_17.py`: permanent regression tests for release safeguards, deterministic audit metadata, fail-closed behavior, and screenshot readiness.

The synthetic latency figure is **not production throughput or an AWS SLO**. Before live release, define an approved SLO and run an appropriately authorized load/chaos exercise on an isolated environment, with bounded traffic and alerts.

### CP17 deliverables

- `docs/MODEL_CARD.md`: evidence-based model card; real-world HR use prohibited.
- `docs/INCIDENT_RESPONSE.md`: local verified steps and proposed AWS response procedure.
- `docs/SCREENSHOT_PLAN.md`: precise numbered filenames and descriptions.
- `CP17_EVIDENCE_AUDIT.py`: inventory of required PNGs and Word handoff; by design keeps publication blocked.
- `CP17_BUILD_SCREENSHOT_DOC.py`: assembles real images into a Word screenshot handoff **only once the PNGs exist**. No synthetic screenshots.

Before final GitHub publication: resolve outstanding CP11–14 requirements or clearly document deployment as unimplemented, finish technical audit, collect screenshots, generate and review screenshot Word document, **wait for user confirmation**, finalize README, inspect Git ignores/credentials/PII, then commit and publish with permission.

## Deferred live release prerequisites

1. AWS identity and approved narrow IAM permissions.
2. Owned HTTPS hostname, issued ACM certificate, verified ALB routing.
3. ECR SHA256 image digest, approved model-release record and immutable manifest.
4. Secrets Manager key, separate execution/application roles, public-exposure review.
5. Reviewed Terraform plan, monthly spending budget and explicit cost approval.
6. Actual ECS smoke/canary, live logs, rollback drill and independent sign-off.

Use `docs/CP11_AWS_DEPLOYMENT_AND_COST_RUNBOOK.md` for the previously prepared plan. Offline validation cannot substitute for real deployment approval.
