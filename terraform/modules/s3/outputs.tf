output "s3_bucket_name" {
  description = "Name of the S3 bucket for cost reports"
  value       = aws_s3_bucket.cost_reports.bucket
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket for cost reports"
  value       = aws_s3_bucket.cost_reports.arn
}

