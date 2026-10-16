variable "manage_api_dns" {
  description = "Create a Route 53 ALB alias only for an already controlled hosted zone. OFF by default."
  type        = bool
  default     = false
}
variable "route53_hosted_zone_id" {
  description = "Existing owned Route 53 hosted zone ID; no credentials or secret keys."
  type        = string
  default     = ""
  validation {
    condition     = var.route53_hosted_zone_id == "" || can(regex("^Z[A-Z0-9]{6,32}$", var.route53_hosted_zone_id))
    error_message = "Provide an existing Route 53 hosted zone ID, or leave blank."
  }
}
