# CP9 Step 6: ADDITIVE public HTTPS network foundation. NO ECS task/service.
# Requires BOTH enable_aws_resources=true AND enable_public_https=true.
# Defaults false; terraform fmt / init / validate do NOT deploy anything.

locals {
  public_https_stack_enabled = var.enable_aws_resources && var.enable_public_https
  https_name                 = "${local.name_prefix}-https"
}

data "aws_availability_zones" "https" {
  count = local.public_https_stack_enabled ? 1 : 0
  state = "available"
}

resource "aws_vpc" "https" {
  count                = local.public_https_stack_enabled ? 1 : 0
  cidr_block           = var.network_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${local.https_name}-vpc" }
}

resource "aws_internet_gateway" "https" {
  count  = local.public_https_stack_enabled ? 1 : 0
  vpc_id = aws_vpc.https[0].id
  tags   = { Name = "${local.https_name}-igw" }
}

# Two public subnets are needed for an internet-facing ALB. ECS tasks will
# eventually use public IPs for outbound ECR/Secrets Manager/CloudWatch calls,
# but INBOUND is restricted to traffic originating from the ALB security group.
# The Fargate ECS service is deliberately NOT defined in this step.
resource "aws_subnet" "https_public" {
  count                   = local.public_https_stack_enabled ? 2 : 0
  vpc_id                  = aws_vpc.https[0].id
  cidr_block              = cidrsubnet(var.network_cidr, 8, count.index + 1)
  availability_zone       = data.aws_availability_zones.https[0].names[count.index]
  map_public_ip_on_launch = false

  tags = { Name = "${local.https_name}-public-${count.index + 1}" }
}

resource "aws_route_table" "https_public" {
  count  = local.public_https_stack_enabled ? 1 : 0
  vpc_id = aws_vpc.https[0].id
  tags   = { Name = "${local.https_name}-public-rt" }
}

resource "aws_route" "https_public_internet" {
  count                  = local.public_https_stack_enabled ? 1 : 0
  route_table_id         = aws_route_table.https_public[0].id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.https[0].id
}

resource "aws_route_table_association" "https_public" {
  count          = local.public_https_stack_enabled ? 2 : 0
  subnet_id      = aws_subnet.https_public[count.index].id
  route_table_id = aws_route_table.https_public[0].id
}

resource "aws_security_group" "https_alb" {
  count       = local.public_https_stack_enabled ? 1 : 0
  name        = "${local.https_name}-alb-sg"
  description = "HTTPS from internet; outbound only to ECS task port 8000"
  vpc_id      = aws_vpc.https[0].id
  tags        = { Name = "${local.https_name}-alb-sg" }
}

resource "aws_security_group" "https_task" {
  count       = local.public_https_stack_enabled ? 1 : 0
  name        = "${local.https_name}-task-sg"
  description = "Port 8000 only from project ALB; HTTPS egress for AWS services"
  vpc_id      = aws_vpc.https[0].id
  tags        = { Name = "${local.https_name}-task-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "https_alb_in" {
  count             = local.public_https_stack_enabled ? 1 : 0
  security_group_id = aws_security_group.https_alb[0].id
  description       = "HTTPS public entrypoint; API-key authorization remains enforced by FastAPI"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_egress_rule" "https_alb_to_task" {
  count                        = local.public_https_stack_enabled ? 1 : 0
  security_group_id            = aws_security_group.https_alb[0].id
  description                  = "Load balancer to Fargate application"
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
  referenced_security_group_id = aws_security_group.https_task[0].id
}

resource "aws_vpc_security_group_ingress_rule" "https_task_from_alb" {
  count                        = local.public_https_stack_enabled ? 1 : 0
  security_group_id            = aws_security_group.https_task[0].id
  description                  = "Fargate app accepts only ALB connections"
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
  referenced_security_group_id = aws_security_group.https_alb[0].id
}

resource "aws_vpc_security_group_egress_rule" "https_task_out" {
  count             = local.public_https_stack_enabled ? 1 : 0
  security_group_id = aws_security_group.https_task[0].id
  description       = "HTTPS outbound for ECR, CloudWatch, Secrets Manager; tighten after image and model transport review"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}
