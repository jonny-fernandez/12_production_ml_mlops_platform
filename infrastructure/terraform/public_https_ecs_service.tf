# Project 12 CP9 Step 7 — disabled-by-default Fargate task/service BLUEPRINT.
# No working cloud model runtime is supplied with this package. The existing
# CP8 Docker image and pinned candidate are deliberately NOT approved for cloud.
# Do not enable until a cloud-specific, provenance-checked image has been tested
# and the model has a separately documented release approval.

locals {
  # A third independent opt-in, in addition to CP9 Step 5 and Step 6.
  ecs_deployment_requested = local.public_https_stack_enabled && var.enable_ecs_deployment
}

# The ECS execution role (NOT the application's task role) needs read access
# for its ONE referenced secret. The secret VALUE must never enter Terraform.
# Uses AWS-managed Secrets Manager encryption; customer-managed KMS keys would
# require a separately scoped kms:Decrypt permission in a later review.
resource "aws_iam_role_policy" "https_execution_api_secret" {
  count = local.ecs_deployment_requested ? 1 : 0

  name = "${local.name_prefix}-read-one-api-secret"
  role = aws_iam_role.https_execution[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "ReadOneApiSecret"
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = var.api_key_secret_arn
    }]
  })
}

resource "aws_ecs_task_definition" "https_api" {
  count = local.ecs_deployment_requested ? 1 : 0

  family                   = "${local.name_prefix}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"  # 0.5 vCPU: validate RAM/latency before approval.
  memory                   = "1024" # 1 GiB: may need more after real load testing.
  execution_role_arn       = aws_iam_role.https_execution[0].arn
  task_role_arn            = aws_iam_role.https_task[0].arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([{
    name                   = "api"
    image                  = "${aws_ecr_repository.api[0].repository_url}@${var.approved_image_digest}"
    essential              = true
    user                   = "10001:10001"
    readonlyRootFilesystem = true
    portMappings = [{
      containerPort = 8000
      hostPort      = 8000
      protocol      = "tcp"
    }]
    # ECS Fargate supports memory-backed tmpfs mounts (AWS Jan 2026 update).
    linuxParameters = {
      initProcessEnabled = true
      tmpfs = [{
        containerPath = "/tmp"
        size          = 64
        mountOptions  = ["rw", "nosuid", "nodev"]
      }]
    }
    environment = [
      { name = "APP_ENV", value = "cloud" },
      { name = "AUTH_REQUIRED", value = "true" },
      { name = "MODEL_NAME", value = "p09-attrition-gb" },
      { name = "MODEL_VERSION", value = "1" },
      { name = "MODEL_THRESHOLD", value = "0.125" },
      { name = "MODEL_BUNDLE_DIR", value = "/app/model" },
      { name = "MODEL_RELEASE_APPROVED", value = "true" },
      { name = "MODEL_RELEASE_APPROVAL_REFERENCE", value = var.release_approval_reference }
    ]
    # ECS injects the SECRET VALUE at container start as API_KEY; value and
    # rotation updates are NOT managed by Terraform. Rotate by redeploying tasks.
    secrets = [{
      name      = "API_KEY"
      valueFrom = var.api_key_secret_arn
    }]
    healthCheck = {
      command     = ["CMD", "python", "-c", "from urllib.request import urlopen; r=urlopen('http://127.0.0.1:8000/ready',timeout=10); assert r.status == 200"]
      interval    = 30
      timeout     = 10
      retries     = 3
      startPeriod = 90
    }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.api[0].name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "api"
      }
    }
  }])

  lifecycle {
    precondition {
      condition     = var.cloud_runtime_verified && var.model_release_approved
      error_message = "Cloud app/model release not approved. CP8 candidate/local Docker image cannot be deployed to public AWS."
    }
    precondition {
      condition     = length(trimspace(var.release_approval_reference)) >= 8
      error_message = "Provide a documented release_approval_reference after review."
    }
    precondition {
      condition     = can(regex("^sha256:[0-9a-f]{64}$", var.approved_image_digest))
      error_message = "Specify the exact approved ECR image sha256 digest, never an unpinned tag."
    }
    precondition {
      condition     = can(regex("^arn:aws:secretsmanager:${var.aws_region}:[0-9]{12}:secret:", var.api_key_secret_arn))
      error_message = "Provide a Secrets Manager ARN in the deployment region, not a secret value."
    }
    precondition {
      condition     = length(var.api_domain_name) > 0 && length(var.acm_certificate_arn) > 0
      error_message = "A controlled API hostname and matching, DNS-validated ACM certificate must be configured first."
    }
  }
}

resource "aws_ecs_service" "https_api" {
  count = local.ecs_deployment_requested ? 1 : 0

  name             = "${local.name_prefix}-api"
  cluster          = aws_ecs_cluster.api[0].id
  task_definition  = aws_ecs_task_definition.https_api[0].arn
  desired_count    = var.ecs_desired_count
  launch_type      = "FARGATE"
  platform_version = "LATEST"

  # Single task by default for cost; ALB spans two AZs, app is NOT highly available.
  health_check_grace_period_seconds = 120
  enable_execute_command            = false
  enable_ecs_managed_tags           = true
  propagate_tags                    = "SERVICE"

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = aws_subnet.https_public[*].id
    security_groups  = [aws_security_group.https_task[0].id]
    assign_public_ip = true # No NAT: allow ECR, Secrets Manager, CloudWatch egress.
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.https_api[0].arn
    container_name   = "api"
    container_port   = 8000
  }

  depends_on = [
    aws_lb_listener.https,
    aws_iam_role_policy.https_execution_api_secret,
  ]
}
