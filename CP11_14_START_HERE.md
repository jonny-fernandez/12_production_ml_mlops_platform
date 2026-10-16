# Project 12 — CP11–CP14 consolidated handoff

**Status:** CP10 offline Kubernetes checks passed. This handoff supplies the complete remaining code, tests and instructions for CP11–CP14 in one package. It does **not** falsely label a public AWS deployment as completed; the actual deployment remains blocked pending account/domain/certificate, costs and explicit model release approval.

## Installation

Extract the package into the existing `12_production_ml_mlops_platform` directory, preserving paths. Replace these three placeholder files only:

- `src/mlops_platform/monitoring/metrics.py` (preserves the existing `ServiceMetrics` dataclass and error-rate property)
- `src/mlops_platform/monitoring/drift.py`
- `src/mlops_platform/monitoring/performance.py`

Add `src/mlops_platform/deployment/release_gate.py`, the `CP11...CP14...` scripts, the one PowerShell runner, regression tests, docs and synthetic example log data. **Do not overwrite** `.env`, `.secrets`, the MLflow SQLite DB, Docker credentials, existing `artifacts/`, any `.tfstate`, Terraform provider lockfile, or original Project 9 files. The ZIP does not contain any of those.

## Run everything offline in one command

```powershell
cd "C:\Users\Jonny Fernandez\Documents\github files\12_production_ml_mlops_platform"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\CP11_14_VALIDATE_ALL.ps1
```

Expected final line:

`RESULT: CP11-CP14 OFFLINE CHECKS PASSED - NO AWS DEPLOYMENT OR MODEL PROMOTION`

If a check fails, **stop** and share the error rather than bypassing it. The validator never calls AWS, builds Docker images, creates approvals or modifies Terraform flags.

## What this actually demonstrates

| Checkpoint | Offline deliverables | Still requires actual deployment/evidence |
|---|---|---|
| CP11 — AWS deployment | AWS prerequisite preflight; existing ECS/Fargate, VPC, IAM, ALB, ACM ARN, ECR Terraform blueprints; authorized deployment runbook | AWS account/identity, cost confirmation, domain, certificate, secret ARN, **independent release approval**, verified image digest, reviewed `plan/apply`, real HTTPS smoke tests, teardown |
| CP12 — Observability | Deterministic route-level request counts, 5xx, p95 latency and auth-rejection metrics from CP8 sanitized JSON logs | CloudWatch integration and real AWS operational data after CP11 |
| CP13 — Drift/performance | Reference-only PSI, categorical shift incl unseen categories, missing percentages; matured-label evaluation; synthetic retrospective report | Timed production monitoring data and matured labels after deployment; alerts and responsible response |
| CP14 — Promotion/rollback | Deterministic screening, explicit blockers, no-auto-promotion, reviewed rollback plan generator | New candidate for comparison, **independent approvals**, observed staged rollout, real ECS rollback drill |

**Safety:** A technically passing checkpoint does not approve use of a synthetic attrition classifier for actual employee decisions. Its limited predictive performance remains documented (test ROC-AUC approx. 0.616, positive precision ~16%).

## Individual commands (also executed by combined runner)

```powershell
.\.venv\Scripts\python.exe .\CP11_PREFLIGHT.py
.\.venv\Scripts\python.exe .\CP12_OBSERVABILITY_REPORT.py
.\.venv\Scripts\python.exe .\CP13_DRIFT_REPORT.py
.\.venv\Scripts\python.exe .\CP14_RELEASE_REVIEW.py
.\.venv\Scripts\python.exe .\CP14_ROLLBACK_PLAN.py
```

CP12 example input is a metadata-only synthetic log. For post-deployment runs, export **sanitized JSON access logs only** and use `CP12_OBSERVABILITY_REPORT.py --input path/to/metadata.jsonl`. Never give logs with PII, raw inputs, query strings, or auth headers.

CP13 uses Project 9 synthetic snapshots and frozen test predictions to test calculations; this is **not** monitoring of live AWS data. The `outputs/` reports are Git-ignored.

CP14 review deliberately yields **BLOCKED** with missing security review and independent release approval. It never mutates the MLflow Registry or AWS.

## Release instructions

Read `docs/CP11_AWS_DEPLOYMENT_AND_COST_RUNBOOK.md` for the future AWS sequence and blocking requirements. No `terraform apply`, `aws ecs update-service`, or `docker push` runs automatically.

At completion of these offline steps, treat CP12/13/14 as **offline implementation ready**, not production-validated. CP11 cannot be closed as an *actual AWS deployment* until the prerequisites are supplied and an explicitly approved cloud deployment is verified. CP15–CP17 then cover CI/CD, security/load audits, final screenshots Word document and GitHub publication.
