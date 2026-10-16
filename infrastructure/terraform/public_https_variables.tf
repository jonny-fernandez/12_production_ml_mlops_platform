# CP9 Step 6: public HTTPS architecture. This is intentionally OFF by default.
# This gate is IN ADDITION TO the foundation enable_aws_resources gate.
variable "enable_public_https" {
  description = "SAFETY GATE: false by default. Requires enable_aws_resources=true, an ACM certificate, a cost review, and explicit authorization before any deployment."
  type        = bool
  default     = false
}

variable "acm_certificate_arn" {
  description = "Existing, DNS-validated public ACM certificate ARN in aws_region. Leave blank until you control a domain; do not put private keys here."
  type        = string
  default     = ""

  validation {
    condition     = var.acm_certificate_arn == "" || can(regex("^arn:aws:acm:[a-z0-9-]+:[0-9]{12}:certificate/[a-fA-F0-9-]+$", var.acm_certificate_arn))
    error_message = "acm_certificate_arn must be empty or a properly shaped ACM certificate ARN."
  }
}

variable "network_cidr" {
  description = "New VPC CIDR for the future public ALB and Fargate task. Confirm it does not overlap with existing networks before deployment."
  type        = string
  default     = "10.72.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.network_cidr))
    error_message = "network_cidr must be a valid IPv4 CIDR block."
  }
}
