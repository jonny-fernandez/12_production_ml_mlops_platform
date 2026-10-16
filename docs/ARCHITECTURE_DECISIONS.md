# Project 12 — Architecture Decisions

| Decision | Rationale | Trade-off / limitation |
|---|---|---|
| Reuse Project 9's validated fitted pipeline | Keeps Project 12 about MLOps instead of a new modeling exercise; frozen output parity is measurable | Synthetic classifier precision is ~16%; not useful for real employment decisions |
| Pin scikit-learn 1.7.2 and joblib 1.5.3 | Saved-model format and reproducibility | Complete transitive dependency locking/SBOM remains future hardening |
| Use local MLflow + SQLite | Reproducible experiment/run metadata with no AWS charges | Local database isn't a scalable or HA cloud registry |
| Use FastAPI with strict schemas | Same feature contract for single and batch prediction; errors are explicit | Missing-value imputation within the original fitted pipeline is not exposed as a loose API acceptance policy |
| Use a read-only Docker model bundle for local inference | Separates source control from binary data; verifies bytes before deserialization | Joblib/pickle must never be loaded from untrusted sources |
| Require API key for Docker predictions | Exercised 401/200 behavior without embedding secrets | Not a replacement for enterprise identity, MFA, or per-user scopes |
| Keep `/health` and `/ready` separate | Avoids claiming a model is available when only the process is running | Readiness can be more expensive than basic liveness |
| Choose AWS ECS/Fargate for proposed public HTTPS demo | Avoids a managed Kubernetes control plane for a small single-service portfolio app | Single-task design isn't highly available; public ALB/IP addresses incur idle charges |
| Keep Kubernetes separate and offline | Demonstrates manifest and security design without duplicate live orchestrators | Does not establish hands-on EKS operations |
| Disable all cloud resources by default | Prevents accidental bills and bypass of model review | Actual AWS deployment, telemetry and costs remain unverified |
| Use independent release reference + pinned digest | Prevents silently treating staged candidates as approved | Current approval JSON isn't cryptographically signed; independent review remains necessary |
| Make CI read-only and deploy workflow review-only | Runs tests and static checks without unsafe autonomous deployment | GitHub Actions results require an actual published repository and workflow run |

These are **implemented decisions or documented blueprints**, not claims that the AWS deployment has occurred. Review `docs/CP11_AWS_DEPLOYMENT_AND_COST_RUNBOOK.md` before proposing any live deployment.
