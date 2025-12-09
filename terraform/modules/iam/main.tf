# Task Execution Role - Used by ECS to pull images and write logs
resource "aws_iam_role" "ecs_task_execution_role" {
  name               = "${var.project_name}-${var.environment}-task-execution-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role.json

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-task-execution-role"
    }
  )
}

# Trust policy - Allow ECS to assume this role
data "aws_iam_policy_document" "ecs_task_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

# Custom policy for Task Execution Role
data "aws_iam_policy_document" "ecs_task_execution_policy" {
  # CloudWatch Logs permissions
  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = ["*"] # this should be more restrictive for production.
  }

  # ECR permissions - pull Docker images
  statement {
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken",
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage"
    ]
    resources = ["*"] # this should be also more restrictive just to the neeeded repositories
}
}

# Attach custom policy to execution role
resource "aws_iam_role_policy" "ecs_task_execution_policy" {
  name   = "${var.project_name}-${var.environment}-task-execution-policy"
  role   = aws_iam_role.ecs_task_execution_role.id
  policy = data.aws_iam_policy_document.ecs_task_execution_policy.json
}

########################################################
# Task Role - Used by the container to call AWS APIs


resource "aws_iam_role" "ecs_task_role" {
  name               = "${var.project_name}-${var.environment}-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role.json

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-task-role"
    }
  )
}

# Custom policy for Task Role - AWS API permissions
data "aws_iam_policy_document" "ecs_task_role_policy" {
  # EC2 permissions - describe instances and volumes
  statement {
    effect = "Allow"
    actions = [
      "ec2:DescribeInstances",
      "ec2:DescribeVolumes",
      "ec2:DescribeSnapshots",
      "ec2:DescribeRegions"
    ]
    resources = ["*"]
  }

  # RDS permissions - describe databases and snapshots
  statement {
    effect = "Allow"
    actions = [
      "rds:DescribeDBInstances",
      "rds:DescribeDBSnapshots",
      "rds:DescribeDBClusters"
    ]
    resources = ["*"]
  }

  # CloudWatch permissions - get metrics for CPU usage
  statement {
    effect = "Allow"
    actions = [
      "cloudwatch:GetMetricStatistics",
      "cloudwatch:ListMetrics"
    ]
    resources = ["*"]
  }

  # S3 permissions - write reports to bucket
  statement {
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:GetObject",
      "s3:ListBucket"
    ]
    resources = [
      var.s3_bucket_arn,
      "${var.s3_bucket_arn}/*"
    ]
  }

  # SNS permissions - publish notifications
  statement {
    effect = "Allow"
    actions = [
      "sns:Publish"
    ]
    resources = [var.sns_topic_arn]
  }
}

# Attach custom policy to task role
resource "aws_iam_role_policy" "ecs_task_role_policy" {
  name   = "${var.project_name}-${var.environment}-task-policy"
  role   = aws_iam_role.ecs_task_role.id
  policy = data.aws_iam_policy_document.ecs_task_role_policy.json
}