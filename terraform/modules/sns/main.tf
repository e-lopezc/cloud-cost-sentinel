resource "aws_sns_topic" "cost_alerts" {
  name = "${var.project_name}-${var.environment}-cost-alerts"
  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-cost-alerts"
    }
  )
}

resource "aws_sns_topic_subscription" "email_subscription" {
  count = var.email_address != "" ? 1 : 0

  topic_arn = aws_sns_topic.cost_alerts.arn
  protocol  = "email"
  endpoint  = var.email_address
}

resource "aws_sns_topic_policy" "cost_alerts_policy" {
  arn = aws_sns_topic.cost_alerts.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action   = ["sns:Publish"]
        Resource = aws_sns_topic.cost_alerts.arn
      }
    ]
  })
}
