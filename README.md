# Cloud Cost Sentinel

A containerized AWS cost monitoring tool that scans for idle/wasteful resources and delivers HTML reports and email alerts — fully automated on a daily schedule.

---

## Architecture

```
EventBridge (daily cron)
    └─► ECS Fargate Task (Docker container)
            ├─► Scans: EC2 · EBS · RDS · S3
            ├─► Reports → S3 bucket (HTML + JSON)
            └─► Alerts  → SNS → Email
```

All infrastructure is managed with Terraform and lives in `terraform/environments/dev`.

---

## What it detects

| Resource | Condition |
|----------|-----------|
| EC2 instances | CPU < 5% average over 7 days |
| EBS volumes | Unattached, or I/O < 100 ops/day over 14 days |
| RDS instances | No connections in 14 days |
| RDS snapshots | Older than 90 days |
| S3 buckets | No access in 180 days |

---

## Prerequisites

- AWS account with appropriate permissions
- [aws-vault](https://github.com/99designs/aws-vault) (or any AWS credential method)
- Terraform ≥ 1.0
- Docker
- Python 3.13+
- `make`

---

## Quick start

```bash
# 1. Provision infrastructure + build and push Docker image
make deploy

# 2. Run a scan immediately (without waiting for the daily schedule)
make run-task

# 3. Check results in CloudWatch
# Log group: /ecs/cloud-cost-sentinel-dev
# Reports:   s3://cloud-cost-sentinel-us-east-1-dev-cost-reports/reports/<date>/
```

---

## Makefile reference

| Command | Description |
|---------|-------------|
| `make deploy` | Full deploy: Terraform apply → Docker build → push to ECR |
| `make run-task` | Trigger ECS task manually for immediate scan |
| `make unit-tests` | Run unit tests (creates venv, installs deps) |
| `make test-all` | Run all tests with coverage report |
| `make teardown` | Destroy all AWS infrastructure (prompts 5s cancel window) |
| `make tf-apply` | Apply Terraform only |
| `make docker-push` | Build and push Docker image only |

Override defaults: `make deploy AWS_REGION=us-west-2 IMAGE_TAG=v1.0.0`

---

## Project structure

```
src/
├── main.py                  # Entry point: orchestrates scan → report → notify
├── scanners/                # EC2, EBS, RDS, S3 scanners
├── reports/                 # HTML report builder + S3 uploader
└── notifications/           # SNS publisher

terraform/
├── environments/dev/        # Root module (wires everything together)
└── modules/                 # ecr · ecs · iam · networking · s3 · sns

scripts/
└── purge_s3_versions.py     # Helper: empties versioned S3 bucket (used by teardown)

tests/
└── unit/                    # moto-based unit tests for all scanners and reporters
```

---

## Running tests

```bash
make unit-tests       # unit tests only
make test-all         # unit + integration tests with coverage
```

---

## Tearing down

```bash
make teardown
```

This will:
1. Purge all ECR images
2. Empty the S3 reports bucket (all versions)
3. Run `terraform destroy`

---

## License

MIT — educational and portfolio use

