output "public_https_requested" {
  description = "User-selected architecture gate (still requires enable_aws_resources)."
  value       = var.enable_public_https
}

output "public_https_effectively_enabled" {
  description = "True only after BOTH cloud-resource opt-in gates are enabled."
  value       = local.public_https_stack_enabled
}

output "public_alb_dns_name" {
  description = "Only present after explicit deployment; NOT a valid certificate-backed domain by itself."
  value       = try(aws_lb.https[0].dns_name, null)
}

output "public_vpc_id" {
  value = try(aws_vpc.https[0].id, null)
}

output "public_target_group_arn" {
  value = try(aws_lb_target_group.https_api[0].arn, null)
}

output "task_execution_role_arn" {
  value = try(aws_iam_role.https_execution[0].arn, null)
}

output "application_task_role_arn" {
  value = try(aws_iam_role.https_task[0].arn, null)
}
