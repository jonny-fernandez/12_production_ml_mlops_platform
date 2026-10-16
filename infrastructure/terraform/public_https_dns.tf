# Optional DNS alias for an EXISTING domain/hosted zone. No domains or certificates
# are purchased or issued here. Explicitly disabled by default.
resource "aws_route53_record" "https_api" {
  count   = local.public_https_stack_enabled && var.manage_api_dns ? 1 : 0
  zone_id = var.route53_hosted_zone_id
  name    = var.api_domain_name
  type    = "A"
  alias {
    name                   = aws_lb.https[0].dns_name
    zone_id                = aws_lb.https[0].zone_id
    evaluate_target_health = true
  }
  lifecycle {
    precondition {
      condition     = length(trimspace(var.route53_hosted_zone_id)) > 0 && length(trimspace(var.api_domain_name)) > 0
      error_message = "A controlled Route 53 hosted zone and full API hostname are required."
    }
  }
}
