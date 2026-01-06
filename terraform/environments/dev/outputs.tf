# ECR Outputs
output "ecr_repository_url" {
  description = "ECR repository URL for docker push"
  value       = module.ecr.repository_url
}

output "ecr_repository_name" {
  description = "ECR repository name"
  value       = module.ecr.repository_name
}

# Networking Outputs
output "vpc_id" {
  description = "VPC ID"
  value       = module.networking.vpc_id
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = module.networking.public_subnet_ids
}

output "security_group_id" {
  description = "Security group ID for ECS tasks"
  value       = module.networking.security_group_id
}

# S3 Outputs
output "s3_bucket_name" {
  description = "S3 bucket name for cost reports"
  value       = module.s3.s3_bucket_name
}

output "s3_bucket_arn" {
  description = "S3 bucket ARN"
  value       = module.s3.s3_bucket_arn
}

# SNS Outputs
output "sns_topic_arn" {
  description = "SNS topic ARN for notifications"
  value       = module.sns.sns_topic_arn
}

output "sns_topic_name" {
  description = "SNS topic name"
  value       = module.sns.sns_topic_name
}

# IAM Outputs
output "task_execution_role_arn" {
  description = "ECS task execution role ARN"
  value       = module.iam.task_execution_role_arn
}

output "task_role_arn" {
  description = "ECS task role ARN"
  value       = module.iam.task_role_arn
}

# ECS Outputs
output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.ecs.cluster_name
}

output "ecs_cluster_arn" {
  description = "ECS cluster ARN"
  value       = module.ecs.cluster_arn
}

output "ecs_task_definition_arn" {
  description = "ECS task definition ARN"
  value       = module.ecs.task_definition_arn
}

output "ecs_log_group_name" {
  description = "CloudWatch log group name for ECS tasks"
  value       = module.ecs.log_group_name
}

output "eventbridge_rule_arn" {
  description = "EventBridge rule ARN for scheduled tasks"
  value       = module.ecs.eventbridge_rule_arn
}
