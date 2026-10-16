# CP9 / Step 5 — AWS foundation only. No ECS task or service is deployed here.
# Creation of ANY AWS resources requires explicitly setting enable_aws_resources=true
# and a separate, authorized terraform apply. Default = false.

terraform {
  required_version = ">= 1.6.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = merge(var.extra_tags, {
      Project            = var.project_name
      Environment        = var.environment
      ManagedBy          = "Terraform"
      DataClassification = "SyntheticOnly"
    })
  }
}

locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

# Encrypted image repository. Never push unreviewed images or real employee data.
resource "aws_ecr_repository" "api" {
  count = var.enable_aws_resources ? 1 : 0

  name                 = "${local.name_prefix}-api"
  image_tag_mutability = "IMMUTABLE"

  encryption_configuration {
    encryption_type = "AES256"
  }

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "api" {
  count      = var.enable_aws_resources ? 1 : 0
  repository = aws_ecr_repository.api[0].name

  # Limit orphaned test images; immutable tagged images are retained for audit.
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after 14 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 14
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# Cluster is defined, but no Fargate task, service, load balancer or VPC
# is created until the deployment/runtime architecture has been validated.
resource "aws_ecs_cluster" "api" {
  count = var.enable_aws_resources ? 1 : 0

  name = "${local.name_prefix}-cluster"

  # Enhanced Container Insights incurs extra CloudWatch costs when enabled.
  setting {
    name  = "containerInsights"
    value = "disabled"
  }
}

# Log group is prepared without a task that publishes into it.
resource "aws_cloudwatch_log_group" "api" {
  count = var.enable_aws_resources ? 1 : 0

  name              = "/ecs/${local.name_prefix}/api"
  retention_in_days = var.log_retention_days
}
