# Production ML, Cloud Deployment & MLOps Platform

> **Portfolio engineering demonstration — validated locally; not an active AWS deployment.** The registered model is a **synthetic-data candidate**, not approved for live cloud serving or real employment decisions.

Project 12 takes a fitted classifier from Project 9 (`09_ai_attrition_prediction`) and develops the operational machinery around it: reproducible training, MLflow provenance, authenticated REST inference, batch processing, hardened Docker serving, cloud infrastructure blueprints, monitoring exercises, and controlled model release gates. The core design principle is that **model predictions and evaluation are computed by deterministic code, not invented by an LLM**.

## Verified implementation status

| Area | Evidence and status |
|---|---|
| Reproducible model training | A separately trained Gradient Boosting pipeline reproduced the Project 9 frozen probabilities to floating-point tolerance; original artifact preserved. |
| MLflow | Local SQLite-backed experiment and model registry; registered `p09-attrition-gb` **version 1**; candidate **not promoted**. |
| REST serving | FastAPI `/health`, `/ready`, `/model/info`, `/predict`, `/predict/batch`; strict 19-feature schema and 1–1,000 batch records. |
| Local container | Python 3.12, non-root user, read-only root filesystem/model mount, localhost-only host binding, file-backed API key, and request-metadata-only logging. |
| Inference parity | Replayed **507 frozen synthetic test records** via model pipeline, in-process API, and local Docker HTTP; output probabilities agree within numerical tolerance. |
| AWS/Terraform | Terraform design for ECR, ECS/Fargate, ALB with HTTPS/ACM, VPC, security groups, IAM, CloudWatch, and optional DNS; **offline validated, not applied**. |
| Kubernetes | Deployment/Service and security manifests with offline checks; **no Kubernetes cluster deployment**. |
| Monitoring | Offline request/latency reporting and synthetic PSI / historical-performance diagnostics; **no live AWS telemetry**. |
| Promotion/rollback | Review gates and rollback planning run offline; **model approval and real rollback not performed**. |
| CI/CD | GitHub Actions workflows defined to test Python, Terraform, and a local-only Docker build; **an actual GitHub-hosted run must be checked after publication**. |
| Reliability/security | Offline failure-injection, model-unavailability recovery, local authorization tests, and repository audit tools. |
| Screenshot evidence | Eight numbered screenshots in `screenshots/final/` with a separately generated Word handoff for prepublication review. |

The verified Windows local test run captured in `screenshots/final/01_full_pytest_suite.png` reported **201 passed, 1 skipped** at the time of capture. Subsequent changes or another environment require rerunning the suite; that screenshot is not proof of a future CI run.

## Model contract and observed performance

- **Model:** fitted scikit-learn `GradientBoostingClassifier` with original preprocessing from Project 9.
- **Task:** synthetic `attrition_within_90_days` classification.
- **Features:** 19 ordered input fields (14 numeric, 5 categorical); identifiers, labels, and post-outcome information are excluded from inference.
- **Decision threshold:** `0.125`, selected on validation data, not the final test set.
- **Frozen test set:** 507 records; confusion matrix `TN=358`, `FP=99`, `FN=31`, `TP=19`.
- **Source model SHA-256:** `12f9c529ecaffe70f8c1ad401ab398e25b135d8a5ecab6edd71584d65a126755`.
- **Reproduced candidate SHA-256:** `27585a4b8443be29a7cf41a5a2bfd3227ae4a66d8dd947afd88d38111f404d43`.

| Metric | Project 9 frozen test result |
|---|---:|
| ROC-AUC | 0.6156 |
| PR-AUC | 0.1994 |
| Brier score | 0.0872 |
| Precision | 16.10% |
| Recall | 38.00% |
| F1 | 0.2262 |

These are **historical synthetic-data results**, not measurements of the Docker container or public cloud. Precision is low: the classifier is **not suitable for real-world hiring, disciplinary, retention, or other employment decisions**. See [`docs/MODEL_CARD.md`](docs/MODEL_CARD.md) for provenance and limitations.

## Architecture

```text
Project 9 synthetic source + locked model
         |
         +--> CP3 reproducible training + SHA-256 / parity checks
         |                 |
         |                 +--> CP4 MLflow / local SQLite registry
         |                                   |
         +------------------------------> verified local bundle
                                             |
                                  FastAPI (Python 3.12)
                               /health | /ready | /predict
                                               | /predict/batch
                                             |
                              Authenticated local Docker API
                        (non-root, read-only, localhost-bound)
                                             |
                     Offline evidence and release-safety controls
                        /                       |                   \
                CP12/13 reports         CP14 approval gate       CP16 audit

Separate, NOT DEPLOYED blueprint:
 HTTPS custom hostname -> ACM / public ALB -> ECS Fargate
                                   |-> ECR immutable image digest
                                   |-> Secrets Manager reference
                                   |-> CloudWatch log group
```

The cloud blueprint intentionally **does not inherit local Windows mounts or local SQLite files**. It requires a separately approved self-contained model image, verified approval provenance, an immutable ECR digest, security review, owned DNS/certificate, and explicit cost authorization. Details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/CP11_AWS_DEPLOYMENT_AND_COST_RUNBOOK.md`](docs/CP11_AWS_DEPLOYMENT_AND_COST_RUNBOOK.md).

## Run the offline validation

**Environment:** Windows PowerShell and Python 3.12, with Docker Desktop and Terraform 1.16.5 for the corresponding checks. Python dependencies used for serving are declared in `requirements-container.txt`; integration tests additionally need test packages and the local Project 9/MLflow artifacts. The original model files, training data, `.env`, API secret, and MLflow tracking database are **deliberately excluded from this repository**.

```powershell
# From the Project 12 repository root
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-container.txt
.\.venv\Scripts\python.exe -m pip install "pytest==9.1.1" "PyYAML==6.0.3"

# Safe offline checks; these do not deploy or approve a model
.\.venv\Scripts\python.exe -m pytest -o addopts="" -q --disable-warnings -p no:cacheprovider
.\.venv\Scripts\python.exe .\CP15_RELEASE_GATE.py
.\.venv\Scripts\python.exe .\CP16_REPOSITORY_AUDIT.py
terraform -chdir=".\infrastructure\terraform" fmt -check
terraform -chdir=".\infrastructure\terraform" init -backend=false -input=false -lockfile=readonly
terraform -chdir=".\infrastructure\terraform" validate
```

An environment without the **original external Project 9 artifacts** or **local registered MLflow model** may skip source-dependent integration tests. Do not interpret such skips as proof that prediction parity ran in CI. To reproduce the local complete run, restore the verified Project 9 files and follow the CP3/CP4 scripts and runbooks; never substitute an unverified joblib artifact.

### Local authenticated Docker demonstration (only with trusted local artifacts)

The local container expects a verified model bundle (`artifacts/cp7_container_model`) and a file-backed API secret created locally. Neither is shipped in Git. After reproducing the model and exporting the bundle, use:

```powershell
.\.venv\Scripts\python.exe .\CP8_create_local_secret.py

docker compose up -d --build --wait api
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
```

Inference routes require a valid API key. Use `Project12_CP8_docker_auth_http_check.py` to test authorization and all 507 frozen predictions; it reads the local test secret without printing it. **Do not expose port 8000 to the internet or commit `.secrets/`.** `docker compose down` stops the local service.

## Evaluation and governance

- **Contracts:** Missing/extra fields, unknown categories, wrong input types, NaN/infinity, empty/oversized batches are rejected with HTTP 422; model-unavailable errors return 503. Authentication rejects missing or wrong keys (HTTP 401 when enabled).
- **Readiness:** `/health` checks process liveness; `/ready` checks key configuration and the model loader. They have deliberately different meanings.
- **Reproducibility:** Locked source/candidate checksums, fixed threshold, frozen test predictions, recorded training splits/versions, registered model lineage.
- **Logging:** Allowlisted request identifiers, route, method, status and duration; no raw personnel data or credential values in structured logs.
- **Monitoring:** CP12 service metrics and CP13 synthetic drift report are proof-of-function only, not production SLIs/SLOs or measured AWS load.
- **Release:** CP14 checks remain fail-closed; the candidate has **not** been independently approved. Automated CI is review/test-only, not a cloud deployment pipeline.
- **Security limitations:** Joblib uses pickle deserialization; verify pinned trusted bytes before loading. Digest checks establish file integrity, not cryptographic approval or source authenticity. Production hardening would additionally include provenance signing, runtime identity, deployed monitoring and independent security review.

## Repository map

```text
.github/workflows/         CI and release-review-only workflows
configs/                   Model and deployment starter settings
docs/                      Model card, architecture, incident response, runbooks
infrastructure/terraform/   Offline-validated AWS design (disabled by default)
infrastructure/kubernetes/  Offline-validated Kubernetes manifests
src/mlops_platform/         API, serving, training, registry, governance, monitoring
tests/                      Contract, training, registry, API, security, cloud gates
screenshots/final/          Eight real, numbered evidence PNGs
CP*_*.py / CP*_*.ps1       Offline checkpoint verification utilities
Dockerfile                 Local hardened FastAPI container
Dockerfile.cloud           Approval-gated cloud-image blueprint
requirements-container.txt Pinned top-level serving dependencies
```

`artifacts/`, `data/raw/`, `outputs/`, `.secrets/`, `.env`, `.venv`, MLflow databases, Terraform state and cloud approval records are **not published**. See `.gitignore`, `.dockerignore`, and [`docs/DEPLOYMENT_RUNBOOK.md`](docs/DEPLOYMENT_RUNBOOK.md).

## Evidence screenshots

| Evidence | File |
|---|---|
| Pytest summary | [01](screenshots/final/01_full_pytest_suite.png) |
| Terraform validation | [02](screenshots/final/02_terraform_validation.png) |
| MLflow registered version | [03](screenshots/final/03_mlflow_registered_model.png) |
| Hardened Docker service healthy | [04](screenshots/final/04_docker_container_healthy.png) |
| Authenticated 507-row parity | [05](screenshots/final/05_secured_prediction_parity.png) |
| Synthetic drift exercise | [06](screenshots/final/06_cp13_drift_report.png) |
| Offline reliability exercise | [07](screenshots/final/07_cp16_reliability_audit.png) |
| Local CI configuration (not a completed GitHub run) | [08](screenshots/final/08_cp15_ci_configuration.png) |

The screenshot Word handoff was reviewed **before** GitHub preparation; it is a local artifact, not required in the public repository.

## Current limitations / future work

1. **Not deployed to AWS** — no live public HTTPS domain, ECS service, CloudWatch dashboard or cost/teardown evidence.
2. **No approved production model** — CP14 and cloud-release controls intentionally block promotion; the fitted classifier's synthetic precision limits real-world applicability.
3. **Offline monitoring only** — real drift monitoring requires representative live distributions and matured outcomes; this project does not claim such data.
4. **Offline Kubernetes and CI definition** — no cluster deployment or GitHub Actions execution evidence at the time this README was prepared; CI results must be reviewed after push.
5. **Reproducibility hardening** — top-level serving pins are not a full transitive lock/SBOM; base images and third-party GitHub Actions are not SHA-pinned.
6. **Single-task AWS design only** — not a production HA or disaster-recovery guarantee; public networking, TLS, budgets, IAM and independent review remain deployment prerequisites.

**Publication is source-and-evidence only.** Publication of the repository does not authorize AWS creation, joblib from untrusted sources, employee-data inference, or model promotion.
