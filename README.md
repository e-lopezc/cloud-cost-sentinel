# Cloud Cost Sentinel

A containerized AWS cost monitoring system that identifies wasteful resources and recommends optimization opportunities.

## 🎯 Project Status

**Current Phase**: Week 1 - Docker + ECS Fundamentals

- [x] Project structure created
- [ ] Docker container running locally
- [ ] ECS task execution
- [ ] EventBridge scheduling
- [ ] Resource scanning logic
- [ ] Report generation
- [ ] Email notifications
- [ ] Production testing

## 🏗️ Architecture

*(Coming in Week 1)*

## 🚀 Quick Start

*(Coming in Week 1)*

## 📋 Features

**Cost Waste Detection:**
- Idle EC2 instances (CPU <5% for 7 days)
- Forgotten RDS databases (no connections in 14 days)
- Old RDS snapshots (>90 days old)
- Unused S3 buckets (no access in 180 days)
- Unattached EBS volumes

**Reporting:**
- JSON, CSV, and HTML reports
- S3 storage with lifecycle policies
- Email notifications via SNS

## 💰 Cost Analysis

*(Coming in Week 4)*

## 🧪 Testing

*(Coming in Week 4)*

## 📚 Documentation

- [Week-by-Week Implementation Plan](docs/IMPLEMENTATION_PLAN.md)
- [Architecture Decisions](docs/ARCHITECTURE.md)
- [Lessons Learned](docs/LESSONS_LEARNED.md)

## License

MIT License - Educational and portfolio use
