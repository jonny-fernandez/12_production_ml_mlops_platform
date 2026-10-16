# Project 12 — CP10 consolidated Kubernetes checkpoint

## What CP10 proves

This package replaces the two **existing** Kubernetes starter manifests and adds a namespace, dedicated service account, NetworkPolicy, Kustomize file, offline validator, regression tests, and a PowerShell runner.

The cluster deployment is deliberately **disabled**: `replicas: 0`, a non-resolving placeholder container image digest, and `MODEL_RELEASE_APPROVED=false`. No cloud release, Kubernetes deployment, ECR push, AWS credentials, or production promotion is authorized by this package.

The blueprint reflects CP8 security and model-aware readiness: `/health` for liveness and startup, `/ready` for readiness, a file-backed API secret, and a non-root/read-only container. Model delivery in CP9 is via a separately approved cloud image, not a Windows host volume.

## Install into your existing project

Extract `Project12_CP10_Kubernetes_Consolidated.zip` into your **existing** `12_production_ml_mlops_platform` repository, preserving folders. Replace only:

- `infrastructure/kubernetes/deployment.yaml`
- `infrastructure/kubernetes/service.yaml`

The remaining package files are additions. Do not delete CP1-CP9 files, `.env`, the MLflow DB, or model artifacts.

## One-command verification (PowerShell)

From the Project 12 root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\CP10_VALIDATE_ALL.ps1
```

This runs your full pytest suite, validates Kubernetes safeguards offline, and (if `kubectl` is present) renders the Kustomize blueprint without applying it. If PyYAML is unexpectedly missing, check with:

```powershell
.\.venv\Scripts\python.exe -m pip show PyYAML
```

Install it in Project 12's own venv **only if missing**: `.\.venv\Scripts\python.exe -m pip install "PyYAML>=6,<7"`. Do not install other Kubernetes tools solely for the offline validator.

## Optional kubectl checks

If `kubectl` is installed, this is safe without a cluster:

```powershell
kubectl kustomize .\infrastructure\kubernetes
kubectl version --client
```

Do **not** run `kubectl apply` or create any Secret yet. `kubectl apply --dry-run=client` may still need cluster API discovery; this package intentionally avoids requiring cluster access.

## Security / release constraints

1. The Pod starts with **zero replicas** and a deliberately invalid image digest; it cannot deploy by accident.
2. The read-only container uses UID/GID 10001, drops Linux capabilities, uses `RuntimeDefault` seccomp, no service-account token, and a tmpfs-backed `/tmp`.
3. A Kubernetes Secret called `project12-api-key` is referenced but **not created or populated**. API key values are never committed. Permission mode 0440 relies on the pod `fsGroup` setting and must be verified in a real cluster before serving.
4. `/ready` will refuse traffic if API auth or approved model availability is missing.
5. The `NetworkPolicy` restricts ingress to labeled client pods in this namespace; enforcement requires a compatible CNI plugin. No public Ingress, LoadBalancer, or NodePort is defined.
6. The public HTTPS deployment target remains **AWS ECS/Fargate**, designed in CP9. This Kubernetes blueprint is intentionally standalone and does **not** deploy another public endpoint or create an EKS cluster.
7. Kubernetes manifests are not the release approval; CP11 (cloud deployment) and CP14 (model promotion/rollback) remain separate and require explicit review.

## CP10 completion criteria

- Full local regression suite passes.
- `CP10_validate_kubernetes.py` passes.
- Optional `kubectl kustomize` rendering succeeds if the CLI is installed.
- No Kubernetes resources have been applied.
- No model approval or AWS resource creation occurred.

**Next:** CP11 cloud deployment design/approval review; do not activate any cloud release automatically. The later cloud deployment requires approved image digest, domain and ACM certificate, AWS budget/cost review, scoped IAM and secret provisioning, model approval, and teardown plan.
