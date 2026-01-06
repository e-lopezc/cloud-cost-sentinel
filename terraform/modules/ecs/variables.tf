variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# ECS task-specific variables

variable "network_mode" {
  description = "The Docker networking mode to use for the containers in the task"
  type        = string
  default     = "awsvpc"
}

variable "requires_compatibilities" {
  description = "The launch type required by the task"
  type        = list(string)
  default     = ["FARGATE"]
}

variable "cpu" {
  description = "The number of CPU units used by the task"
  type        = string
  default     = "256" # 0.25 vCPU
}

variable "memory" {
  description = "The amount of memory (in MiB) used by the task"
  type        = string
  default     = "512" # 512 MiB
}

variable "execution_role_arn" {
  description = "The ARN of the task execution role that the Amazon ECS container agent and the Docker daemon can assume"
  type        = string
}

variable "task_role_arn" {
  description = "The ARN of the IAM role that containers in the task can assume"
  type        = string
}

# Container-specific variables

variable "ecr_repository_url" {
  description = "The URL of the ECR repository containing the container image"
  type        = string
}

variable "image_tag" {
  description = "The tag of the container image to deploy"
  type        = string
  default     = "latest"
}

variable "sns_topic_arn" {
  description = "The ARN of the SNS topic for notifications (passed as environment variable to container)"
  type        = string
}

variable "aws_region" {
  description = "AWS region for the ECS task"
  type        = string
}

variable "log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 7
}

# Network configuration

variable "subnets" {
  description = "A list of VPC subnets for the ECS service"
  type        = list(string)
}

variable "security_groups" {
  description = "A list of security group IDs for the ECS service"
  type        = list(string)
}

variable "assign_public_ip" {
  description = "Whether to assign a public IP address to the ECS service"
  type        = bool
  default     = true
}

variable "schedule_expression" {
  description = "The schedule expression for the CloudWatch Event rule"
  type        = string
  default     = "cron(0 0 * * ? *)" # Every day at midnight UTC
}
