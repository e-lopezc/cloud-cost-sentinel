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

# SNS-specific variables
variable "email_address" {
  description = "Email address for notifications (optional)"
  type        = string
  default     = "" # Empty string means no email subscription
}
