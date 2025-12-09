output "task_execution_role_arn" {
  description = "ARN of the ECS task execution role (used by ECS to pull images and write logs)"
  value       = aws_iam_role.ecs_task_execution.arn
}

output "task_role_arn" {
  description = "ARN of the ECS task role (used by container to call AWS APIs)"
  value       = aws_iam_role.ecs_task_role.arn
}

output "task_execution_role_name" {
  description = "Name of the ECS task execution role"
  value       = aws_iam_role.ecs_task_execution.name
}

output "task_role_name" {
  description = "Name of the ECS task role"
  value       = aws_iam_role.ecs_task_role.name
}
