"""
Integration tests for the main pipeline in Cloud Cost Sentinel.

Tests the full end-to-end flow of main() with all four AWS services
mocked via moto, ensuring scanner method calls, key references, and
the overall pipeline execute without errors.
"""

import os
import sys
import pytest
import boto3
from moto import mock_aws
from unittest.mock import patch
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from main import main, verify_aws_credentials


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_ec2(ec2_client):
    """Create a running EC2 instance."""
    vpc = ec2_client.create_vpc(CidrBlock="10.0.0.0/16")
    subnet = ec2_client.create_subnet(
        VpcId=vpc["Vpc"]["VpcId"], CidrBlock="10.0.1.0/24"
    )
    ec2_client.run_instances(
        ImageId="ami-12345678",
        MinCount=1,
        MaxCount=1,
        InstanceType="t3.medium",
        SubnetId=subnet["Subnet"]["SubnetId"],
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [{"Key": "Name", "Value": "test-instance"}],
        }],
    )


def _setup_ebs(ec2_client):
    """Create an unattached EBS volume."""
    ec2_client.create_volume(
        AvailabilityZone="us-east-1a",
        Size=20,
        VolumeType="gp2",
    )


def _setup_rds(rds_client):
    """Create an available RDS instance and a manual snapshot."""
    rds_client.create_db_instance(
        DBInstanceIdentifier="test-db",
        DBInstanceClass="db.t3.micro",
        Engine="postgres",
        MasterUsername="admin",
        MasterUserPassword="password123",
        AllocatedStorage=20,
    )
    rds_client.create_db_snapshot(
        DBInstanceIdentifier="test-db",
        DBSnapshotIdentifier="test-db-snapshot",
    )


def _setup_s3(s3_client):
    """Create an S3 bucket."""
    s3_client.create_bucket(Bucket="test-bucket-sentinel")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def aws_env():
    """Set mock AWS environment variables."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    yield
    for key in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
                "AWS_SECURITY_TOKEN", "AWS_SESSION_TOKEN"]:
        os.environ.pop(key, None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestVerifyAwsCredentials:
    """Tests for the credential verification step."""

    @mock_aws
    def test_returns_success_with_valid_credentials(self, aws_env):
        success, account_id, region, error = verify_aws_credentials()

        assert success is True
        assert account_id is not None
        assert region is not None
        assert error is None

    def test_returns_failure_without_credentials(self):
        for key in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
                    "AWS_SECURITY_TOKEN", "AWS_SESSION_TOKEN"]:
            os.environ.pop(key, None)

        success, account_id, region, error = verify_aws_credentials()

        assert success is False
        assert account_id is None
        assert error is not None


class TestMainPipeline:
    """End-to-end integration tests for the main() pipeline."""

    @mock_aws
    def test_main_returns_zero_on_success(self, aws_env):
        """main() should complete and return 0 with all AWS resources mocked."""
        ec2_client = boto3.client("ec2", region_name="us-east-1")
        rds_client = boto3.client("rds", region_name="us-east-1")
        s3_client = boto3.client("s3", region_name="us-east-1")

        _setup_ec2(ec2_client)
        _setup_ebs(ec2_client)
        _setup_rds(rds_client)
        _setup_s3(s3_client)

        # Patch pricing utils to avoid real HTTP calls
        with patch("scanners.ec2_scanner.calculate_ec2_monthly_cost", return_value=50.0), \
             patch("scanners.ebs_scanner.calculate_ebs_monthly_cost", return_value=10.0), \
             patch("scanners.rds_scanner.calculate_rds_monthly_cost", return_value=80.0), \
             patch("scanners.rds_scanner.calculate_snapshot_monthly_cost", return_value=5.0), \
             patch("scanners.s3_scanner.calculate_bucket_monthly_cost", return_value=2.0):

            result = main()

        assert result == 0

    @mock_aws
    def test_main_with_no_resources(self, aws_env):
        """main() should complete successfully even when no AWS resources exist."""
        with patch("scanners.ec2_scanner.calculate_ec2_monthly_cost", return_value=0.0), \
             patch("scanners.ebs_scanner.calculate_ebs_monthly_cost", return_value=0.0), \
             patch("scanners.rds_scanner.calculate_rds_monthly_cost", return_value=0.0), \
             patch("scanners.rds_scanner.calculate_snapshot_monthly_cost", return_value=0.0), \
             patch("scanners.s3_scanner.calculate_bucket_monthly_cost", return_value=0.0):

            result = main()

        assert result == 0

    @mock_aws
    def test_main_ec2_scanner_keys_are_valid(self, aws_env):
        """EC2 idle instance dicts must contain all keys referenced in main()."""
        ec2_client = boto3.client("ec2", region_name="us-east-1")
        _setup_ec2(ec2_client)

        with patch("scanners.ec2_scanner.calculate_ec2_monthly_cost", return_value=50.0), \
             patch("scanners.ebs_scanner.calculate_ebs_monthly_cost", return_value=0.0), \
             patch("scanners.rds_scanner.calculate_rds_monthly_cost", return_value=0.0), \
             patch("scanners.rds_scanner.calculate_snapshot_monthly_cost", return_value=0.0), \
             patch("scanners.s3_scanner.calculate_bucket_monthly_cost", return_value=0.0):

            from scanners.ec2_scanner import EC2Scanner
            scanner = EC2Scanner(region="us-east-1", days=7, idle_threshold=100.0)
            idle_instances = scanner.analyze_ec2_instances(use_pricing_api=False)

        for instance in idle_instances:
            assert "instance_id" in instance
            assert "instance_name" in instance
            assert "avg_cpu_percent" in instance

    @mock_aws
    def test_main_ebs_scanner_keys_are_valid(self, aws_env):
        """EBS volume dicts must contain all keys referenced in main()."""
        ec2_client = boto3.client("ec2", region_name="us-east-1")
        _setup_ebs(ec2_client)

        with patch("scanners.ebs_scanner.calculate_ebs_monthly_cost", return_value=10.0):
            from scanners.ebs_scanner import EBSScanner
            scanner = EBSScanner(region="us-east-1", days=14, io_threshold=99)
            summary = scanner.analyze_ebs_volumes(use_pricing_api=False)

        assert "unattached_volumes_count" in summary
        assert "unattached_volumes_monthly_cost" in summary
        assert "low_io_volumes_count" in summary
        assert "low_io_volumes_monthly_cost" in summary

        for volume in summary["unattached_volumes"]:
            assert "VolumeId" in volume
            assert "Size" in volume
            assert "VolumeType" in volume

        for volume in summary["low_io_volumes"]:
            assert "VolumeId" in volume
            assert "Size" in volume
            assert "VolumeType" in volume

    @mock_aws
    def test_main_rds_scanner_keys_are_valid(self, aws_env):
        """RDS idle instance and snapshot dicts must contain all keys referenced in main()."""
        rds_client = boto3.client("rds", region_name="us-east-1")
        _setup_rds(rds_client)

        with patch("scanners.rds_scanner.calculate_rds_monthly_cost", return_value=80.0), \
             patch("scanners.rds_scanner.calculate_snapshot_monthly_cost", return_value=5.0):

            from scanners.rds_scanner import RDSScanner
            scanner = RDSScanner(region="us-east-1", days=7, cpu_threshold=100.0, connections_threshold=9999)
            scanner.find_old_snapshots()
            scanner.analyze_rds_instances(use_pricing_api=False)
            summary = scanner.get_scan_summary()

        assert "idle_instances_count" in summary
        assert "idle_instances_monthly_cost" in summary
        assert "old_snapshots_count" in summary
        assert "old_snapshots_monthly_cost" in summary

        for instance in summary["idle_instances"]:
            assert "db_instance_id" in instance
            assert "db_instance_class" in instance
            assert "avg_cpu_percent" in instance
            assert "avg_connections" in instance

        for snapshot in summary["old_snapshots"]:
            assert "snapshot_id" in snapshot
            assert "db_instance_id" in snapshot
            assert "snapshot_create_time" in snapshot

    @mock_aws
    def test_main_s3_scanner_keys_are_valid(self, aws_env):
        """S3 unused bucket dicts must contain all keys referenced in main()."""
        s3_client = boto3.client("s3", region_name="us-east-1")
        _setup_s3(s3_client)

        with patch("scanners.s3_scanner.calculate_bucket_monthly_cost", return_value=2.0):
            from scanners.s3_scanner import S3Scanner
            scanner = S3Scanner(region="us-east-1", days=60, request_threshold=10)
            scanner.analyze_s3_buckets()
            summary = scanner.get_scan_summary()

        assert "unused_buckets_count" in summary
        assert "unused_buckets_monthly_cost" in summary

        for bucket in summary["unused_buckets"]:
            assert "bucket_name" in bucket
            assert "creation_date" in bucket
            assert "total_requests" in bucket
