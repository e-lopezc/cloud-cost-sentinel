.PHONY: help unit-tests unit-tests-clean integration-tests test-all clean venv install lint format \
        docker-login docker-build docker-push tf-apply tf-init-upgrade deploy run-task teardown

# Variables
VENV_DIR := .venv
PYTHON := python3
VENV_PYTHON := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip
VENV_PYTEST := $(VENV_DIR)/bin/pytest

TF_DIR       := terraform/environments/dev
AWS_REGION   ?= us-east-1
IMAGE_TAG    ?= latest

# Default target
help:
	@echo "Cloud Cost Sentinel - Makefile Commands"
	@echo "========================================"
	@echo ""
	@echo "Environment Management:"
	@echo "  make venv              - Create Python virtual environment"
	@echo "  make install           - Install dependencies in virtual environment"
	@echo "  make clean             - Remove virtual environment and cache files"
	@echo ""
	@echo "Testing:"
	@echo "  make unit-tests        - Create venv, install deps, and run unit tests"
	@echo "  make unit-tests-clean  - Clean up test environment"
	@echo "  make integration-tests - Run integration tests"
	@echo "  make test-all          - Run all tests with coverage"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint              - Run linting checks"
	@echo "  make format            - Format code (if formatter installed)"
	@echo ""
	@echo "Deployment:"
	@echo "  make tf-apply          - Apply Terraform (provisions all AWS infrastructure)"
	@echo "  make tf-init-upgrade   - Upgrade Terraform providers (updates lock file)"
	@echo "  make docker-login      - Authenticate Docker to ECR"
	@echo "  make docker-build      - Build Docker image tagged for ECR"
	@echo "  make docker-push       - Push Docker image to ECR"
	@echo "  make deploy            - Full deploy: tf-apply → docker-login → build → push"
	@echo "  make run-task          - Manually trigger ECS task (for testing)"
	@echo "  make teardown          - Destroy ALL AWS infrastructure (terraform destroy)"
	@echo ""
	@echo "Override defaults: make deploy AWS_REGION=us-west-2 IMAGE_TAG=v1.0.0"
	@echo ""

# Create virtual environment
venv:
	@echo "Creating Python virtual environment..."
	$(PYTHON) -m venv $(VENV_DIR)
	@echo "Virtual environment created at $(VENV_DIR)"

# Install dependencies
install: venv
	@echo "Installing dependencies..."
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -r requirements.txt
	@echo "Dependencies installed successfully"

# Run unit tests (creates env if needed)
unit-tests: install
	@echo "Running unit tests..."
	$(VENV_PYTEST) tests/unit/ -v
	@echo "Unit tests completed"

# Run integration tests
integration-tests: install
	@echo "Running integration tests..."
	$(VENV_PYTEST) tests/integration/ -v
	@echo "Integration tests completed"

# Run all tests with coverage
test-all: install
	@echo "Running all tests with coverage..."
	$(VENV_PYTEST) tests/ --cov=src --cov-report=html --cov-report=term
	@echo "All tests completed. Coverage report: htmlcov/index.html"

# Clean up test environment
unit-tests-clean:
	@echo "Cleaning up test environment..."
	rm -rf $(VENV_DIR)
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "Test environment cleaned"

# Full cleanup
clean: unit-tests-clean
	@echo "Full cleanup completed"

# Lint code
lint: install
	@echo "Running linting checks..."
	@if $(VENV_PIP) list | grep -q pylint; then \
		$(VENV_DIR)/bin/pylint src/; \
	else \
		echo "pylint not installed. Skipping..."; \
	fi
	@if $(VENV_PIP) list | grep -q flake8; then \
		$(VENV_DIR)/bin/flake8 src/; \
	else \
		echo "flake8 not installed. Skipping..."; \
	fi

# Format code
format: install
	@echo "Formatting code..."
	@if $(VENV_PIP) list | grep -q black; then \
		$(VENV_DIR)/bin/black src/ tests/; \
	else \
		echo "black not installed. Install with: $(VENV_PIP) install black"; \
	fi

# ---------------------------------------------------------------------------
# Deployment targets
# ---------------------------------------------------------------------------

# Apply Terraform to provision/update all AWS infrastructure
tf-apply:
	@echo "Applying Terraform in $(TF_DIR)..."
	cd $(TF_DIR) && terraform init && terraform apply -auto-approve
	@echo "Terraform apply complete."

# Upgrade Terraform providers (opt-in; updates .terraform.lock.hcl)
tf-init-upgrade:
	@echo "Upgrading Terraform providers in $(TF_DIR)..."
	cd $(TF_DIR) && terraform init -upgrade
	@echo "Provider upgrade complete."

# Authenticate Docker CLI to ECR — derives region from the ECR URL itself
docker-login:
	$(eval ECR_URL := $(shell cd $(TF_DIR) && terraform output -raw ecr_repository_url))
	$(eval ECR_REGISTRY := $(shell echo $(ECR_URL) | cut -d'/' -f1))
	$(eval ECR_REGION := $(shell echo $(ECR_REGISTRY) | cut -d'.' -f4))
	@echo "Logging in to ECR at $(ECR_REGISTRY)..."
	aws ecr get-login-password --region $(ECR_REGION) | \
		docker login --username AWS --password-stdin \
		$(ECR_REGISTRY)
	@echo "ECR login successful."

# Build the Docker image, tagged for ECR (no AWS credentials required)
docker-build:
	$(eval ECR_URL := $(shell cd $(TF_DIR) && terraform output -raw ecr_repository_url))
	@echo "Building Docker image: $(ECR_URL):$(IMAGE_TAG)..."
	docker build -t $(ECR_URL):$(IMAGE_TAG) .
	@echo "Docker build complete."

# Push the image to ECR (login + build first)
docker-push: docker-login docker-build
	$(eval ECR_URL := $(shell cd $(TF_DIR) && terraform output -raw ecr_repository_url))
	@echo "Pushing $(ECR_URL):$(IMAGE_TAG) to ECR..."
	docker push $(ECR_URL):$(IMAGE_TAG)
	@echo "Image pushed successfully."

# Full deployment: provision infrastructure then build and push the image
deploy: tf-apply docker-push
	@echo ""
	@echo "✅ Deployment complete!"
	@echo "   Image: $(shell cd $(TF_DIR) && terraform output -raw ecr_repository_url):$(IMAGE_TAG)"
	@echo "   ECS task will run on the next EventBridge schedule."
	@echo "   To trigger a manual run now: make run-task"

# Manually trigger the ECS task (useful for testing without waiting for cron)
run-task:
	$(eval CLUSTER  := $(shell cd $(TF_DIR) && terraform output -raw ecs_cluster_name))
	$(eval TASK_DEF := $(shell cd $(TF_DIR) && terraform output -raw ecs_task_definition_arn))
	$(eval SUBNETS  := $(shell cd $(TF_DIR) && terraform output -json public_subnet_ids | tr -d '[] "'))
	$(eval SG       := $(shell cd $(TF_DIR) && terraform output -raw security_group_id))
	@echo "Triggering ECS task on cluster: $(CLUSTER)..."
	aws ecs run-task \
		--cluster $(CLUSTER) \
		--task-definition $(TASK_DEF) \
		--launch-type FARGATE \
		--network-configuration "awsvpcConfiguration={subnets=[$(SUBNETS)],securityGroups=[$(SG)],assignPublicIp=ENABLED}" \
		--region $(AWS_REGION)
	@echo "ECS task triggered. Check CloudWatch logs for output."

# Tear down all AWS infrastructure (Terraform destroy)
teardown:
	@echo "⚠️  WARNING: This will destroy ALL AWS infrastructure for this project."
	@echo "Press Ctrl+C within 5 seconds to cancel..."
	@sleep 5
	$(eval ECR_REPO := $(shell cd $(TF_DIR) && terraform output -raw ecr_repository_name 2>/dev/null))
	@if [ -n "$(ECR_REPO)" ]; then \
		echo "Purging all images from ECR repository '$(ECR_REPO)'..."; \
		IMAGE_IDS=$$(aws ecr list-images --repository-name $(ECR_REPO) --region $(AWS_REGION) --query 'imageIds[*]' --output json 2>/dev/null); \
		if [ "$$IMAGE_IDS" != "[]" ] && [ -n "$$IMAGE_IDS" ]; then \
			aws ecr batch-delete-image --repository-name $(ECR_REPO) --region $(AWS_REGION) --image-ids "$$IMAGE_IDS" > /dev/null; \
			echo "Images purged."; \
		else \
			echo "No images found in ECR repository. Skipping purge."; \
		fi \
	else \
		echo "Could not determine ECR repository name. Skipping image purge."; \
	fi
	cd $(TF_DIR) && terraform destroy -auto-approve
	@echo "✅ All infrastructure destroyed."
