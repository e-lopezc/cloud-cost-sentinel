"""
Unit tests for HTMLReporter.

Verifies structure and content of the generated HTML report across
multiple scenarios: full findings, empty findings, partial findings,
and edge cases.
"""

import pytest
from datetime import datetime, timezone

from reports.html_reporter import HTMLReporter


# ------------------------------------------------------------------ #
# Shared fixtures
# ------------------------------------------------------------------ #

@pytest.fixture
def full_findings():
    """all_findings dict with data in every scanner section."""
    return {
        "account_id": "123456789012",
        "region": "us-east-1",
        "scan_timestamp": "2025-06-15T02:00:00+00:00",
        "ec2": {
            "idle_instances_count": 2,
            "idle_instances_monthly_cost": 142.56,
            "idle_instances": [
                {
                    "instance_id": "i-aaaa1111",
                    "instance_name": "web-server-01",
                    "instance_type": "t3.large",
                    "avg_cpu_percent": 1.2,
                    "estimated_monthly_cost": 60.74,
                },
                {
                    "instance_id": "i-bbbb2222",
                    "instance_name": "batch-worker",
                    "instance_type": "m5.xlarge",
                    "avg_cpu_percent": 3.8,
                    "estimated_monthly_cost": 81.82,
                },
            ],
        },
        "ebs": {
            "unattached_volumes_count": 1,
            "unattached_volumes_monthly_cost": 8.00,
            "low_io_volumes_count": 1,
            "low_io_volumes_monthly_cost": 5.00,
            "unattached_volumes": [
                {
                    "VolumeId": "vol-0abc1234",
                    "VolumeType": "gp3",
                    "Size": 100,
                    "AvailabilityZone": "us-east-1a",
                    "estimated_monthly_cost": 8.00,
                }
            ],
            "low_io_volumes": [
                {
                    "VolumeId": "vol-0def5678",
                    "VolumeType": "gp2",
                    "Size": 50,
                    "AvailabilityZone": "us-east-1b",
                    "estimated_monthly_cost": 5.00,
                }
            ],
        },
        "rds": {
            "idle_instances_count": 1,
            "idle_instances_monthly_cost": 75.00,
            "old_snapshots_count": 1,
            "old_snapshots_monthly_cost": 2.30,
            "idle_instances": [
                {
                    "db_instance_id": "mydb-prod",
                    "db_instance_class": "db.t3.medium",
                    "engine": "mysql",
                    "engine_version": "8.0.32",
                    "allocated_storage_gb": 20,
                    "storage_type": "gp2",
                    "multi_az": False,
                    "avg_cpu_percent": 0.5,
                    "avg_connections": 0.0,
                    "estimated_monthly_cost": 75.00,
                }
            ],
            "old_snapshots": [
                {
                    "snapshot_id": "rds:mydb-snap-2024-01-01",
                    "db_instance_id": "mydb-prod",
                    "snapshot_create_time": "2024-01-01T00:00:00+00:00",
                    "allocated_storage_gb": 20,
                    "engine": "mysql",
                    "status": "available",
                    "estimated_monthly_cost": 2.30,
                }
            ],
        },
        "s3": {
            "unused_buckets_count": 1,
            "unused_buckets_monthly_cost": 0.50,
            "unused_buckets": [
                {
                    "bucket_name": "old-backup-bucket",
                    "region": "us-east-1",
                    "creation_date": "2022-03-10T00:00:00+00:00",
                    "size_bytes": 1073741824,
                    "size_formatted": "1.00 GB",
                    "object_count": 42,
                    "total_requests": 3,
                    "estimated_monthly_cost": 0.50,
                }
            ],
            "buckets_without_metrics_count": 0,
            "buckets_without_metrics": [],
        },
    }


@pytest.fixture
def empty_findings():
    """all_findings dict where every scanner returned zero findings."""
    return {
        "account_id": "000000000000",
        "region": "eu-west-1",
        "scan_timestamp": "2025-06-15T02:00:00+00:00",
        "ec2": {
            "idle_instances_count": 0,
            "idle_instances_monthly_cost": 0,
            "idle_instances": [],
        },
        "ebs": {
            "unattached_volumes_count": 0,
            "unattached_volumes_monthly_cost": 0,
            "low_io_volumes_count": 0,
            "low_io_volumes_monthly_cost": 0,
            "unattached_volumes": [],
            "low_io_volumes": [],
        },
        "rds": {
            "idle_instances_count": 0,
            "idle_instances_monthly_cost": 0,
            "old_snapshots_count": 0,
            "old_snapshots_monthly_cost": 0,
            "idle_instances": [],
            "old_snapshots": [],
        },
        "s3": {
            "unused_buckets_count": 0,
            "unused_buckets_monthly_cost": 0,
            "unused_buckets": [],
            "buckets_without_metrics_count": 0,
            "buckets_without_metrics": [],
        },
    }


@pytest.fixture
def reporter():
    return HTMLReporter()


# ------------------------------------------------------------------ #
# Return type and basic structure
# ------------------------------------------------------------------ #

class TestHTMLReporterOutput:
    """Tests for the generated HTML string."""

    def test_returns_string(self, reporter, full_findings):
        result = reporter.generate(full_findings)
        assert isinstance(result, str)

    def test_is_valid_html_skeleton(self, reporter, full_findings):
        result = reporter.generate(full_findings)
        assert "<!DOCTYPE html>" in result
        assert "<html" in result
        assert "</html>" in result
        assert "<body" in result
        assert "</body>" in result

    def test_contains_inline_style_block(self, reporter, full_findings):
        result = reporter.generate(full_findings)
        assert "<style>" in result
        assert "</style>" in result

    def test_contains_viewport_meta(self, reporter, full_findings):
        """Ensures the report is mobile-responsive."""
        result = reporter.generate(full_findings)
        assert 'name="viewport"' in result


# ------------------------------------------------------------------ #
# Header
# ------------------------------------------------------------------ #

class TestHTMLReporterHeader:
    """Tests for the report header section."""

    def test_renders_account_id(self, reporter, full_findings):
        result = reporter.generate(full_findings)
        assert "123456789012" in result

    def test_renders_region(self, reporter, full_findings):
        result = reporter.generate(full_findings)
        assert "us-east-1" in result

    def test_renders_scan_date(self, reporter, full_findings):
        result = reporter.generate(full_findings)
        assert "June 15, 2025" in result

    def test_renders_project_name(self, reporter, full_findings):
        result = reporter.generate(full_findings)
        assert "Cloud Cost Sentinel" in result


# ------------------------------------------------------------------ #
# Summary table
# ------------------------------------------------------------------ #

class TestHTMLReporterSummary:
    """Tests for the 6-category summary table."""

    def test_summary_section_present(self, reporter, full_findings):
        result = reporter.generate(full_findings)
        assert "Summary" in result

    def test_all_six_categories_present(self, reporter, full_findings):
        result = reporter.generate(full_findings)
        assert "Idle Instances" in result          # EC2 + RDS
        assert "Unattached Volumes" in result
        assert "Low I/O Volumes" in result
        assert "Old Snapshots" in result
        assert "Unused Buckets" in result

    def test_total_savings_displayed(self, reporter, full_findings):
        result = reporter.generate(full_findings)
        # 142.56 + 8 + 5 + 75 + 2.30 + 0.50 = 233.36
        assert "233.36" in result

    def test_total_savings_row_highlighted(self, reporter, full_findings):
        """Savings row uses a distinct CSS class."""
        result = reporter.generate(full_findings)
        assert "savings-row" in result

    def test_zero_total_savings_with_empty_findings(self, reporter, empty_findings):
        result = reporter.generate(empty_findings)
        assert "$0.00" in result


# ------------------------------------------------------------------ #
# EC2 detail section
# ------------------------------------------------------------------ #

class TestHTMLReporterEC2Section:
    """Tests for the EC2 idle instances detail section."""

    def test_ec2_section_rendered_when_findings_exist(self, reporter, full_findings):
        result = reporter.generate(full_findings)
        assert "i-aaaa1111" in result
        assert "web-server-01" in result
        assert "t3.large" in result

    def test_ec2_section_shows_both_instances(self, reporter, full_findings):
        result = reporter.generate(full_findings)
        assert "i-bbbb2222" in result
        assert "batch-worker" in result

    def test_ec2_section_not_rendered_when_empty(self, reporter, empty_findings):
        result = reporter.generate(empty_findings)
        # Section header should not appear when no findings
        assert "i-" not in result

    def test_ec2_avg_cpu_displayed(self, reporter, full_findings):
        result = reporter.generate(full_findings)
        assert "1.2%" in result
        assert "3.8%" in result


# ------------------------------------------------------------------ #
# EBS detail section
# ------------------------------------------------------------------ #

class TestHTMLReporterEBSSection:
    """Tests for the EBS volumes detail section."""

    def test_unattached_volume_rendered(self, reporter, full_findings):
        result = reporter.generate(full_findings)
        assert "vol-0abc1234" in result
        assert "gp3" in result

    def test_low_io_volume_rendered(self, reporter, full_findings):
        result = reporter.generate(full_findings)
        assert "vol-0def5678" in result
        assert "gp2" in result

    def test_ebs_section_not_rendered_when_empty(self, reporter, empty_findings):
        result = reporter.generate(empty_findings)
        assert "vol-" not in result

    def test_ebs_section_with_only_unattached(self, reporter, full_findings):
        """Low I/O sub-section should still render if only unattached is present."""
        findings = dict(full_findings)
        findings["ebs"] = dict(full_findings["ebs"])
        findings["ebs"]["low_io_volumes"] = []
        findings["ebs"]["low_io_volumes_count"] = 0
        result = reporter.generate(findings)
        assert "vol-0abc1234" in result
        assert "vol-0def5678" not in result


# ------------------------------------------------------------------ #
# RDS detail section
# ------------------------------------------------------------------ #

class TestHTMLReporterRDSSection:
    """Tests for the RDS instances and snapshots detail section."""

    def test_idle_rds_instance_rendered(self, reporter, full_findings):
        result = reporter.generate(full_findings)
        assert "mydb-prod" in result
        assert "db.t3.medium" in result
        assert "mysql" in result

    def test_old_snapshot_rendered(self, reporter, full_findings):
        result = reporter.generate(full_findings)
        assert "rds:mydb-snap-2024-01-01" in result

    def test_snapshot_date_formatted(self, reporter, full_findings):
        """Snapshot create time should be rendered as YYYY-MM-DD."""
        result = reporter.generate(full_findings)
        assert "2024-01-01" in result

    def test_rds_section_not_rendered_when_empty(self, reporter, empty_findings):
        result = reporter.generate(empty_findings)
        assert "db.t3" not in result
        assert "rds:" not in result


# ------------------------------------------------------------------ #
# S3 detail section
# ------------------------------------------------------------------ #

class TestHTMLReporterS3Section:
    """Tests for the S3 unused buckets detail section."""

    def test_unused_bucket_rendered(self, reporter, full_findings):
        result = reporter.generate(full_findings)
        assert "old-backup-bucket" in result
        assert "1.00 GB" in result

    def test_s3_section_not_rendered_when_empty(self, reporter, empty_findings):
        result = reporter.generate(empty_findings)
        assert "old-backup-bucket" not in result

    def test_request_count_displayed(self, reporter, full_findings):
        result = reporter.generate(full_findings)
        assert "3" in result  # total_requests


# ------------------------------------------------------------------ #
# Footer
# ------------------------------------------------------------------ #

class TestHTMLReporterFooter:
    """Tests for the report footer."""

    def test_footer_present(self, reporter, full_findings):
        result = reporter.generate(full_findings)
        assert "2025-06-15T02:00:00+00:00" in result

    def test_footer_disclaimer_present(self, reporter, full_findings):
        result = reporter.generate(full_findings)
        assert "estimates" in result.lower()


# ------------------------------------------------------------------ #
# Edge cases
# ------------------------------------------------------------------ #

class TestHTMLReporterEdgeCases:
    """Tests for missing or malformed data in all_findings."""

    def test_handles_missing_account_id(self, reporter):
        findings = {
            "region": "us-east-1",
            "scan_timestamp": "2025-06-15T02:00:00+00:00",
            "ec2": {"idle_instances_count": 0, "idle_instances_monthly_cost": 0, "idle_instances": []},
            "ebs": {"unattached_volumes_count": 0, "unattached_volumes_monthly_cost": 0,
                    "low_io_volumes_count": 0, "low_io_volumes_monthly_cost": 0,
                    "unattached_volumes": [], "low_io_volumes": []},
            "rds": {"idle_instances_count": 0, "idle_instances_monthly_cost": 0,
                    "old_snapshots_count": 0, "old_snapshots_monthly_cost": 0,
                    "idle_instances": [], "old_snapshots": []},
            "s3": {"unused_buckets_count": 0, "unused_buckets_monthly_cost": 0,
                   "unused_buckets": [], "buckets_without_metrics_count": 0,
                   "buckets_without_metrics": []},
        }
        result = reporter.generate(findings)
        assert "N/A" in result

    def test_handles_missing_scanner_sections(self, reporter):
        """Report should not crash if a scanner key is missing from findings."""
        findings = {
            "account_id": "123456789012",
            "region": "us-east-1",
            "scan_timestamp": "2025-06-15T02:00:00+00:00",
        }
        result = reporter.generate(findings)
        assert isinstance(result, str)
        assert "Cloud Cost Sentinel" in result

    def test_handles_invalid_timestamp(self, reporter, empty_findings):
        """Malformed scan_timestamp should not crash the reporter."""
        findings = dict(empty_findings)
        findings["scan_timestamp"] = "not-a-real-timestamp"
        result = reporter.generate(findings)
        assert isinstance(result, str)
        assert "not-a-real-timestamp" in result

    def test_handles_zero_cost_instances(self, reporter, full_findings):
        """Instances with $0 estimated cost should display $0.00, not error."""
        findings = dict(full_findings)
        findings["ec2"] = dict(full_findings["ec2"])
        findings["ec2"]["idle_instances"] = [
            {**full_findings["ec2"]["idle_instances"][0], "estimated_monthly_cost": 0}
        ]
        result = reporter.generate(findings)
        assert "$0.00" in result
