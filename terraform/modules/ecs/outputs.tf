# ECS Cluster outputs
output "cluster_arn" {
  description = "ARN of the ECS cluster"
  value       = aws_ecs_cluster.cloud_cost_sentinel.arn
}

output "cluster_id" {
  description = "ID of the ECS cluster"
  value       = aws_ecs_cluster.cloud_cost_sentinel.id
}

output "cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.cloud_cost_sentinel.name
}

# Task Definition outputs
output "task_definition_arn" {
  description = "ARN of the ECS task definition"
  value       = aws_ecs_task_definition.cloud_cost_sentinel_task.arn
}

output "task_definition_family" {
  description = "Family of the ECS task definition"
  value       = aws_ecs_task_definition.cloud_cost_sentinel_task.family
}

output "task_definition_revision" {
  description = "Revision of the ECS task definition"
  value       = aws_ecs_task_definition.cloud_cost_sentinel_task.revision
}

# CloudWatch Logs outputs
output "log_group_name" {
  description = "Name of the CloudWatch log group for ECS tasks"
  value       = aws_cloudwatch_log_group.ecs_logs.name
}

output "log_group_arn" {
  description = "ARN of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.ecs_logs.arn
}

# EventBridge outputs
output "eventbridge_rule_arn" {
  description = "ARN of the EventBridge rule that triggers the ECS task"
  value       = aws_cloudwatch_event_rule.daily_trigger.arn
}

output "eventbridge_role_arn" {
  description = "ARN of the IAM role used by EventBridge to trigger ECS tasks"
  value       = aws_iam_role.eventbridge_ecs_role.arn
}
