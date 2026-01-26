"""
Unit tests for EC2 Scanner module.

Uses moto to mock AWS EC2 and CloudWatch services.
Fixtures are defined in conftest.py.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
import boto3
from moto import mock_aws

from scanners.ec2_scanner import EC2Scanner



class TestEC2ScannerInit:
    """Tests for EC2Scanner initialization."""

    @mock_aws
    def test_init_with_defaults(self, aws_credentials):
        """Test scanner initializes with default values."""
        scanner = EC2Scanner(region="us-east-1")

        assert scanner.region == "us-east-1"
        assert scanner.days == 14
        assert scanner.idle_threshold == 5.0
        assert scanner.idle_instances == []

    @mock_aws
    def test_init_with_custom_values(self, aws_credentials):
        """Test scanner initializes with custom values."""
        scanner = EC2Scanner(region="us-west-2", days=7, idle_threshold=10.0)

        assert scanner.region == "us-west-2"
        assert scanner.days == 7
        assert scanner.idle_threshold == 10.0

    @mock_aws
    def test_init_creates_boto3_clients(self, aws_credentials):
        """Test scanner creates EC2 and CloudWatch clients."""
        scanner = EC2Scanner(region="us-east-1")

        assert scanner.ec2_client is not None
        assert scanner.cloudwatch_client is not None


class TestGetRunningEC2Instances:
    """Tests for get_running_ec2_instances method."""

    @mock_aws
    def test_returns_empty_list_when_no_instances(self, aws_credentials):
        """Test returns empty list when no EC2 instances exist."""
        scanner = EC2Scanner(region="us-east-1")
        instances = scanner.get_running_ec2_instances()

        assert instances == []

    @mock_aws
    def test_returns_running_instances_only(self, aws_credentials):
        """Test returns only running instances, not stopped ones."""
        ec2 = boto3.client("ec2", region_name="us-east-1")

        # Create a VPC and subnet (required for instances)
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        subnet = ec2.create_subnet(
            VpcId=vpc["Vpc"]["VpcId"],
            CidrBlock="10.0.1.0/24"
        )

        # Launch instances
        running_instances = ec2.run_instances(
            ImageId="ami-12345678",
            MinCount=2,
            MaxCount=2,
            InstanceType="t2.micro",
            SubnetId=subnet["Subnet"]["SubnetId"]
        )

        # Stop one instance
        instance_to_stop = running_instances["Instances"][0]["InstanceId"]
        ec2.stop_instances(InstanceIds=[instance_to_stop])

        scanner = EC2Scanner(region="us-east-1")
        instances = scanner.get_running_ec2_instances()

        # Should only return 1 running instance
        assert len(instances) == 1
        assert instances[0]["instance_id"] != instance_to_stop

    @mock_aws
    def test_extracts_instance_metadata(self, aws_credentials):
        """Test extracts correct metadata from instances."""
        ec2 = boto3.client("ec2", region_name="us-east-1")

        # Create VPC and subnet
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        subnet = ec2.create_subnet(
            VpcId=vpc["Vpc"]["VpcId"],
            CidrBlock="10.0.1.0/24"
        )

        # Launch an instance
        response = ec2.run_instances(
            ImageId="ami-12345678",
            MinCount=1,
            MaxCount=1,
            InstanceType="t3.medium",
            SubnetId=subnet["Subnet"]["SubnetId"],
            TagSpecifications=[
                {
                    "ResourceType": "instance",
                    "Tags": [{"Key": "Name", "Value": "test-instance"}]
                }
            ]
        )

        scanner = EC2Scanner(region="us-east-1")
        instances = scanner.get_running_ec2_instances()

        assert len(instances) == 1
        instance = instances[0]

        assert "instance_id" in instance
        assert instance["instance_type"] == "t3.medium"
        assert instance["instance_name"] == "test-instance"
        assert "launch_time" in instance
        assert "private_ip" in instance
        assert "public_ip" in instance

    @mock_aws
    def test_handles_instance_without_name_tag(self, aws_credentials):
        """Test handles instances without Name tag gracefully."""
        ec2 = boto3.client("ec2", region_name="us-east-1")

        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        subnet = ec2.create_subnet(
            VpcId=vpc["Vpc"]["VpcId"],
            CidrBlock="10.0.1.0/24"
        )

        # Launch instance without tags
        ec2.run_instances(
            ImageId="ami-12345678",
            MinCount=1,
            MaxCount=1,
            InstanceType="t2.micro",
            SubnetId=subnet["Subnet"]["SubnetId"]
        )

        scanner = EC2Scanner(region="us-east-1")
        instances = scanner.get_running_ec2_instances()

        assert len(instances) == 1
        assert instances[0]["instance_name"] == "N/A"

    @mock_aws
    def test_handles_api_error_gracefully(self, aws_credentials):
        """Test handles EC2 API errors gracefully."""
        scanner = EC2Scanner(region="us-east-1")

        # Mock the EC2 client to raise an exception
        with patch.object(scanner.ec2_client, 'get_paginator') as mock_paginator:
            from botocore.exceptions import ClientError
            mock_paginator.side_effect = ClientError(
                {"Error": {"Code": "UnauthorizedOperation", "Message": "Access Denied"}},
                "DescribeInstances"
            )

            instances = scanner.get_running_ec2_instances()
            assert instances == []


class TestGetEC2CPUUtilization:
    """Tests for get_ec2_cpu_utilization method."""

    @mock_aws
    def test_returns_empty_list_when_no_metrics(self, aws_credentials):
        """Test returns empty list when no CloudWatch metrics exist."""
        scanner = EC2Scanner(region="us-east-1")
        datapoints = scanner.get_ec2_cpu_utilization("i-nonexistent")

        assert datapoints == []

    @mock_aws
    def test_handles_cloudwatch_api_error(self, aws_credentials):
        """Test handles CloudWatch API errors gracefully."""
        scanner = EC2Scanner(region="us-east-1")

        with patch.object(scanner.cloudwatch_client, 'get_metric_statistics') as mock_cw:
            from botocore.exceptions import ClientError
            mock_cw.side_effect = ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
                "GetMetricStatistics"
            )

            datapoints = scanner.get_ec2_cpu_utilization("i-12345678")
            assert datapoints == []

    @mock_aws
    def test_uses_correct_time_range(self, aws_credentials):
        """Test uses correct time range based on days parameter."""
        scanner = EC2Scanner(region="us-east-1", days=7)

        with patch.object(scanner.cloudwatch_client, 'get_metric_statistics') as mock_cw:
            mock_cw.return_value = {"Datapoints": []}

            scanner.get_ec2_cpu_utilization("i-12345678")

            # Verify the call was made with correct parameters
            call_args = mock_cw.call_args
            assert call_args is not None

            kwargs = call_args.kwargs if call_args.kwargs else call_args[1]
            start_time = kwargs["StartTime"]
            end_time = kwargs["EndTime"]

            # Check that the time range is approximately 7 days
            time_diff = end_time - start_time
            assert 6 <= time_diff.days <= 7


class TestCalculateAverageCPU:
    """Tests for calculate_average_cpu method."""

    @mock_aws
    def test_returns_none_for_empty_datapoints(self, aws_credentials):
        """Test returns None when datapoints list is empty."""
        scanner = EC2Scanner(region="us-east-1")
        result = scanner.calculate_average_cpu([])

        assert result is None

    @mock_aws
    def test_calculates_correct_average(self, aws_credentials):
        """Test calculates correct average from datapoints."""
        scanner = EC2Scanner(region="us-east-1")

        datapoints = [
            {"Average": 10.0},
            {"Average": 20.0},
            {"Average": 30.0},
        ]

        result = scanner.calculate_average_cpu(datapoints)
        assert result == 20.0

    @mock_aws
    def test_handles_single_datapoint(self, aws_credentials):
        """Test handles single datapoint correctly."""
        scanner = EC2Scanner(region="us-east-1")

        datapoints = [{"Average": 42.5}]
        result = scanner.calculate_average_cpu(datapoints)

        assert result == 42.5


class TestAnalyzeEC2Instances:
    """Tests for analyze_ec2_instances method."""

    @mock_aws
    def test_returns_empty_list_when_no_instances(self, aws_credentials):
        """Test returns empty list when no instances exist."""
        scanner = EC2Scanner(region="us-east-1")
        result = scanner.analyze_ec2_instances()

        assert result == []
        assert scanner.idle_instances == []

    @mock_aws
    def test_identifies_idle_instance(self, aws_credentials):
        """Test correctly identifies idle instances."""
        scanner = EC2Scanner(region="us-east-1", idle_threshold=5.0)

        # Mock get_running_ec2_instances
        mock_instances = [{
            "instance_id": "i-idle123",
            "instance_name": "idle-server",
            "instance_type": "t3.medium",
            "launch_time": datetime.now(timezone.utc),
            "private_ip": "10.0.1.10",
            "public_ip": "N/A",
        }]

        # Mock get_ec2_cpu_utilization to return low CPU
        mock_cpu_data = [
            {"Average": 1.0},
            {"Average": 2.0},
            {"Average": 3.0},
        ]

        with patch.object(scanner, 'get_running_ec2_instances', return_value=mock_instances):
            with patch.object(scanner, 'get_ec2_cpu_utilization', return_value=mock_cpu_data):
                result = scanner.analyze_ec2_instances()

        assert len(result) == 1
        assert result[0]["instance_id"] == "i-idle123"
        assert result[0]["avg_cpu_percent"] == 2.0

    @mock_aws
    def test_does_not_flag_active_instance(self, aws_credentials):
        """Test does not flag active instances as idle."""
        scanner = EC2Scanner(region="us-east-1", idle_threshold=5.0)

        mock_instances = [{
            "instance_id": "i-active123",
            "instance_name": "active-server",
            "instance_type": "t3.large",
            "launch_time": datetime.now(timezone.utc),
            "private_ip": "10.0.1.20",
            "public_ip": "N/A",
        }]

        # Mock CPU data with high utilization
        mock_cpu_data = [
            {"Average": 60.0},
            {"Average": 70.0},
            {"Average": 80.0},
        ]

        with patch.object(scanner, 'get_running_ec2_instances', return_value=mock_instances):
            with patch.object(scanner, 'get_ec2_cpu_utilization', return_value=mock_cpu_data):
                result = scanner.analyze_ec2_instances()

        assert len(result) == 0

    @mock_aws
    def test_handles_instance_without_cpu_data(self, aws_credentials):
        """Test handles instances without CPU data gracefully."""
        scanner = EC2Scanner(region="us-east-1")

        mock_instances = [{
            "instance_id": "i-nodata123",
            "instance_name": "no-data-server",
            "instance_type": "t2.micro",
            "launch_time": datetime.now(timezone.utc),
            "private_ip": "10.0.1.30",
            "public_ip": "N/A",
        }]

        with patch.object(scanner, 'get_running_ec2_instances', return_value=mock_instances):
            with patch.object(scanner, 'get_ec2_cpu_utilization', return_value=[]):
                result = scanner.analyze_ec2_instances()

        # Should not crash, should return empty (no idle instances detected)
        assert len(result) == 0

    @mock_aws
    def test_resets_idle_instances_on_each_scan(self, aws_credentials):
        """Test resets idle_instances list on each scan."""
        scanner = EC2Scanner(region="us-east-1")

        # Pre-populate idle_instances
        scanner.idle_instances = [{"instance_id": "i-old123"}]

        with patch.object(scanner, 'get_running_ec2_instances', return_value=[]):
            scanner.analyze_ec2_instances()

        assert scanner.idle_instances == []

    @mock_aws
    def test_idle_instance_contains_required_fields(self, aws_credentials):
        """Test idle instance dictionary contains all required fields."""
        scanner = EC2Scanner(region="us-east-1", days=7, idle_threshold=5.0)

        mock_instances = [{
            "instance_id": "i-test123",
            "instance_name": "test-server",
            "instance_type": "t3.small",
            "launch_time": datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            "private_ip": "10.0.1.40",
            "public_ip": "54.123.45.67",
        }]

        mock_cpu_data = [{"Average": 2.5}]

        with patch.object(scanner, 'get_running_ec2_instances', return_value=mock_instances):
            with patch.object(scanner, 'get_ec2_cpu_utilization', return_value=mock_cpu_data):
                result = scanner.analyze_ec2_instances()

        assert len(result) == 1
        idle_instance = result[0]

        # Check all required fields
        assert "instance_id" in idle_instance
        assert "instance_name" in idle_instance
        assert "instance_type" in idle_instance
        assert "launch_time" in idle_instance
        assert "private_ip" in idle_instance
        assert "public_ip" in idle_instance
        assert "avg_cpu_percent" in idle_instance
        assert "analysis_period_days" in idle_instance
        assert "idle_threshold" in idle_instance
        assert "recommendation" in idle_instance

        # Check values
        assert idle_instance["analysis_period_days"] == 7
        assert idle_instance["idle_threshold"] == 5.0
        assert "stopping or terminating" in idle_instance["recommendation"].lower()


class TestGetScanSummary:
    """Tests for get_scan_summary method."""

    @mock_aws
    def test_returns_correct_summary_structure(self, aws_credentials):
        """Test returns summary with correct structure."""
        scanner = EC2Scanner(region="us-east-1", days=7, idle_threshold=5.0)

        summary = scanner.get_scan_summary()

        assert "scanner" in summary
        assert "region" in summary
        assert "analysis_period_days" in summary
        assert "idle_threshold_percent" in summary
        assert "idle_instances_count" in summary
        assert "idle_instances" in summary
        assert "scan_timestamp" in summary

    @mock_aws
    def test_summary_reflects_scanner_config(self, aws_credentials):
        """Test summary reflects scanner configuration."""
        scanner = EC2Scanner(region="us-west-2", days=30, idle_threshold=10.0)

        summary = scanner.get_scan_summary()

        assert summary["scanner"] == "EC2Scanner"
        assert summary["region"] == "us-west-2"
        assert summary["analysis_period_days"] == 30
        assert summary["idle_threshold_percent"] == 10.0

    @mock_aws
    def test_summary_includes_idle_instances(self, aws_credentials):
        """Test summary includes idle instances list."""
        scanner = EC2Scanner(region="us-east-1")

        # Manually add idle instances
        scanner.idle_instances = [
            {"instance_id": "i-123", "avg_cpu_percent": 2.0},
            {"instance_id": "i-456", "avg_cpu_percent": 3.0},
        ]

        summary = scanner.get_scan_summary()

        assert summary["idle_instances_count"] == 2
        assert len(summary["idle_instances"]) == 2

    @mock_aws
    def test_summary_timestamp_is_valid_iso_format(self, aws_credentials):
        """Test summary timestamp is valid ISO format."""
        scanner = EC2Scanner(region="us-east-1")

        summary = scanner.get_scan_summary()

        # Should not raise an exception
        timestamp = datetime.fromisoformat(summary["scan_timestamp"].replace("Z", "+00:00"))
        assert timestamp is not None


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @mock_aws
    def test_zero_idle_threshold(self, aws_credentials):
        """Test with zero idle threshold (only completely idle instances)."""
        scanner = EC2Scanner(region="us-east-1", idle_threshold=0.0)

        mock_instances = [{
            "instance_id": "i-test",
            "instance_name": "test",
            "instance_type": "t2.micro",
            "launch_time": datetime.now(timezone.utc),
            "private_ip": "10.0.1.1",
            "public_ip": "N/A",
        }]

        # CPU at exactly 0
        mock_cpu_data = [{"Average": 0.0}]

        with patch.object(scanner, 'get_running_ec2_instances', return_value=mock_instances):
            with patch.object(scanner, 'get_ec2_cpu_utilization', return_value=mock_cpu_data):
                result = scanner.analyze_ec2_instances()

        assert len(result) == 1

    @mock_aws
    def test_cpu_exactly_at_threshold(self, aws_credentials):
        """Test instance with CPU exactly at threshold is considered idle."""
        scanner = EC2Scanner(region="us-east-1", idle_threshold=5.0)

        mock_instances = [{
            "instance_id": "i-boundary",
            "instance_name": "boundary-test",
            "instance_type": "t2.micro",
            "launch_time": datetime.now(timezone.utc),
            "private_ip": "10.0.1.1",
            "public_ip": "N/A",
        }]

        # CPU exactly at threshold
        mock_cpu_data = [{"Average": 5.0}]

        with patch.object(scanner, 'get_running_ec2_instances', return_value=mock_instances):
            with patch.object(scanner, 'get_ec2_cpu_utilization', return_value=mock_cpu_data):
                result = scanner.analyze_ec2_instances()

        # Should be considered idle (<=)
        assert len(result) == 1

    @mock_aws
    def test_cpu_just_above_threshold(self, aws_credentials):
        """Test instance with CPU just above threshold is not idle."""
        scanner = EC2Scanner(region="us-east-1", idle_threshold=5.0)

        mock_instances = [{
            "instance_id": "i-above",
            "instance_name": "above-test",
            "instance_type": "t2.micro",
            "launch_time": datetime.now(timezone.utc),
            "private_ip": "10.0.1.1",
            "public_ip": "N/A",
        }]

        # CPU just above threshold
        mock_cpu_data = [{"Average": 5.01}]

        with patch.object(scanner, 'get_running_ec2_instances', return_value=mock_instances):
            with patch.object(scanner, 'get_ec2_cpu_utilization', return_value=mock_cpu_data):
                result = scanner.analyze_ec2_instances()

        # Should NOT be considered idle
        assert len(result) == 0

    @mock_aws
    def test_large_number_of_instances(self, aws_credentials):
        """Test handles large number of instances."""
        scanner = EC2Scanner(region="us-east-1", idle_threshold=5.0)

        # Create 100 mock instances
        mock_instances = [
            {
                "instance_id": f"i-{i:05d}",
                "instance_name": f"server-{i}",
                "instance_type": "t2.micro",
                "launch_time": datetime.now(timezone.utc),
                "private_ip": f"10.0.1.{i % 256}",
                "public_ip": "N/A",
            }
            for i in range(100)
        ]

        # Half are idle, half are active
        def mock_cpu(instance_id):
            idx = int(instance_id.split("-")[1])
            if idx < 50:
                return [{"Average": 2.0}]  # Idle
            return [{"Average": 50.0}]  # Active

        with patch.object(scanner, 'get_running_ec2_instances', return_value=mock_instances):
            with patch.object(scanner, 'get_ec2_cpu_utilization', side_effect=mock_cpu):
                result = scanner.analyze_ec2_instances()

        assert len(result) == 50
