# Project 12 CP9 Step 7 — release prerequisites for future ECS/Fargate runtime.
# This file is DESIGN ONLY: false defaults mean no ECS task/service is created.

variable "enable_ecs_deployment" {
  description = "FINAL opt-in gate for ECS task and service; requires existing AWS + HTTPS gates, cloud runtime validation, approved model and immutable image."
  type        = bool
  default     = false
}

variable "cloud_runtime_verified" {
  description = "Must be explicitly confirmed only after a cloud-specific image loads its embedded verified model using APP_ENV=cloud and passes parity/security tests. The CP8 local image does NOT meet this requirement."
  type        = bool
  default     = false
}

variable "model_release_approved" {
  description = "Explicit release approval for cloud use. Does not itself modify MLflow status or override any model-loader protections."
  type        = bool
  default     = false
}

variable "release_approval_reference" {
  description = "Non-secret release/change record identifier; empty until real review."
  type        = string
  default     = ""
}

variable "approved_image_digest" {
  description = "Immutable SHA-256 image digest only (sha256:<64 lowercase hex>). ECS image URL is constructed from THIS project's ECR repository."
  type        = string
  default     = ""

  validation {
    condition     = var.approved_image_digest == "" || can(regex("^sha256:[0-9a-f]{64}$", var.approved_image_digest))
    error_message = "approved_image_digest must be empty or sha256: followed by exactly 64 lowercase hexadecimal characters."
  }
}

variable "api_key_secret_arn" {
  description = "ARN of a pre-existing Secrets Manager secret containing ONLY the API key (not its value). Do not store the secret value in Terraform."
  type        = string
  default     = ""

  validation {
    condition     = var.api_key_secret_arn == "" || can(regex("^arn:aws:secretsmanager:[a-z0-9-]+:[0-9]{12}:secret:[A-Za-z0-9/_+=.@-]+$", var.api_key_secret_arn))
    error_message = "api_key_secret_arn must be empty or a valid-looking AWS Secrets Manager secret ARN."
  }
}

variable "api_domain_name" {
  description = "Planned public DNS name covered by the regional ACM certificate; DNS record is intentionally NOT created in this step."
  type        = string
  default     = ""

  validation {
    condition     = var.api_domain_name == "" || can(regex("^[a-z0-9][a-z0-9.-]+\\.[a-z]{2,}$", var.api_domain_name))
    error_message = "api_domain_name must be empty or a lowercase DNS hostname such as api.example.com."
  }
}

variable "ecs_desired_count" {
  description = "Cost cap on continuously running app tasks in this initial design. Default one; no autoscaling configured."
  type        = number
  default     = 1

  validation {
    condition     = contains([1, 2], var.ecs_desired_count)
    error_message = "ecs_desired_count must be either 1 or 2 for the initial portfolio design."
  }
}
