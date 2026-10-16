output "aws_resources_enabled" {
  description = "Whether AWS foundation resources were explicitly enabled."
  value       = var.enable_aws_resources
}

output "aws_region" {
  description = "Selected AWS region."
  value       = var.aws_region
}

output "ecr_repository_url" {
  description = "ECR destination for future approved container image uploads."
  value       = try(aws_ecr_repository.api[0].repository_url, null)
}

output "ecs_cluster_name" {
  description = "Foundation ECS cluster; no tasks or services are defined."
  value       = try(aws_ecs_cluster.api[0].name, null)
}

output "cloudwatch_log_group_name" {
  description = "Foundation log group; no running application publishes logs yet."
  value       = try(aws_cloudwatch_log_group.api[0].name, null)
}
