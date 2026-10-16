# Project 12 — Incident Response and Recovery Runbook (CP16)

**Status:** Local/offline response plan. No live AWS incident drill has been performed.

## Detection and SLO review

Monitor `/ready` health failures, unexpected HTTP 5xx, request latency, authorization 401 trends, model artifact integrity, task health, and late-arriving drift/performance reports. CP12 outputs local SLI summaries only; production SLOs, an error budget, paging ownership, and alert thresholds require explicit review before any public release.

## Severity policy (proposed)

| Severity | Signal | Initial response |
|---|---|---|
| SEV1 | Unauthorized data exposure, compromised secrets, incorrect model version | Restrict ingress, disable compromised secret, preserve evidence, notify responsible owner; keep deployment blocked |
| SEV2 | Sustained 5xx, `/ready` not healthy, task crash | Check ECS/task/ALB status, container logs, load balancer target health; prepare rollback |
| SEV3 | Elevated latency, PSI warning without measured degradation | Investigate safely, compare baselines and mature labels, avoid unapproved retraining |

## Verified local response commands

From repository root, use `docker compose ps` and `docker compose logs --tail 100 api`. After a configuration change, `docker compose up -d --wait --wait-timeout 120 api` checks readiness. `CP16_RELIABILITY_AUDIT.py` rehearses simulated model outage and recovery using an in-process fake model. It **never touches AWS or production credentials**.

## Live AWS response (documentation only, not yet validated)

Review CloudWatch logs, ECS task/service events, ALB target group health, recent image digest, CloudTrail, and Secrets Manager rotation history. Do not place secrets, request bodies, personal identifiers, or raw feature values into incident reports. Obtain the incident owner's release/rollback authorization **before** any `aws ecs update-service` or `terraform apply`. Verify a known-good pinned task-definition ARN, canary/healthy rollout plan, and post-rollback prediction parity. CP14 rollback script only generates review instructions; it does not execute them.

## Evidence and postmortem

Record UTC start/end, impact, alert source, sanitized request counts and durations, affected model/image/task versions, approved actions, rollback decision, validation evidence, follow-up regression tests, and owners. Avoid any employee data. Final AWS recovery certification is **pending live exercise**.
