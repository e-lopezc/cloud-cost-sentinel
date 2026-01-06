# This module creates an ECS cluster to lunch a scheduled task
# the scheduled task will run a Fargate task every day at midnight UTC


resource "aws_ecs_cluster" "cloud_cost_sentinel" {
  name = "${var.project_name}-${var.environment}-ecs-cluster"
  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-ecs-cluster"
    }
  )
  setting {
    name  = "containerInsights"
    value = "enabled"
  }

}

resource "aws_ecs_task_definition" "cloud_cost_sentinel_task" {
  family                   = "${var.project_name}-${var.environment}-cloud-cost-sentinel-task"
  network_mode             = var.network_mode
  requires_compatibilities = var.requires_compatibilities
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([
    {
      name      = "${var.project_name}-${var.environment}-scanner"
      image     = "${var.ecr_repository_url}:${var.image_tag}"
      essential = true

      environment = [
        {
          name  = "SNS_TOPIC_ARN"
          value = var.sns_topic_arn
        },
        {
          name  = "AWS_REGION"
          value = var.aws_region
        },
        {
          name  = "ENVIRONMENT"
          value = var.environment
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_logs.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])
  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-cloud-cost-sentinel-task"
    }
  )
}


resource "aws_cloudwatch_event_rule" "daily_trigger" {
  name                = "${var.project_name}-${var.environment}-daily-trigger"
  description         = "Triggers the Cloud Cost Sentinel task daily at midnight UTC"
  schedule_expression = "cron(0 0 * * ? *)" # Every day at midnight UTC
}

resource "aws_iam_role" "eventbridge_ecs_role" {
  name = "${var.project_name}-${var.environment}-eventbridge-ecs-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "events.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "eventbridge_ecs_policy" {
  role = aws_iam_role.eventbridge_ecs_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ecs:RunTask"
      ]
      Resource = aws_ecs_task_definition.cloud_cost_sentinel_task.arn
      },
      {
        Effect = "Allow"
        Action = "iam:PassRole"
        Resource = [
          var.execution_role_arn,
          var.task_role_arn
        ]
    }]
  })
}

resource "aws_cloudwatch_event_target" "ecs_task_target" {
  rule      = aws_cloudwatch_event_rule.daily_trigger.name
  role_arn  = aws_iam_role.eventbridge_ecs_role.arn
  target_id = "cloud-cost-sentinel-ecs-task"
  arn       = aws_ecs_cluster.cloud_cost_sentinel.arn

  ecs_target {
    task_definition_arn = aws_ecs_task_definition.cloud_cost_sentinel_task.arn
    launch_type         = "FARGATE"
    network_configuration {
      subnets          = var.subnets
      security_groups  = var.security_groups
      assign_public_ip = var.assign_public_ip
    }
  }
}


resource "aws_cloudwatch_log_group" "ecs_logs" {
  name              = "/ecs/${var.project_name}-${var.environment}"
  retention_in_days = var.log_retention_days

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-ecs-logs"
    }
  )
}
