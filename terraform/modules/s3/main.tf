# S3 buckets for cost reports

resource "aws_s3_bucket" "cost_reports" {
  bucket = "${var.project_name}-${var.s3_region}-${var.environment}-cost-reports"

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-cost-reports"
    }
  )


}

# Enable versioning for the bucket
resource "aws_s3_bucket_versioning" "cost_reports_versioning" {
  bucket = aws_s3_bucket.cost_reports.id

  versioning_configuration {
    status = "Enabled"
  }
}

# enable server-side encryption for the bucket
resource "aws_s3_bucket_server_side_encryption_configuration" "cost_reports_encryption" {
  bucket = aws_s3_bucket.cost_reports.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }

}

# Disabling public access to the bucket
resource "aws_s3_bucket_public_access_block" "cost_reports_public_access" {
  bucket = aws_s3_bucket.cost_reports.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}


# Lifecycle policy - delete old reports after 60 days (cost optimization)
resource "aws_s3_bucket_lifecycle_configuration" "cost_reports" {
  bucket = aws_s3_bucket.cost_reports.id

  rule {
    id     = "delete-old-reports"
    status = "Enabled"

    filter {}

    expiration {
      days = 60
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}
