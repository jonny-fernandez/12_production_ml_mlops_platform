# Project 12 — Local Demonstration and Cloud Release Boundary

## A. Offline validation (safe; no AWS)

From the repository root, with Python 3.12 and necessary installed dependencies:

```powershell
.\.venv\Scripts\python.exe -m pytest -o addopts="" -q --disable-warnings -p no:cacheprovider
.\.venv\Scripts\python.exe .\CP15_RELEASE_GATE.py
.\.venv\Scripts\python.exe .\CP16_REPOSITORY_AUDIT.py
terraform -chdir=".\infrastructure\terraform" fmt -check
terraform -chdir=".\infrastructure\terraform" init -backend=false -input=false -lockfile=readonly
terraform -chdir=".\infrastructure\terraform" validate
```

A clone without local MLflow metadata or Project 9 source files may skip some source-dependent integration tests. Record counts/skip reasons. Never claim missing tests passed.

## B. Local Docker API (requires locally reproduced, trusted model)

- Confirm `artifacts/cp7_container_model/` exists and its SHA-256 manifest was generated from the verified, pinned Project 9 candidate.
- Create the file-backed test API key locally with `CP8_create_local_secret.py` (idempotent, never displays the key).
- `docker compose up -d --build --wait api`
- `docker compose ps`, `Invoke-RestMethod http://127.0.0.1:8000/health`, `Invoke-RestMethod http://127.0.0.1:8000/ready`
- Run `Project12_CP8_docker_auth_http_check.py` against the localhost API to verify HTTP 401/200/422 and frozen 507-record parity.
- Stop safely with `docker compose down`.

Docker Compose uses only `127.0.0.1` on the host; the Docker image is not a publicly approved model release. Never commit or display `.env`, `.secrets`, or the model binary.

## C. Kubernetes configuration only

See `CP10_RUNBOOK.md` and `infrastructure/kubernetes/`. Validation is offline and manifests contain zero replicas and unfilled image/release values. Do not deploy those manifests to a cluster without a separate approval and updated image/secret policy.

## D. AWS ECS public HTTPS — proposal, not run

See `docs/CP11_AWS_DEPLOYMENT_AND_COST_RUNBOOK.md` and `CP9_CONSOLIDATED_RUNBOOK.md`. Do **not** execute AWS/ECR/Terraform apply commands until all prerequisites are independently reviewed and an explicit authorization is obtained:

- Synthetic-only approved model, manifest, reviewer and release reference; reviewed immutable image digest.
- Correct AWS account, least-privilege identity, Secrets Manager secret ARN, owned domain and issued ACM certificate.
- Terraform plan reviewed in full; operating budget and teardown plan approved.
- HTTP auth, real HTTPS smoke tests, CloudWatch monitoring, synthetic-record parity and rollback verification planned.

The model approval remains `pending_review`, so cloud deployment is **not authorized**. The CP14 rollback plan is review-only and does not establish a completed rollback exercise.

## E. Before GitHub publication

- Confirm screenshot Word handoff and eight final PNG files were reviewed by the user.
- Run `GITHUB_PREP_AUDIT.py`, review its warnings and Git status/paths.
- Ensure `.env`, `.secrets`, `.venv`, local MLflow DB, raw data, model artifacts, Terraform state, generated outputs, and individual approval records are excluded.
- GitHub Actions results are not available until after publication. Don't insert fabricated CI screenshots.
