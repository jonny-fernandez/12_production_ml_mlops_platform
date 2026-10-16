# Project 12 — Implemented Architecture and Deferred Cloud Design

## Verified local data flow

1. Project 9 generated a **synthetic** workforce snapshot dataset and produced a fitted preprocessing and Gradient Boosting pipeline.
2. Project 12 CP2 and CP3 verified source checksum, the original 19-feature schema, 0.125 threshold, and prediction parity across 507 frozen test records. A separate training run produced a pinned candidate.
3. Project 12 CP4 logged runs in a local SQLite-backed MLflow store and registered candidate `p09-attrition-gb/1` (`candidate_not_promoted`).
4. FastAPI serves `/health`, `/ready`, authenticated `/model/info`, `/predict`, and `/predict/batch`. `/predict/batch` handles 1–1000 records, preserving input order; invalid records reject the entire request.
5. Docker local serving uses a SHA-256-verified, read-only model bundle, file-backed API key, non-root UID, read-only root filesystem, localhost host binding, and allowlisted JSON request logs. The local bundle and secret are **excluded** from Git and the image build context.
6. CP12–CP14 operate as **offline** service-metrics, drift, and review/rollback exercises; CP15–CP17 add CI definitions, failure tests, documentation, and screenshot evidence.

## AWS ECS/Fargate architecture — designed, NOT deployed

```text
Client -> custom domain HTTPS:443 / ACM -> public ALB (2 AZ subnets)
        -> ALB-only ingress SG -> ECS Fargate FastAPI:8000
                                      |
                                     ECR immutable digest
                                     Secrets Manager key ARN
                                     CloudWatch aggregate metadata logs
```

Terraform defines networking, ECR, ECS cluster/task/service, IAM roles, ALB/HTTPS, logging, and optional DNS. The Terraform resource flags are false by default. A real release additionally requires an owned domain, issued ACM certificate, Secrets Manager secret, reviewed cost/budget/teardown, ECR digest and independent model approval.

The cloud loader requires a separate `release_approval.json` and exact reviewed approval reference before loading verified model bytes. Current candidate approval is `pending_review`; it may **not** serve in cloud mode. A hash proves integrity but does not replace independent provenance review or a signed attestation.

## Offline Kubernetes blueprint — NOT deployed

`infrastructure/kubernetes/` contains constrained manifests, zero replicas, an immutable-image placeholder, probes, Service, Namespace, ServiceAccount and NetworkPolicy. Offline tests check the manifests; no cluster deployment has been claimed. ECS/Fargate remains the selected AWS hosting design.

## Operational and trust boundaries

- Synthetic source data and the local MLflow database are **not** public repository assets.
- Docker local API is **not** internet-accessible; remote serving must use independently reviewed image and credentials.
- `/health` proves process liveness; `/ready` also checks security config and pinned-model availability.
- The model was not independently certified for real employment actions. Do not use it for decisions about real people.
- CP13 PSI/monitoring is synthetic proof-of-function, not live drift or a fairness certificate.
- Actual release/canary and rollback are governed separately, with CP11/CP14 still pending live execution.

See `docs/MODEL_CARD.md`, `docs/CP11_AWS_DEPLOYMENT_AND_COST_RUNBOOK.md`, `docs/INCIDENT_RESPONSE.md`, and `docs/ARCHITECTURE_DECISIONS.md`.
