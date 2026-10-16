# CP9 Step 6: HTTPS-only ALB. No ECS service or tasks are created.
# A DNS-validated ACM certificate in aws_region is mandatory before enabling.
resource "aws_lb" "https" {
  count                      = local.public_https_stack_enabled ? 1 : 0
  name                       = "${local.name_prefix}-alb"
  internal                   = false
  load_balancer_type         = "application"
  security_groups            = [aws_security_group.https_alb[0].id]
  subnets                    = aws_subnet.https_public[*].id
  enable_deletion_protection = false # Portfolio teardown should be possible.

  tags = { Name = "${local.https_name}-alb" }
}

resource "aws_lb_target_group" "https_api" {
  count       = local.public_https_stack_enabled ? 1 : 0
  name        = "${local.name_prefix}-api-tg"
  port        = 8000
  protocol    = "HTTP" # TLS is terminated by ALB; ALB-to-task traffic stays inside VPC.
  target_type = "ip"   # Required for ECS Fargate awsvpc mode.
  vpc_id      = aws_vpc.https[0].id

  health_check {
    enabled             = true
    path                = "/ready"
    protocol            = "HTTP"
    matcher             = "200"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 5
  }
}

resource "aws_lb_listener" "https" {
  count             = local.public_https_stack_enabled ? 1 : 0
  load_balancer_arn = aws_lb.https[0].arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.acm_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.https_api[0].arn
  }

  lifecycle {
    precondition {
      condition     = length(trimspace(var.acm_certificate_arn)) > 0
      error_message = "Do not enable public HTTPS until an ACM certificate exists and is DNS-validated in the AWS deployment region."
    }
    precondition {
      condition     = can(regex("^arn:aws:acm:${var.aws_region}:[0-9]{12}:certificate/", var.acm_certificate_arn))
      error_message = "The ACM certificate must be in the same region as the load balancer."
    }
  }
}
