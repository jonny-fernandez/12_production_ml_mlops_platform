# CP11 — Public HTTPS AWS Deployment: approved-only runbook

**Do not execute this live deployment sequence yet.** The model is `pending_review`; your files do not establish an independently approved cloud release. The commands below are reference commands to use **only after** real AWS account, budget, DNS, certificate, security and approval reviews. This is not a deployment authorization.

## Architecture from CP9

- ECR immutable-image registry; ECS/Fargate one 0.5 vCPU/1 GiB task (validate sizing).
- Application Load Balancer in two public subnets with ACM HTTPS certificate.
- Task public IP used for outbound AWS services; ingress only from ALB security group.
- API-key in Secrets Manager; least-privilege ECS execution role; localhost CP8 behavior retained.
- Approved self-contained model image; `APP_ENV=cloud`, SHA-pinned model and independently reviewed approval JSON, exact ECS image digest.
- CloudWatch structured metadata logs; regional billing alerts and teardown procedures.

## Risks / cost before any apply

- The ALB, Fargate, public IPv4 and optional DNS incur ongoing monthly charges even at zero traffic. Previous **rough planning** estimate was around $50–60/month for 1 task, but it is not a billing cap or a current price quote. Recalculate for your AWS region, usage, traffic, DNS, retained images, budgets and taxes before deployment.
- Verify Domain/Route53 control, issued ACM certificate in the same region, secret ARN, Fargate load requirements and AWS identity. Use a hard end date for a demo and manually verify all assets are deleted after teardown.
- AWS Budgets alerts (e.g. $25/$50/$75) **notify; they do not prevent charges**.
- At least one task in public subnets limits isolation. Production-appropriate private subnets and NAT/VPC endpoints can be assessed separately. Public API-key auth alone isn't enterprise identity control.

## Reference commands — **manual and approved-only**

The steps intentionally contain placeholders; don't copy them as executable deployment defaults.

```powershell
# After explicitly selecting the correct AWS identity/region and permissions:
aws sts get-caller-identity
aws configure get region

# Read-only: check Terraform safe defaults and generated candidate evidence:
.\.venv\Scripts\python.exe .\CP11_PREFLIGHT.py

# Future approval gates: review README/runbook, independent signed or reviewed
# change request, reviewed artifacts/cp9_cloud_candidate manifest, model card,
# source checksum, 507-row parity, security audit and regression results.
# Human review must create its OWN release approval record outside Git.
# See CP9_CONSOLIDATED_RUNBOOK.md for the already implemented approved-context
# assembler. Do NOT modify the unapproved CP9 template to fake approval.

# After external approval only, assemble approved image context using CP9 process.
# docker build -f .\artifacts\cp9_cloud_image_context\Dockerfile `
#   -t project12-attrition-api:review .\artifacts\cp9_cloud_image_context

# Before any apply, prepare off-repo, Git-ignored review-only Terraform .tfvars
# with appropriate values, and compute an exact saved plan for review:
# terraform -chdir=.\infrastructure\terraform plan -input=false `
#   -var-file=<reviewed_private_path.tfvars> -out=<reviewed_plan.tfplan>
# terraform -chdir=.\infrastructure\terraform show <reviewed_plan.tfplan>
# Do NOT run apply without explicit authorization and complete plan review.

# Initial foundation only (ECR) may precede pushing a reviewed image; ensure
# ECS deployment stays disabled until the approved digest exists.
# aws ecr get-login-password --region us-east-1 | `
#   docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com
# docker tag project12-attrition-api:review <account>.dkr.ecr.us-east-1.amazonaws.com/<repo>:<release-id>
# docker push <account>.dkr.ecr.us-east-1.amazonaws.com/<repo>:<release-id>
# aws ecr describe-images --region us-east-1 --repository-name <repo> `
#   --image-ids imageTag=<release-id> --query 'imageDetails[0].imageDigest' --output text

# Record the ECR digest in Terraform, verify existing ACM certificate + domain,
# Secrets Manager secret ARN (never its value), cost review and image approval.
# Build an approval-provenance plan, then re-review before any apply.
```

### Post-release checks (only after deployment is actually approved and running)

1. Public HTTPS DNS/certificate match, TLS policy, ALB access paths, no public task port.
2. `/health` 200, `/ready` 200; unauthenticated `/model/info` and `/predict` 401.
3. Authenticated frozen test replay (507, synthetic only) matches model; batch 1–1000 and invalid 422 rules remain intact.
4. Real CloudWatch service SLIs, drift collection without PII, alarm routing and incident owner.
5. Deployment rollback: verify previous **approved** ECS task definition, not only a Docker tag. Use the CP14 rollback plan generator for review; deployment action requires explicit separate authorization.
6. Stop or scale down when not demonstrating; teardown retained ECR images, ALB, ECS, networking and monitoring when appropriate. Verify final AWS billing.

## Known limitation

With the existing synthetic dataset and model (`precision ~16%`), cloud release should be for a clearly scoped synthetic-only demonstration, not real staffing or adverse employment decisions. The deployment must not claim production business suitability.
