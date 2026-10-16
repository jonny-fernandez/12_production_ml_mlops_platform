variable "aws_region" {
  description = "Future AWS deployment region (not contacted during validation)."
  type        = string
  default     = "us-east-1"

  validation {
    condition     = can(regex("^[a-z]{2}(-gov)?-[a-z]+-[0-9]+$", var.aws_region))
    error_message = "aws_region must resemble a valid AWS region, for example us-east-1."
  }
}

variable "project_name" {
  description = "Lowercase AWS resource name prefix."
  type        = string
  default     = "portfolio-mlops"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,23}[a-z0-9]$", var.project_name))
    error_message = "project_name must have 4–25 lowercase letters, digits or hyphens, beginning with a letter and ending in a letter/digit."
  }
}

variable "environment" {
  description = "Logical infrastructure environment; this does not grant model approval."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod."
  }
}

variable "enable_aws_resources" {
  description = "SAFETY GATE: false (default) creates no AWS resources. Never enable without explicit approval and a reviewed cost estimate."
  type        = bool
  default     = false
}

variable "log_retention_days" {
  description = "CloudWatch log retention once explicitly deployed."
  type        = number
  default     = 7

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90], var.log_retention_days)
    error_message = "log_retention_days must be one of the supported values: 1, 3, 5, 7, 14, 30, 60, 90."
  }
}

variable "extra_tags" {
  description = "Optional non-sensitive tags; standard project and data-classification tags cannot be overwritten."
  type        = map(string)
  default     = {}
}
