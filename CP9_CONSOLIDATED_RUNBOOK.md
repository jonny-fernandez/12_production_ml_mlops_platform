# Project 12 — CP9 consolidated handoff (all remaining local work)

**Scope:** AWS Infrastructure as Code (ECS/Fargate, ALB HTTPS, VPC, IAM, ECR,
CloudWatch, Secrets Manager reference, optional Route 53 DNS). No AWS deployment,
model promotion or expenditure is authorized by this package. CP11 will cover
actual AWS deployment; CP14 will cover candidate promotion/rollback.

**Required baseline:** CP1–CP8 completed; CP9 Step 11 candidate rehearsal passed;
Project 12 Python 3.12 `.venv`, Terraform 1.16.5, and the generated
`artifacts/cp9_cloud_candidate` exist on your Windows machine.

## Files in this package

Replace these three existing files, preserving directory structure:

- `src/mlops_platform/config.py` — adds cloud approval configuration, false by default.
- `src/mlops_platform/serving/realtime.py` — retains local serving; verifies approved cloud artifacts before cloud inference.
- `infrastructure/terraform/public_https_ecs_service.tf` — passes the exact reviewed release reference and approval opt-in to ECS runtime.

Add these files:

- `src/mlops_platform/serving/cloud_release.py` — independently checked approval record, provenance, checksum, and safe deserialization gate.
- `Dockerfile.cloud` — self-contained cloud image design; only use assembled reviewed build context.
- `Project12_CP9_prepare_cloud_image.py` — defaults to a safe, read-only preflight. An approved image context needs a separate review record.
- `tests/test_cp9_release_controls.py` — regression tests for cloud approval failure conditions.
- `infrastructure/terraform/public_https_dns.tf` and `public_https_dns_variables.tf` — optional Route 53 ALB alias, OFF by default.
- `CP9_RELEASE_APPROVAL_TEMPLATE.json` — intentionally unapproved. This is **not** a release approval.
- `CP9_SAFE_DEFAULTS.tfvars.example` — illustrative false-only variables; never automatically applied.
- `CP9_VALIDATE_ALL.ps1` — a single command runs the local pytest and Terraform checks.

**Never overwrite:** the original model, any `artifacts/` folder, the real
`.env`, `.secrets`, the MLflow database, `terraform.tfstate`, or
`.terraform.lock.hcl`.

## Do all remaining offline CP9 checks (one batch)

Open PowerShell in:

```powershell
cd "C:\Users\Jonny Fernandez\Documents\github files\12_production_ml_mlops_platform"
terraform -chdir=".\infrastructure\terraform" fmt
.\CP9_VALIDATE_ALL.ps1
```

If your PowerShell execution policy blocks running the file, execute just that
script for this process without changing machine policy:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\CP9_VALIDATE_ALL.ps1
```

The validator runs the full pytest suite, validates the staged model, checks
that the cloud release is blocked, and runs Terraform `fmt -check`, `init`
(`-backend=false`, `-lockfile=readonly`) and `validate`. It does not call AWS.
Expected final line:

`RESULT: CP9 OFFLINE VALIDATION PASSED — DEPLOYMENT DISABLED`

If any check fails, **stop** and share the error. Do not enable any Terraform
resource flag to make the test pass.

## Release architecture and cost controls

```text
Browser / API client
   | HTTPS (valid custom hostname + ACM cert)
Application Load Balancer (public, two AZs)
   | HTTP 8000 (security-group-to-security-group only)
ECS / Fargate (one task; public IP outbound; no open inbound except ALB)
   |--> ECR immutable digest
   |--> AWS Secrets Manager API key (task EXECUTION role)
   |--> CloudWatch JSON request metadata logs
```

This is a single-task demonstration, **not HA**. Start with 0.5 vCPU / 1 GiB
only if validated against load; use 1 vCPU / 2 GiB if necessary. A public ALB,
Fargate and public IPv4 charge even when usage is low. Previous preliminary
budget was ~$50–60/month for 0.5 vCPU / 1 GiB and light traffic, **not a cap
or price quote**. Domain registration, taxes, data transfer, WAF and other
resources are extra. Before deployment, confirm current AWS prices and create
alerts at e.g. $25, $50, and $75 (alerts are not hard spending limits). Define
a teardown plan and schedule. Region `us-east-1` is the current default.

The ECS task uses a public IP for outbound AWS service access to avoid NAT
Gateway cost, but the security group only permits inbound port 8000 from the
ALB. For a hardened, private-subnet production setup, review NAT/VPC endpoints,
WAF, scaling, network egress and multi-AZ high availability separately.

## Domain and certificate (future AWS setup, not run in CP9)

An ALB `amazonaws.com` DNS name cannot substitute for a cert valid for an
owned hostname. Obtain/control a domain or subdomain (e.g. `api.example.com`),
validate an ACM public cert in `us-east-1`, and either create DNS externally or
turn on `manage_api_dns` with an already-owned Route 53 hosted zone. Never put
private certificate keys into Terraform.

## Review and model approval (future, NOT automatic)

`artifacts/cp9_cloud_candidate` is `pending_review` and not cloud deployable.
It must remain so until **explicit independent model-release approval**.
The supplied JSON template says `approved: false`. An external, reviewed
record must document the actual reviewer, date, approval ID, exact candidate
manifest hash, target and model hash. The human review should include model
performance limitations (precision ~16%, ROC-AUC ~0.616), model cards,
allowed synthetic-only use, security findings and rollback criteria. The model
must never be advertised as appropriate for actual employment decisions.

The approval JSON is **process evidence**, not cryptographic proof of identity.
Approval must also be enforced organizationally and by the immutable ECR digest,
scoped IAM, release gates and CI reviews. Stronger signed attestations may be
added in CP16.

Inspecting the candidate again (safe, no approval):

```powershell
.\.venv\Scripts\python.exe .\Project12_CP9_prepare_cloud_image.py
```

After a future explicit approval and review ONLY (not during current CP9):

```powershell
# Store the independently approved manifest OUTSIDE Git, e.g.:
# .secrets\release_approval.json
# The approval-reference parameter must match the independently reviewed record.
$env:PROJECT12_RELEASE_REVIEW_ACK = "YES_REVIEWED"
.\.venv\Scripts\python.exe .\Project12_CP9_prepare_cloud_image.py --assemble --approval-file .\.secrets\release_approval.json --approval-reference REVIEW-CHANGE-0001
Remove-Item Env:\PROJECT12_RELEASE_REVIEW_ACK
```

The script refuses existing destination overrides and checks approval before
copying anything into `artifacts/cp9_cloud_image_context`. It creates **no
approval and no Docker image**. Only after authorization, locally build:

```powershell
# This is for a future independently approved release — do not run it now.
docker build -f .\artifacts\cp9_cloud_image_context\Dockerfile -t project12-attrition-api:release-review .\artifacts\cp9_cloud_image_context
```

The approved runtime will require `APP_ENV=cloud`, `AUTH_REQUIRED=true`,
`MODEL_RELEASE_APPROVED=true`, `MODEL_BUNDLE_DIR=/app/model`, and a matching
`MODEL_RELEASE_APPROVAL_REFERENCE`. The API key must come from Secrets Manager
(or a local test secret), never from the Docker image. `/ready` must only
return 200 when secret validation and approved-model loading succeed.

## AWS rollout commands (REFERENCE ONLY — NOT authorized by this package)

1. Have a real AWS account, domain, cert, image digest, secret ARN, model
   approval and reviewed spending limit. Do not run a release against personal
   unknown accounts. Review IAM permissions and cost estimates first.
2. From the AWS account you intentionally chose: provision only needed
   resources with a reviewed, saved Terraform plan (`terraform plan -out`),
   confirm the complete resource diff, and perform `terraform apply` only after
   an explicit go-ahead. ECR foundation might be provisioned before the service;
   keep `enable_ecs_deployment=false` until image digest exists.
3. Push the approved image to ECR using a tag, confirm the **actual ECR digest**
   (not a local tar hash), set the ECS image `repository@sha256:...`, and
   replan/review the service; never use `latest` as the release identity.
4. Configure the secret in AWS Secrets Manager using the AWS console or
   approved secret workflow (not Terraform variables or CLI history). Reference
   only its ARN in Terraform. Rotate the secret and restart tasks when needed.
5. After independent approval, run a plan with `enable_aws_resources=true`,
   `enable_public_https=true`, and finally `enable_ecs_deployment=true` only
   after all prerequisites are confirmed, including DNS/certificate matching
   and cloud-runtime parity tests. Never flip flags to silence checks.
6. Smoke test `/health`, `/ready`, authenticated `/predict`, and
   `/predict/batch` on the HTTPS hostname using synthetic data. Verify 507-row
   parity, unauthorized 401, invalid input 422, observability, circuit breaker,
   and rollback. Never upload sensitive employment data.
7. Destroy the approved demo infrastructure after review, verifying every
   chargeable resource and retained asset. `terraform destroy` is destructive;
   do not execute without an explicit scope and authorization review.

These actions belong to CP11 (AWS deployment), with release approvals and
promotion checks further exercised in CP14. CP9 finishes after *offline IaC
validation*, not by turning an unapproved model into a public endpoint.

## Evidence for screenshots (later CP17)

Save the final successful `CP9_VALIDATE_ALL.ps1` output, Terraform validation,
no-AWS-release preflight, and infrastructure diagram in the final screenshot
inventory. The completed screenshot Word document and publication flow occur
at CP17, before GitHub publication.
