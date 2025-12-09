output "repository_url" {
  description = "Full URL of the ECR repository"
  value       = aws_ecr_repository.cost_sentinel.repository_url
}

output "repository_arn" {
  description = "ARN of the ECR repository"
  value       = aws_ecr_repository.cost_sentinel.arn
}

output "repository_name" {
  description = "Name of the ECR repository"
  value       = aws_ecr_repository.cost_sentinel.name
}
