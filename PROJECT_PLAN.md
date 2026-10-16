# Project Plan

## Core question

Can a previously validated ML model be operated as a safe, observable, reproducible production service?

## Primary architecture

Validated data/model
-> reproducible training
-> MLflow experiment tracking
-> model registry
-> model approval metadata
-> Docker image
-> FastAPI serving
-> Kubernetes
-> Terraform-managed AWS infrastructure
-> real-time/batch inference
-> logging/metrics/traces
-> drift/performance monitoring
-> candidate evaluation
-> staged promotion or rollback

## AWS-first cloud scope

AWS is the primary cloud for Project 12 to broaden the portfolio beyond the Microsoft ecosystem used later in Project 15.

Potential AWS services should be introduced only when justified:
- ECR for container images
- ECS/EKS or another justified container runtime
- CloudWatch for monitoring
- Secrets Manager / Parameter Store for secrets
- S3 for artifacts where useful

Do not add every AWS service.

## Required engineering themes

1. Model and feature contract
2. Reproducible training metadata
3. MLflow tracking/registry
4. FastAPI serving
5. Docker
6. Batch + real-time inference
7. Terraform
8. Kubernetes
9. Authentication/secrets
10. Observability
11. Drift/performance monitoring
12. Model governance/model card
13. Staged promotion
14. Rollback
15. CI/CD
16. Incident response

## Non-goals

- Building another novel ML algorithm
- Pretending a local container is a cloud deployment
- Automatic retraining without evidence
- Automatic promotion of an unevaluated model
- Adding AWS/Kubernetes/Terraform only as résumé keywords
