# Project 12 — Evaluation Evidence and Remaining Gaps

## Local verified tests

- **Reproducibility:** original and retrained model hash/metadata, 19-feature order, chronological dataset splits, frozen Project 9 507-row prediction parity.
- **Inference correctness:** positive/negative score parity and HTTP responses for 507-row batch, reversed order, 1000-row limit, empty and malformed batches.
- **API security:** authenticated 200, missing/wrong key 401, malformed input 422, unavailable model 503.
- **Container:** non-root UID, read-only root and bundle volume, restricted localhost binding, secure key mounting, restart health recovery, metadata-only logging.
- **IaC and Kubernetes:** Terraform format/init/validate; manifests validated offline, no applied resources.
- **CI/CD controls:** workflow content and read-only release gates tested offline; actual hosted CI run pending first push.
- **Monitoring:** CP12 aggregates of safe request metadata; CP13 synthetic PSI drift plus historical model metrics. No live cloud traffic/labels.
- **Reliability:** bounded synthetic in-process traffic and fail-closed model outage/recovery simulation; not a production load test.
- **Governance:** CP14 refuses promotion pending independent approval; rollback plan is generated only, not executed.

## Model limitations

At a 0.125 validation-selected threshold, the historical 507-record synthetic test set yielded ROC-AUC ~0.616, PR-AUC ~0.199, precision ~16.1%, and recall 38%. These numbers are not representative of real employees and do not support employment decisions.

## Outstanding live tests (not completed)

1. Approved ECS/Fargate public HTTPS deployment with registered domain and ACM certificate.
2. Real CloudWatch, sustained load, error budgets, alerting and cost monitoring.
3. Independent model approval, immutable release provenance, canary deployment, verified rollback.
4. Actual GitHub Actions run and follow-up repository audit after publication.

Never infer success of these items from successful offline checks.
