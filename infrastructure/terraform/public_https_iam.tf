# CP9 Step 6: separate ECS execution and application task identities.
# No application privileges, secrets, or model bucket access are granted yet.
# Never store API-key values in Terraform variables, plans, or state.
resource "aws_iam_role" "https_execution" {
  count = local.public_https_stack_enabled ? 1 : 0
  name  = "${local.https_name}-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "https_execution_ecr_logs" {
  count      = local.public_https_stack_enabled ? 1 : 0
  role       = aws_iam_role.https_execution[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "https_task" {
  count = local.public_https_stack_enabled ? 1 : 0
  name  = "${local.https_name}-app-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# TODO in a LATER CP9 step: scoped Secrets Manager read grants to execution role,
# approved model artifact transport and narrow S3 access where justified.
# ECS task definition/service are intentionally absent until cloud model
# approval, immutable image digest, image portability and secret injection pass.
