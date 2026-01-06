output "sns_topic_arn" {
  description = "ARN of the SNS topic for cost alerts"
  value       = aws_sns_topic.cost_alerts.arn
}

output "sns_topic_name" {
  description = "Name of the SNS topic"
  value       = aws_sns_topic.cost_alerts.name
}


output "email_subscription_arn" {
  description = "ARN of the email subscription (if created)"
  value       = var.email_address != "" ? aws_sns_topic_subscription.email_subscription[0].arn : null
}
