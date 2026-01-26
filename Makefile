.PHONY: help unit-tests unit-tests-clean integration-tests test-all clean venv install lint format

# Variables
VENV_DIR := .venv
PYTHON := python3
VENV_PYTHON := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip
VENV_PYTEST := $(VENV_DIR)/bin/pytest

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
