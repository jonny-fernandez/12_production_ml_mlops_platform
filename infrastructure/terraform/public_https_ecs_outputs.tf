# CP9 Step 7 — non-secret ECS deployment metadata only.
output "ecs_deployment_requested" {
  description = "ECS opt-in switch; NOT evidence of an approved model release."
  value       = var.enable_ecs_deployment
}

output "ecs_task_definition_arn" {
  description = "Null while the ECS service has not been explicitly authorized/deployed."
  value       = try(aws_ecs_task_definition.https_api[0].arn, null)
}

output "ecs_service_name" {
  description = "Null until deployment is explicitly approved."
  value       = try(aws_ecs_service.https_api[0].name, null)
}

output "ecs_desired_count" {
  description = "Requested initial Fargate count (not evidence of running tasks)."
  value       = var.ecs_desired_count
}
