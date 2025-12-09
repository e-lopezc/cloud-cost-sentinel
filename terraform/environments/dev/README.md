# Cloud Cost Sentinel - Development Environment

## Prerequisites

- AWS CLI configured with credentials
- Terraform >= 1.0 installed
- Docker installed

## Deploy ECR Module

```bash
cd terraform/environments/dev

# Initialize Terraform
terraform init

# Validate configuration
terraform validate

# Preview changes
terraform plan

# Deploy
terraform apply
