# Cloud Cost Sentinel - Project Context Memory

## 🎯 Project Overview

**Project Name**: Cloud Cost Sentinel  
**Repository**: `cloud-cost-sentinel`  
**Goal**: Containerized AWS cost monitoring system using ECS Fargate to scan for wasteful resources daily

## 👤 User Profile

**Background:**
- Junior SRE with 10+ years technical support experience
- Transitioning to Cloud Solutions Architect role
- Already completed: Serverless Product Catalog API (Lambda + DynamoDB + Terraform)
- Current skills: Basic Terraform, AWS Lambda, DynamoDB, Aurora POC experience
- Docker level: Intermediate (can write Dockerfiles, understand layers, haven't done multi-stage builds yet)

**Learning Goals (Ranked):**
1. Master ECS/Docker (containers are critical for 2025)
2. Build FinOps expertise (massive market demand)
3. Demonstrate multi-service AWS integration

**Time Commitment:** 10 hours/week for 4 weeks, then 1 week documentation

## 🎨 Project Architecture

### **Real Problems Identified:**
- Idle EC2 instances running 24/7
- Forgotten RDS databases from old POCs
- Old RDS snapshots (>90 days)
- S3 buckets unused for years
- Unattached EBS volumes

### **Architecture Design:**

```
EventBridge Schedule (daily 2 AM UTC)
    ↓
ECS Fargate Task (Cost Analyzer Container)
    ↓
    ├─→ EC2 API (describe instances, CloudWatch metrics)
    ├─→ RDS API (describe DB instances)
    ├─→ EBS API (describe volumes)
    ├─→ S3 API (bucket access metrics)
    ↓
Analysis Logic (Python script)
    ├─→ Rule-based checks (CPU <5%, detached volumes)
    ├─→ Cost calculations (potential savings)
    ↓
Store Results
    ├─→ S3 (daily reports as JSON/CSV/HTML)
    └─→ (Optional later: DynamoDB for historical tracking)
    ↓
Notifications
    └─→ SNS → Email
```

### **Tech Stack:**
- **ECS Fargate**: Scheduled task (learning containers for EKS prep)
- **Python 3.13**: Analysis logic, boto3 for AWS APIs
- **EventBridge**: Cron-based daily triggers
- **S3**: Report storage with lifecycle policies
- **SNS**: Email notifications
- **CloudWatch Logs**: Container debugging
- **Terraform**: Infrastructure as Code (consistency with previous project)
- **ECR**: Container image registry

### **Scope Decision:**
"Option A+ with a bit of B" - Foundational architecture that's extensible:
- Daily scans for idle resources (EC2, RDS, EBS, S3)
- Rule-based alerts with cost calculations
- Email notifications + S3 reports
- Simple but production-ready
- Can extend later with dashboard, multi-account, auto-remediation

## 📅 4-Week Implementation Plan

### **Week 1: Docker + ECS Fundamentals (10 hours)**
**Goal**: Master containers and get basic ECS task running

- Mon-Tue (3h): Docker deep dive, multi-stage builds
- Wed-Thu (4h): ECR setup, ECS task execution
- Fri-Weekend (3h): EventBridge scheduling, CloudWatch logs

**Deliverable**: ECS task running on schedule, logging to CloudWatch

### **Week 2: Resource Scanning Logic (10 hours)**
**Goal**: Build the actual cost analysis engine

- Mon-Tue (4h): EC2 idle detection with CloudWatch metrics
- Wed-Thu (4h): RDS + snapshot analysis
- Fri-Weekend (2h): S3 + EBS scanning

**Deliverable**: Container scans all 4 resource types, prints findings

### **Week 3: Reporting + Notifications (10 hours)**
**Goal**: Generate actionable reports and send alerts

- Mon-Tue (4h): JSON, CSV, HTML report generation
- Wed-Thu (4h): S3 integration with lifecycle policies
- Fri-Weekend (2h): SNS email notifications

**Deliverable**: Complete cost scanning system with reports and emails

### **Week 4: Production Readiness + Testing (10 hours)**
**Goal**: Make it interview-worthy

- Mon-Tue (3h): Error handling, cost optimization
- Wed-Thu (4h): Unit tests, integration testing
- Fri-Weekend (3h): Documentation, architecture diagram

**Deliverable**: Production-ready Cost Sentinel

### **Week 5: Documentation (5 hours)**
- Lessons learned section
- Demo video/screenshots
- Interview prep stories
- LinkedIn post
- GitHub polish

## 📝 Recent Session Summary

### **2026-01-26 Session:**
**Duration:** ~30 minutes  
**Focus:** Project progress assessment and status review

**Key Findings:**
1. ✅ **EC2 Scanner COMPLETE** - Feature branch ready to merge
   - `feature/ec2-scanner-logic` has 3 commits ahead of main
   - EC2Scanner fully implemented (198 lines)
   - **28 unit tests passing** ✅
   - Makefile added for automated testing
   - No bugs found (previous "Class" bug was already fixed)

2. ✅ **Infrastructure status confirmed**
   - All 6 Terraform modules complete
   - Previously deployed but now destroyed
   - Ready to redeploy when needed

3. 📊 **Overall project assessment: ~45% complete**
   - Week 1: ✅ 100% (Docker + Infrastructure)
   - Week 2: 🟡 45% (EC2 done, RDS/EBS/S3 pending)
   - Week 3-4: ❌ 0% (Reporting and production hardening)

**Next Actions:**
1. Merge `feature/ec2-scanner-logic` to main
2. Deploy infrastructure with `terraform apply`
3. Push Docker image to ECR and test ECS task
4. Begin RDS scanner (Week 2 priority)

---

### **2025-01-06 Session:**
**Duration:** ~1 hour  
**Focus:** Complete dev environment integration - wire all Terraform modules together

**Accomplishments:**
1. ✅ **Integrated ALL 6 Terraform modules in dev/main.tf**
   - ECR (already existed)
   - Networking (VPC, subnets, security group)
   - S3 (cost reports storage)
   - SNS (email notifications)
   - IAM (task execution + task roles)
   - ECS (cluster, task definition, EventBridge scheduling)

2. ✅ **Created terraform.tfvars for centralized configuration**
   - Removed hardcoded tags from all module calls (DRY principle)
   - Created `var.tags`, `var.environment`, `var.email_address` variables
   - Created `terraform.tfvars.example` for version control

3. ✅ **Fixed multiple validation errors**
   - S3 lifecycle rule: Added required `filter {}` block
   - IAM outputs: Fixed resource names (`ecs_task_execution_role`, `ecs_task_role`)
   - S3/SNS output references: Fixed to use `s3_bucket_arn`, `sns_topic_arn`
   - ECS outputs: Fixed `eventbridge_rule_name` → `eventbridge_rule_arn`

4. ✅ **Updated AWS provider version**
   - Terraform: `>= 1.0` → `>= 1.6`
   - AWS Provider: `~> 5.0` → `~> 5.80` (using v5.100.0)

5. ✅ **Added comprehensive outputs** (18 total)
   - ECR: repository_url, repository_name
   - Networking: vpc_id, public_subnet_ids, security_group_id
   - S3: bucket_name, bucket_arn
   - SNS: topic_arn, topic_name
   - IAM: task_execution_role_arn, task_role_arn
   - ECS: cluster_name, cluster_arn, task_definition_arn, log_group_name, eventbridge_rule_arn

6. ✅ **Validated complete configuration**
   - `terraform init` ✅
   - `terraform validate` ✅ Success!

**Key Refactoring:**
- Replaced hardcoded tags in every module with `var.tags`
- Replaced hardcoded `environment = "dev"` with `var.environment`
- All configuration now flows from `terraform.tfvars`

**Files Modified:**
- `terraform/environments/dev/main.tf` - All 6 modules integrated
- `terraform/environments/dev/variables.tf` - Added environment, email_address, tags
- `terraform/environments/dev/outputs.tf` - 18 outputs for all modules
- `terraform/environments/dev/terraform.tfvars` - Centralized config values
- `terraform/modules/s3/main.tf` - Fixed lifecycle filter
- `terraform/modules/iam/outputs.tf` - Fixed resource name references

**Module Integration Order (dependency chain):**
```
ECR (no deps) → Networking (no deps) → S3 (no deps) → SNS (no deps)
    ↓                                      ↓              ↓
    └──────────────────────────────────────┴──────────────┘
                                           ↓
                                    IAM (needs S3 + SNS ARNs)
                                           ↓
                                    ECS (needs ALL above)
```

**Infrastructure Ready for Deployment:**
- All modules wired together correctly
- `terraform apply` will create ~25-30 AWS resources
- Estimated cost: ~$0.80/month

**Discovered: EC2 Scanner Already Started**
- Found `src/scanners/ec2_scanner.py` with partial implementation
- Has bug: `Class` should be `class` (Python case-sensitive)
- Methods exist for: get_running_ec2_instances, get_ec2_cpu_utilization, analyze_ec2_instances

**Next Focus:**
- Fix EC2 scanner bug (`Class` → `class`)
- Complete EC2 scanner implementation
- Implement RDS, EBS, S3 scanners (Week 2 work)
- Add report generation and SNS notifications

---

### **2025-12-23 Session:**
**Duration:** ~2 hours  
**Focus:** Complete SNS and ECS Terraform modules with architectural decisions

**Accomplishments:**
1. ✅ **Reviewed and validated SNS module** (already complete)
   - SNS topic with proper naming and tags
   - Conditional email subscription (only if email_address provided)
   - Topic policy allowing ECS tasks to publish
   - All outputs defined (topic ARN, name, subscription ARN)
   
2. ✅ **Learned the 5-Step Terraform Module Framework**
   - Step 1: Define Business Purpose (what problem does it solve?)
   - Step 2: Identify Required Resources (what AWS components needed?)
   - Step 3: Map Dependencies (inputs from/outputs to other modules)
   - Step 4: Design for Flexibility (configurable vs hard-coded)
   - Step 5: Validate Integration (how does it fit the architecture?)
   
3. ✅ **Created complete ECS Terraform module**
   - **ECS Cluster** with Container Insights enabled
   - **Task Definition** with Fargate launch type
     - CPU: 256 (0.25 vCPU), Memory: 512 MiB
     - Network mode: awsvpc (required for Fargate)
     - Both execution_role_arn and task_role_arn configured
     - Container definitions built inside module (not passed as variable)
   - **Container Configuration**:
     - Image from ECR with configurable tag
     - Environment variables: SNS_TOPIC_ARN, AWS_REGION, ENVIRONMENT
     - CloudWatch logs with awslogs driver
   - **EventBridge Scheduling**:
     - CloudWatch Event Rule (cron: daily at midnight UTC)
     - IAM role for EventBridge to run ECS tasks
     - Event target linking rule to ECS cluster
   - **CloudWatch Log Group** with 7-day retention (cost optimization)
   - Complete variables.tf and outputs.tf
   - Validated with `terraform init` and `terraform validate` ✅

**Key Architectural Decisions:**

1. **Removed `aws_ecs_service` resource**
   - **Reasoning:** ECS Service runs containers 24/7 (would cost $8-10/month)
   - **Solution:** Use EventBridge scheduled tasks instead (only runs 10 min/day)
   - **Cost Impact:** Reduced from ~$8/month to ~$0.20/month
   
2. **EventBridge IAM role in ECS module (not IAM module)**
   - **Why?** Avoids circular dependency (EventBridge role needs task_definition_arn)
   - **Principle:** "The module that uses the resource should own it"
   - **IAM module** = Application identity (task roles for container permissions)
   - **ECS module** = Infrastructure orchestration (EventBridge role for scheduling)
   
3. **Build container_definitions inside ECS module**
   - **Why?** More maintainable than passing JSON strings as variables
   - **Benefit:** Module handles all container configuration internally
   - **Clean Interface:** Caller only provides ECR URL, image tag, SNS ARN
   
4. **Self-contained module design**
   - ECS module includes all its dependencies (EventBridge, IAM role, CloudWatch logs)
   - Clear input/output interface with other modules
   - Follows separation of concerns

**Module Status After Session:**
- ✅ ECR - Complete (100%)
- ✅ IAM - Complete (100%)
- ✅ Networking - Complete (100%)
- ✅ S3 - Complete (100%)
- ✅ SNS - Complete (100%)
- ✅ **ECS - Complete (100%)** ✨ NEW
- ❌ Dev environment integration - Not complete (only ECR module integrated)

**Next Focus:** 
- Integrate all modules in terraform/environments/dev/main.tf
- Deploy infrastructure with `terraform apply`
- Push Docker image to ECR
- Test ECS task execution

---

### **2025-12-15 Session:**
**Duration:** ~1 hour  
**Focus:** Complete Networking Terraform module with public subnets

**Accomplishments:**
1. ✅ Created complete Networking Terraform module
   - **VPC** with DNS hostnames and DNS support enabled
   - **Internet Gateway** for internet access
   - **2 Public Subnets** across different availability zones (us-east-1a, us-east-1b)
     - Auto-assign public IPs enabled
     - CIDR: 10.0.1.0/24 and 10.0.2.0/24
   - **Route Table** with route to Internet Gateway (0.0.0.0/0)
   - **Route Table Associations** connecting both subnets
   - **Security Group** for ECS tasks
     - Egress: Allow all outbound (needed for AWS API calls)
     - Ingress: None (tasks don't accept inbound traffic)
   
2. ✅ Created proper `variables.tf`
   - project_name, environment, aws_region
   - vpc_cidr, public_subnet_1_cidr, public_subnet_2_cidr
   - tags for resource tagging
   
3. ✅ Created `outputs.tf` with all necessary exports
   - vpc_id, public_subnet_ids (as list), security_group_id, vpc_cidr
   
4. ✅ Validated Terraform syntax
   - Successfully ran `terraform init` (installed AWS provider v6.26.0)
   - Successfully ran `terraform validate` - no errors

**Key Architectural Decision:**
- Chose **public subnets** over private subnets + NAT Gateway/VPC Endpoints
- **Reasoning:** 
  - NAT Gateway: $32/month (too expensive for learning project)
  - VPC Endpoints: ~$43/month for 6 interface endpoints (EC2, RDS, CloudWatch, SNS, STS, ECR)
  - Public subnets: FREE (Internet Gateway has no charge)
  - Security: Still secure - tasks run 10 min/day, no inbound traffic, IAM controls API access
  - For production: Would document "use private subnets + VPC endpoints" in README

**Traffic Flow:**
```
ECS Task (public subnet with public IP)
    ↓
Security Group (egress only - all outbound allowed)
    ↓
Route Table (routes 0.0.0.0/0 → Internet Gateway)
    ↓
Internet Gateway
    ↓
Internet → AWS APIs (EC2, RDS, S3, CloudWatch, etc.)
```

**Next Decision Point:** 
- Finish infrastructure modules first (S3, SNS, ECS) OR
- Implement scanning logic first (EC2, RDS, EBS, S3 scanners in Python)
- Recommended: Add scanning logic first, then complete infrastructure for single deployment

---

### **2025-12-08 Session:**
**Duration:** ~30 minutes  
**Focus:** Create IAM Terraform module with custom policies

**Accomplishments:**
1. ✅ Created complete IAM Terraform module
   - **Task Execution Role** with custom policy (not AWS managed policy)
     - CloudWatch Logs: CreateLogGroup, CreateLogStream, PutLogEvents
     - ECR: GetAuthorizationToken, BatchCheckLayerAvailability, GetDownloadUrlForLayer, BatchGetImage
   
   - **Task Role** with comprehensive AWS API permissions
     - EC2: DescribeInstances, DescribeVolumes, DescribeSnapshots, DescribeRegions
     - RDS: DescribeDBInstances, DescribeDBSnapshots, DescribeDBClusters
     - CloudWatch: GetMetricStatistics, ListMetrics
     - S3: PutObject, GetObject, ListBucket (for reports bucket)
     - SNS: Publish (for notifications)
   
2. ✅ Created `variables.tf` with all required inputs
   - project_name, environment, tags
   - s3_bucket_arn, sns_topic_arn (with defaults for flexibility)
   
3. ✅ Created `outputs.tf` with role ARNs
   - task_execution_role_arn (for ECS to pull images/write logs)
   - task_role_arn (for container to call AWS APIs)
   - Both role names for reference

**Key Decision:**
- Chose custom IAM policies over AWS managed policies for explicit control
- Separated execution role (ECS permissions) from task role (container permissions)
- Made S3/SNS ARNs optional with defaults to avoid circular dependencies

**Next Focus:** Create Networking, S3, SNS, and ECS Terraform modules

---

### **2025-12-03 Session:**
**Duration:** ~1-2 hours  
**Focus:** Complete AWS SDK verification and start Terraform infrastructure

**Accomplishments:**
1. ✅ Implemented AWS credential verification using boto3 STS
   - Added `verify_aws_credentials()` function to main.py
   - Returns account ID, user/role ARN, and AWS region
   - Graceful error handling for NoCredentialsError and ClientError
   
2. ✅ Fixed Python deprecation warnings
   - Replaced `datetime.utcnow()` with `datetime.now(timezone.utc)`
   - Added timezone import for Python 3.9+ compatibility
   
3. ✅ Created ECR Terraform module
   - ECR repository with image scanning enabled
   - Lifecycle policy to keep only last 5 images (cost optimization)
   - Proper tagging and MUTABLE tag configuration for development
   
4. ✅ Created dev environment Terraform skeleton
   - Provider configuration with AWS ~> 5.0
   - Default tags for all resources
   - ECR module integration

**Container Testing Results:**
- Container successfully verifies AWS credentials
- Displays account information in logs
- Proper structured logging with timestamps
- Ready for deployment to ECS

**Next Focus:** Create remaining Terraform modules (Networking, ECS, S3, SNS)

---

## 📁 Current Project Structure

```
cloud-cost-sentinel/
├── README.md                      # Initial structure created
├── Dockerfile                     # Multi-stage build ready
├── requirements.txt               # boto3, pytest, moto, jinja2
├── .dockerignore                  # Created
├── .gitignore                     # Created
├── src/
│   ├── __init__.py
│   ├── main.py                    # Entry point with AWS credential verification + scanner calls
│   ├── scanners/
│   │   ├── __init__.py
│   │   └── ec2_scanner.py         # ✅ COMPLETE - EC2 idle detection (198 lines, 28 tests)
│   ├── reports/
│   │   └── __init__.py
│   └── utils/
│       └── __init__.py
├── terraform/
│   ├── modules/
│   │   ├── ecr/                   # ✅ CREATED - ECR repository with lifecycle policy
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   ├── iam/                   # ✅ CREATED - Task execution + task roles with custom policies
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   ├── networking/            # ✅ CREATED - VPC, public subnets, IGW, security group
│   │   │   ├── main.tf            # ✅ VPC, 2 public subnets, IGW, route table, security group
│   │   │   ├── variables.tf      # ✅ All variables defined
│   │   │   └── outputs.tf        # ✅ Outputs: vpc_id, subnet_ids, security_group_id
│   │   ├── s3/                    # ✅ CREATED - S3 bucket with versioning, encryption, lifecycle
│   │   │   ├── main.tf            # ✅ Bucket, versioning, encryption, public access block, lifecycle
│   │   │   ├── variables.tf      # ✅ All variables defined
│   │   │   └── outputs.tf        # ✅ Outputs: bucket_name, bucket_arn
│   │   ├── sns/                   # ✅ CREATED - SNS topic with email subscription
│   │   │   ├── main.tf            # ✅ Topic, conditional subscription, topic policy
│   │   │   ├── variables.tf      # ✅ All variables defined
│   │   │   └── outputs.tf        # ✅ Outputs: topic_arn, topic_name, subscription_arn
│   │   └── ecs/                   # ✅ CREATED - ECS cluster, task, EventBridge, CloudWatch
│   │       ├── main.tf            # ✅ Cluster, task definition, EventBridge, IAM role, logs
│   │       ├── variables.tf      # ✅ All variables defined
│   │       └── outputs.tf        # ✅ Outputs: cluster_arn, task_arn, log_group_name
│   └── environments/
│       └── dev/                   # ✅ COMPLETE - All 6 modules integrated (2025-01-06)
│           ├── main.tf            # ✅ All modules: ECR, Networking, S3, SNS, IAM, ECS
│           ├── variables.tf       # ✅ aws_region, project_name, environment, email_address, tags
│           ├── outputs.tf         # ✅ 18 outputs for all resources
│           ├── terraform.tfvars   # ✅ Centralized configuration values
│           └── terraform.tfvars.example  # ✅ Template for version control
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # ✅ Test fixtures with moto (155 lines)
│   ├── unit/
│   │   ├── __init__.py
│   │   └── test_ec2_scanner.py      # ✅ 28 comprehensive tests passing
│   └── integration/                 # Empty directory
├── docs/
│   └── cost-sentinel-memory.md      # This file
└── Makefile                         # ✅ Automated testing and environment management
```

## ✅ Current Progress

### **Completed:**
- [x] Project name decided: `cloud-cost-sentinel`
- [x] Project structure created (all directories)
- [x] Multi-stage Dockerfile created and built successfully
- [x] Docker image tested locally (v0.1: 232MB, v0.2: 224MB, v0.3: in progress) ✨
- [x] Container runs and logging works properly
- [x] requirements.txt with all dependencies
- [x] .gitignore and .dockerignore configured
- [x] README.md with project overview
- [x] Initial git commit pushed to GitHub
- [x] **AWS SDK/boto3 verification IMPLEMENTED** ✨ (2025-12-03)
- [x] **main.py with AWS STS credential verification** ✨
- [x] **Graceful error handling for missing/invalid AWS credentials** ✨
- [x] **Fixed datetime deprecation warnings (timezone-aware timestamps)** ✨
- [x] **ECR Terraform module created** ✨ (main.tf, variables.tf, outputs.tf)
- [x] **Dev environment Terraform skeleton created** ✨
- [x] **IAM Terraform module created** ✨ (2025-12-08)
- [x] **Task Execution Role with custom CloudWatch + ECR policies** ✨
- [x] **Task Role with EC2, RDS, CloudWatch, S3, SNS permissions** ✨
- [x] **Networking Terraform module created** ✨ (2025-12-15)
- [x] **VPC with DNS support, 2 public subnets (multi-AZ), Internet Gateway** ✨
- [x] **Route table with internet access, Security group for ECS tasks** ✨
- [x] **Networking module validated (terraform init + validate successful)** ✨
- [x] **S3 Terraform module created** ✨ (2025-12-23) - bucket, versioning, encryption, lifecycle
- [x] **SNS Terraform module created** ✨ (2025-12-23) - topic, conditional email subscription
- [x] **ECS Terraform module created** ✨ (2025-12-23) - cluster, task def, EventBridge, CloudWatch
- [x] **ALL modules integrated in dev environment** ✨ (2025-01-06)
- [x] **terraform.tfvars created with centralized config** ✨ (2025-01-06)
- [x] **terraform validate passing** ✨ (2025-01-06)
- [x] **AWS Provider updated to ~> 5.80** ✨ (2025-01-06)
- [x] **Terraform version updated to >= 1.6** ✨ (2025-01-06)
- [x] **EC2 Scanner COMPLETE with 28 passing unit tests** ✨ (2026-01-26)
- [x] **Makefile created for automated testing** ✨ (2026-01-26)
- [x] **Feature branch feature/ec2-scanner-logic ready to merge** ✨ (2026-01-26)

### **NOT Yet Done (Infrastructure - Ready for Deployment):**
- ⏸️ AWS resources deployment (`terraform apply`) - Ready when needed
- ⏸️ Docker image pushed to ECR - Waiting for deployment
- ⏸️ scripts/push-to-ecr.sh - Not created yet
- ⏸️ ECS task execution test - Waiting for deployment

### **NOT Yet Done (Application Logic - Week 2 Focus):**
- ✅ EC2 scanner COMPLETE (198 lines, 28 tests passing)
- ❌ RDS scanner NOT implemented
- ❌ EBS scanner NOT implemented  
- ❌ S3 scanner NOT implemented
- ❌ Report generation NOT implemented (JSON/CSV/HTML)
- ❌ SNS notifications from Python NOT implemented

### **Week 1 Progress:**

**Day 1-2: Docker Deep Dive (3 hours) - COMPLETED ✅ (2025-12-03)**
- [x] Build Docker image locally (v0.1, v0.2, v0.3 built)
- [x] Test container runs and logs work
- [x] Multi-stage build working (224MB final size)
- [x] Add AWS boto3 SDK test (verify AWS credentials) - DONE ✨
- [x] Fixed datetime.utcnow() deprecation warnings - DONE ✨
- [x] Container successfully verifies AWS credentials and shows account info
- [ ] Document Docker commands (optional)

**Day 3-4: ECR + ECS Task Creation (4 hours) - COMPLETE ✅**
- [x] Create ECR Terraform module (main.tf, variables.tf, outputs.tf) - DONE ✨
- [x] Create dev environment skeleton (main.tf with ECR module) - DONE ✨
- [x] Create IAM Terraform module (task execution + task roles) - DONE ✨ (2025-12-08)
- [x] Create networking Terraform module (VPC, public subnets, IGW) - DONE ✨ (2025-12-15)
- [x] Create S3 Terraform module (reports storage) - DONE ✨ (2025-12-23)
- [x] Create SNS Terraform module (email notifications) - DONE ✨ (2025-12-23)
- [x] Create ECS Terraform module (cluster, task definition, CloudWatch logs, EventBridge) - DONE ✨ (2025-12-23)
- [x] **Complete dev environment main.tf integrating all modules** - DONE ✨ (2025-01-06)
- [x] **Create terraform.tfvars with centralized configuration** - DONE ✨ (2025-01-06)
- [x] **terraform init + validate passing** - DONE ✨ (2025-01-06)
- [ ] Deploy with terraform apply (ready when needed)
- [ ] Create push-to-ecr.sh script
- [ ] Push image to ECR
- [ ] Run manual ECS task test

**Day 5-Weekend: EventBridge Scheduling (3 hours) - COMPLETE ✅**
- [x] EventBridge scheduling included in ECS module - DONE ✨ (2025-12-23)
- [x] Schedule configured: daily at midnight UTC - DONE ✨
- [ ] Test automated execution (after deployment)

### **Week 2 Progress: Resource Scanning Logic**

**EC2 Scanner - ✅ COMPLETE**
- [x] Created `src/scanners/ec2_scanner.py` - COMPLETE (198 lines)
- [x] Method: `get_running_ec2_instances()` - IMPLEMENTED
- [x] Method: `get_ec2_cpu_utilization()` - IMPLEMENTED
- [x] Method: `analyze_ec2_instances()` - IMPLEMENTED
- [x] Method: `calculate_average_cpu()` - IMPLEMENTED
- [x] Method: `get_scan_summary()` - IMPLEMENTED
- [x] **28 comprehensive unit tests passing** ✨
- [x] Integration with main.py complete
- [x] Branch ready to merge to main

**RDS Scanner - NOT STARTED ❌**
- [ ] Create `src/scanners/rds_scanner.py`
- [ ] Detect unused RDS instances
- [ ] Find old snapshots (>90 days)

**EBS Scanner - NOT STARTED ❌**
- [ ] Create `src/scanners/ebs_scanner.py`
- [ ] Find unattached volumes

**S3 Scanner - NOT STARTED ❌**
- [ ] Create `src/scanners/s3_scanner.py`
- [ ] Find unused buckets

## 🔑 Key Technical Decisions Made

### **1. Why ECS over Lambda?**
- Want to learn container orchestration (prep for EKS/Kubernetes)
- No 15-minute timeout constraint
- Already used Lambda in serverless API project
- Foundation for future Kubernetes learning

### **2. Scheduled vs. Continuous:**
- Daily scans at 2 AM UTC (cost waste accumulates slowly)
- Much cheaper than 24/7 monitoring
- Simpler architecture for MVP

### **3. Email + S3 Reports (No Dashboard Yet):**
- Faster to implement
- Reports are portable and shareable
- Can add dashboard later (Lambda + API Gateway + S3 static site)

### **4. Multi-Stage Docker Build:**
- Reduces image size from 1GB+ to ~200MB
- Better security (no build tools in production)
- Faster deployments

### **5. Public Subnets over Private + NAT/VPC Endpoints:** (2025-12-15)
- NAT Gateway would cost $32/month
- VPC Endpoints would cost ~$43/month (6 interface endpoints needed)
- Public subnets are FREE
- Security maintained through: ephemeral tasks (10 min/day), no inbound rules, IAM role restrictions
- Production recommendation: Use private subnets + VPC endpoints for compliance/security requirements

## 💰 Estimated Costs

**Monthly running costs:**
- ECS Fargate: $0.20 (1 task/day × 10 min)
- ECR Storage: $0.05 (500 MB)
- S3 Storage: $0.02 (30 reports)
- Internet Gateway: $0.00 (no charge for gateway itself)
- Data Transfer: ~$0.01 (minimal outbound data)
- CloudWatch Logs: $0.50 (100 MB/month)
- SNS: $0.00 (30 emails)
- **Total: ~$0.78/month**

**ROI**: Tool costs <$1/month but identifies $200-500+ in waste

## 🎤 Interview Story Framework

### **Project Elevator Pitch:**
*"I built Cloud Cost Sentinel, a containerized tool that scans AWS accounts daily to identify wasteful resources. It costs less than $1/month to run but can identify hundreds of dollars in monthly savings. I chose ECS Fargate to learn container orchestration as preparation for Kubernetes, and implemented Infrastructure as Code with modular Terraform."*

### **Key Stories to Develop:**
1. **Why ECS over Lambda** (architectural decision-making)
2. **Multi-stage Docker optimization** (performance thinking)
3. **Real cost problems solved** (business value focus)
4. **Scheduled vs. continuous monitoring** (cost/benefit analysis)
5. **Public subnets vs NAT/VPC endpoints** (cost optimization decision)
6. **Coming from SRE background** (operational excellence mindset)

## 🚀 Next Immediate Steps

**CURRENT STATUS (as of 2026-01-26):**
- ✅ ALL infrastructure modules complete (6 modules, 18 .tf files)
- ✅ EC2 Scanner complete with 28 passing tests
- ✅ Docker image ready (~224MB optimized)
- ✅ Makefile for automated testing
- 🟡 Infrastructure previously deployed, now destroyed (ready to redeploy)
- 🟡 Feature branch `feature/ec2-scanner-logic` ready to merge
- ❌ RDS, EBS, S3 scanners not started

**NEXT ACTIONS:**

**Immediate (Before Week 2 Continues):**
1. **Merge EC2 scanner branch to main** (~5 min)
2. **Deploy infrastructure** (~30 min)
   - `terraform apply` in dev environment
   - Confirm SNS subscription
3. **Push Docker image to ECR** (~15 min)
4. **Test ECS task execution** (~20 min)

**Week 2 Continuation (Scanners - 6-8 hours remaining):**
5. **Implement RDS Scanner** (~2-3 hours)
   - Create `src/scanners/rds_scanner.py`
   - Detect idle RDS instances and old snapshots
6. **Implement EBS Scanner** (~1-2 hours)
   - Create `src/scanners/ebs_scanner.py`
   - Find unattached volumes
7. **Implement S3 Scanner** (~1-2 hours)
   - Create `src/scanners/s3_scanner.py`
   - Find unused buckets
8. **Test all scanners together** (~1 hour)

## 📚 Resources Referenced

- Docker multi-stage builds: https://docs.docker.com/build/building/multi-stage/
- AWS ECS Fargate: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html
- ECS Task Definitions: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definitions.html

## 🎯 Success Criteria

**Week 1 completion means:**
- ✅ Docker container built with multi-stage optimization
- ✅ Image stored in ECR
- ✅ ECS task definition created
- ✅ IAM roles configured
- ✅ Task runs successfully (manual or scheduled)
- ✅ CloudWatch logs showing successful AWS API calls
- ✅ EventBridge scheduling working

## 💡 Important Context

- User prefers concise, actionable guidance
- Wants to avoid documentation rabbit holes (spent enough time on previous project's README)
- Values practical, hands-on learning over theory
- Appreciates realistic timelines and honest assessments
- SRE background means operational thinking comes naturally
- Cost optimization is a personal interest (noticed real waste in current role)

## 🔄 Project Philosophy

**"Foundational architecture you can extend and build upon"**
- Start simple, make it work, then enhance
- Quality over perfection
- Document lessons learned (interview gold)
- Every decision should be defendable in an interview
- Connect technical choices to business outcomes

---

## 📌 To Continue This Project

**Say to Claude:**
"I'm continuing work on my Cloud Cost Sentinel project. I've loaded the project memory."

**Current exact state (2026-01-26):**
- ✅ ALL infrastructure complete: 6 Terraform modules (ECR, Networking, S3, SNS, IAM, ECS)
- ✅ Infrastructure validated and integrated in dev environment
- ✅ Docker image optimized to 224MB with multi-stage build
- ✅ **EC2 Scanner COMPLETE** - 198 lines, 28 unit tests passing
- ✅ Makefile for automated testing created
- ✅ main.py integrates EC2Scanner successfully
- 🟡 Feature branch `feature/ec2-scanner-logic` ready to merge
- 🟡 Infrastructure previously deployed but now destroyed (ready to redeploy)
- ❌ RDS, EBS, S3 scanners not started
- ❌ Report generation not started
- ❌ SNS notifications from Python not implemented

**Next immediate task:**
1. Merge feature/ec2-scanner-logic to main
2. Deploy infrastructure with terraform apply
3. Begin RDS scanner implementation (Week 2 priority)

---

*Memory file updated: 2026-01-26*  
*Project: Cloud Cost Sentinel*  
*Phase: Week 2 (Resource Scanning Logic) - EC2 Scanner COMPLETE ✅, RDS/EBS/S3 pending*
