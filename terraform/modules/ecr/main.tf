# ECR Repository for Cloud Cost Sentinel Docker images

resource "aws_ecr_repository" "cost_sentinel" {
  name                 = var.repository_name
  image_tag_mutability = "MUTABLE" # Allow overwriting tags (useful for development)

  image_scanning_configuration {
    scan_on_push = true # Enable image scanning on push
  }

  tags = merge(
    var.tags,
    {
      Name = var.repository_name
    }
  )
}

# Lifecycle policy to keep only recent images and reduce storage costs
resource "aws_ecr_lifecycle_policy" "cost_sentinel" {
  repository = aws_ecr_repository.cost_sentinel.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 5 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
