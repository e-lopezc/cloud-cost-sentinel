# Development environment for Cloud Cost Sentinel

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "CloudCostSentinel"
      Environment = "dev"
      ManagedBy   = "Terraform"
    }
  }
}

# Module 1: ECR Repository
module "ecr" {
  source          = "../../modules/ecr"
  repository_name = var.project_name
  tags            = var.tags
}

# Module 2: Networking (VPC, Subnets, Security Group)
module "networking" {
  source       = "../../modules/networking"
  project_name = var.project_name
  environment  = var.environment
  aws_region   = var.aws_region
  tags         = var.tags
}

# Module 3: S3 (Cost Reports Storage)
module "s3" {
  source       = "../../modules/s3"
  project_name = var.project_name
  environment  = var.environment
  s3_region    = var.aws_region
  tags         = var.tags
}

# Module 4: SNS (Email Notifications)
module "sns" {
  source        = "../../modules/sns"
  project_name  = var.project_name
  environment   = var.environment
  email_address = var.email_address
  tags          = var.tags
}

# Module 5: IAM (Task Execution and Task Roles)
module "iam" {
  source        = "../../modules/iam"
  project_name  = var.project_name
  environment   = var.environment
  s3_bucket_arn = module.s3.s3_bucket_arn
  sns_topic_arn = module.sns.sns_topic_arn
  tags          = var.tags
}

# Module 6: ECS (Cluster, Task Definition, EventBridge Scheduling)
module "ecs" {
  source       = "../../modules/ecs"
  project_name = var.project_name
  environment  = var.environment
  aws_region   = var.aws_region

  # IAM roles
  execution_role_arn = module.iam.task_execution_role_arn
  task_role_arn      = module.iam.task_role_arn

  # ECR configuration
  ecr_repository_url = module.ecr.repository_url
  image_tag          = "latest"

  # SNS configuration
  sns_topic_arn = module.sns.sns_topic_arn

  # Network configuration from networking module
  subnets          = module.networking.public_subnet_ids
  security_groups  = [module.networking.security_group_id]
  assign_public_ip = true

  # Task size
  cpu    = "256" # 0.25 vCPU
  memory = "512" # 512 MiB

  # Scheduling: Daily at midnight UTC
  schedule_expression = "cron(0 0 * * ? *)"

  # CloudWatch logs retention
  log_retention_days = 7

  tags = var.tags
}
