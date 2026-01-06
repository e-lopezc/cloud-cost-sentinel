variable "repository_name" {
  description = "Name of the ECR repository"
  type        = string
  default     = "cloud-cost-sentinel"
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default = {
    Project     = "CloudCostSentinel"
    ManagedBy   = "Terraform"
    Environment = "dev"
  }
}
