"""
Unit tests for EBS Scanner module.

Uses moto to mock AWS EC2 and CloudWatch services.
Fixtures are defined in conftest.py.
"""

import pytest
from unittest.mock import patch
import boto3
from moto import mock_aws

from scanners.ebs_scanner import EBSScanner


class TestEBSScannerInit:
    """Tests for EBSScanner initialization."""

    @mock_aws
    def test_init_with_defaults(self, aws_credentials):
        """Test scanner initializes with correct default values and creates clients."""
        scanner = EBSScanner(region="us-east-1")

        assert scanner.region == "us-east-1"
        assert scanner.days == 14
        assert scanner.io_threshold == 100
        assert scanner.unattached_volumes == []
        assert scanner.low_io_volumes == []
        assert scanner.ec2_client is not None
        assert scanner.cloudwatch_client is not None

    @mock_aws
    def test_init_with_custom_values(self, aws_credentials):
        """Test scanner initializes with custom values."""
        scanner = EBSScanner(region="us-west-2", days=7, io_threshold=50)

        assert scanner.region == "us-west-2"
        assert scanner.days == 7
        assert scanner.io_threshold == 50


class TestGetUnattachedVolumes:
    """Tests for get_unattached_volumes method."""

    @mock_aws
    def test_returns_only_unattached_volumes(self, aws_credentials):
        """Test returns only unattached volumes, not attached ones."""
        ec2 = boto3.client("ec2", region_name="us-east-1")

        # Create VPC and subnet for instance
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        subnet = ec2.create_subnet(
            VpcId=vpc["Vpc"]["VpcId"],
            CidrBlock="10.0.1.0/24",
            AvailabilityZone="us-east-1a"
        )

        # Launch an instance and attach a volume
        instances = ec2.run_instances(
            ImageId="ami-12345678",
            MinCount=1,
            MaxCount=1,
            InstanceType="t2.micro",
            SubnetId=subnet["Subnet"]["SubnetId"],
            Placement={"AvailabilityZone": "us-east-1a"}
        )
        instance_id = instances["Instances"][0]["InstanceId"]

        attached_volume = ec2.create_volume(
            AvailabilityZone="us-east-1a", Size=50, VolumeType="gp2"
        )
        ec2.attach_volume(
            VolumeId=attached_volume["VolumeId"],
            InstanceId=instance_id,
            Device="/dev/sdf"
        )

        # Create unattached volumes
        unattached1 = ec2.create_volume(
            AvailabilityZone="us-east-1a", Size=100, VolumeType="gp2"
        )
        unattached2 = ec2.create_volume(
            AvailabilityZone="us-east-1a", Size=200, VolumeType="gp3"
        )

        scanner = EBSScanner(region="us-east-1")
        volumes = scanner.get_unattached_volumes()

        assert len(volumes) == 2
        volume_ids = [v["VolumeId"] for v in volumes]
        assert unattached1["VolumeId"] in volume_ids
        assert unattached2["VolumeId"] in volume_ids
        assert attached_volume["VolumeId"] not in volume_ids

    @mock_aws
    def test_handles_api_error_gracefully(self, aws_credentials):
        """Test handles API errors gracefully and returns empty list."""
        scanner = EBSScanner(region="us-east-1")

        with patch.object(scanner.ec2_client, "get_paginator") as mock_paginator:
            from botocore.exceptions import ClientError
            mock_paginator.side_effect = ClientError(
                {"Error": {"Code": "UnauthorizedAccess", "Message": "Access Denied"}},
                "DescribeVolumes"
            )
            volumes = scanner.get_unattached_volumes()
            assert volumes == []


class TestGetLowIOVolumes:
    """Tests for get_low_io_volumes method."""

    @mock_aws
    def test_identifies_low_io_volumes_correctly(self, aws_credentials):
        """Test correctly identifies volumes based on combined read+write I/O threshold."""
        ec2 = boto3.client("ec2", region_name="us-east-1")

        low_io_vol = ec2.create_volume(
            AvailabilityZone="us-east-1a", Size=100, VolumeType="gp2"
        )
        high_io_vol = ec2.create_volume(
            AvailabilityZone="us-east-1a", Size=100, VolumeType="gp2"
        )

        scanner = EBSScanner(region="us-east-1", io_threshold=100)

        def mock_metrics(**kwargs):
            vol_id = kwargs["Dimensions"][0]["Value"]
            metric_name = kwargs["MetricName"]

            if vol_id == low_io_vol["VolumeId"]:
                # Low I/O: 20 reads + 15 writes = 35 total
                if metric_name == "VolumeReadOps":
                    return {"Datapoints": [{"Sum": 20.0}]}
                else:  # VolumeWriteOps
                    return {"Datapoints": [{"Sum": 15.0}]}
            else:
                # High I/O: 500 reads + 600 writes = 1100 total
                if metric_name == "VolumeReadOps":
                    return {"Datapoints": [{"Sum": 500.0}]}
                else:  # VolumeWriteOps
                    return {"Datapoints": [{"Sum": 600.0}]}

        with patch.object(scanner.cloudwatch_client, "get_metric_statistics", side_effect=mock_metrics):
            volumes = scanner.get_low_io_volumes()

        assert len(volumes) == 1
        assert volumes[0]["VolumeId"] == low_io_vol["VolumeId"]

    @mock_aws
    def test_high_write_low_read_not_flagged(self, aws_credentials):
        """Test volume with low reads but high writes is NOT flagged as low I/O."""
        ec2 = boto3.client("ec2", region_name="us-east-1")

        volume = ec2.create_volume(
            AvailabilityZone="us-east-1a", Size=100, VolumeType="gp2"
        )

        scanner = EBSScanner(region="us-east-1", io_threshold=100)

        def mock_metrics(**kwargs):
            metric_name = kwargs["MetricName"]
            if metric_name == "VolumeReadOps":
                return {"Datapoints": [{"Sum": 10.0}]}  # Low reads
            else:  # VolumeWriteOps
                return {"Datapoints": [{"Sum": 500.0}]}  # High writes

        with patch.object(scanner.cloudwatch_client, "get_metric_statistics", side_effect=mock_metrics):
            volumes = scanner.get_low_io_volumes()

        # Total I/O is 510, above threshold - should NOT be flagged
        assert len(volumes) == 0

    @mock_aws
    def test_empty_datapoints_flagged_as_low_io(self, aws_credentials):
        """Test volume with no CloudWatch data is flagged as low I/O."""
        ec2 = boto3.client("ec2", region_name="us-east-1")
        volume = ec2.create_volume(
            AvailabilityZone="us-east-1a", Size=100, VolumeType="gp2"
        )

        scanner = EBSScanner(region="us-east-1", io_threshold=100)

        with patch.object(scanner.cloudwatch_client, "get_metric_statistics") as mock_metrics:
            # Both read and write return empty datapoints
            mock_metrics.return_value = {"Datapoints": []}
            volumes = scanner.get_low_io_volumes()

        assert len(volumes) == 1
        assert volumes[0]["VolumeId"] == volume["VolumeId"]

    @mock_aws
    def test_handles_api_error_gracefully(self, aws_credentials):
        """Test handles API errors gracefully and returns empty list."""
        scanner = EBSScanner(region="us-east-1")

        with patch.object(scanner.ec2_client, "get_paginator") as mock_paginator:
            from botocore.exceptions import BotoCoreError
            mock_paginator.side_effect = BotoCoreError()
            volumes = scanner.get_low_io_volumes()
            assert volumes == []


class TestCalculateMonthlyCost:
    """Tests for calculate_monthly_cost method."""

    @mock_aws
    @pytest.mark.parametrize("volume_type,size,expected_cost", [
        ("standard", 100, 5.0),      # 100 * $0.05
        ("gp2", 100, 10.0),          # 100 * $0.10
        ("gp3", 100, 8.0),           # 100 * $0.08
        ("st1", 500, 22.5),          # 500 * $0.045
        ("sc1", 1000, 15.0),         # 1000 * $0.015
    ])
    def test_calculates_storage_cost_by_volume_type(self, aws_credentials, volume_type, size, expected_cost):
        """Test storage cost calculation for different volume types."""
        scanner = EBSScanner(region="us-east-1")
        volume = {"VolumeType": volume_type, "Size": size}
        cost = scanner.calculate_monthly_cost(volume, use_api=False)
        assert cost == expected_cost

    @mock_aws
    @pytest.mark.parametrize("volume_type,size,iops,expected_cost", [
        ("io1", 100, 1000, 100 * 0.125 + 1000 * 0.065),  # storage + IOPS
        ("io2", 100, 2000, 100 * 0.125 + 2000 * 0.065),  # storage + IOPS
        ("gp3", 100, 3000, 8.0),                          # baseline IOPS, no extra cost
        ("gp3", 100, 5000, 8.0 + 2000 * 0.005),          # 2000 IOPS above baseline
    ])
    def test_calculates_iops_cost(self, aws_credentials, volume_type, size, iops, expected_cost):
        """Test IOPS cost calculation for provisioned IOPS volumes."""
        scanner = EBSScanner(region="us-east-1")
        volume = {"VolumeType": volume_type, "Size": size, "Iops": iops}
        cost = scanner.calculate_monthly_cost(volume, use_api=False)
        assert cost == expected_cost

    @mock_aws
    def test_calculates_gp3_throughput_cost(self, aws_credentials):
        """Test gp3 throughput cost above baseline."""
        scanner = EBSScanner(region="us-east-1")

        # At baseline (125 MB/s) - no extra cost
        volume_baseline = {"VolumeType": "gp3", "Size": 100, "Throughput": 125}
        assert scanner.calculate_monthly_cost(volume_baseline, use_api=False) == 8.0

        # Above baseline (500 MB/s) - extra cost for 375 MB/s
        volume_extra = {"VolumeType": "gp3", "Size": 100, "Throughput": 500}
        expected = 8.0 + 375 * 0.06  # $30.50
        assert scanner.calculate_monthly_cost(volume_extra, use_api=False) == round(expected, 2)

    @mock_aws
    def test_handles_edge_cases(self, aws_credentials):
        """Test edge cases: unknown type, missing type, zero size."""
        scanner = EBSScanner(region="us-east-1")

        # Unknown type falls back to gp2 price
        assert scanner.calculate_monthly_cost({"VolumeType": "unknown", "Size": 100}, use_api=False) == 10.0

        # Missing type defaults to standard
        assert scanner.calculate_monthly_cost({"Size": 100}, use_api=False) == 5.0

        # Zero size
        assert scanner.calculate_monthly_cost({"VolumeType": "gp2", "Size": 0}, use_api=False) == 0.0


class TestAnalyzeEBSVolumes:
    """Tests for analyze_ebs_volumes method."""

    @mock_aws
    def test_returns_correct_structure_and_costs(self, aws_credentials):
        """Test returns correct structure with counts and costs."""
        ec2 = boto3.client("ec2", region_name="us-east-1")

        # Create unattached volumes
        ec2.create_volume(AvailabilityZone="us-east-1a", Size=100, VolumeType="gp2")
        ec2.create_volume(AvailabilityZone="us-east-1a", Size=200, VolumeType="gp3")

        scanner = EBSScanner(region="us-east-1", io_threshold=100)

        with patch.object(scanner.cloudwatch_client, "get_metric_statistics") as mock_metrics:
            mock_metrics.return_value = {"Datapoints": [{"Sum": 10.0}]}
            result = scanner.analyze_ebs_volumes(use_pricing_api=False)

        # Verify structure
        assert "unattached_volumes_count" in result
        assert "unattached_volumes_monthly_cost" in result
        assert "low_io_volumes_count" in result
        assert "low_io_volumes_monthly_cost" in result
        assert "total_potential_monthly_savings" in result
        assert "unattached_volumes" in result
        assert "low_io_volumes" in result

        # Verify counts and costs
        assert result["unattached_volumes_count"] == 2
        assert result["unattached_volumes_monthly_cost"] == 26.0  # 100*0.10 + 200*0.08

    @mock_aws
    def test_calculates_costs_for_attached_and_unattached_low_io_volumes(self, aws_credentials):
        """Test cost calculation for both attached low-IO and unattached volumes."""
        ec2 = boto3.client("ec2", region_name="us-east-1")

        # Create VPC and subnet for instance
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        subnet = ec2.create_subnet(
            VpcId=vpc["Vpc"]["VpcId"],
            CidrBlock="10.0.1.0/24",
            AvailabilityZone="us-east-1a"
        )

        # Launch an instance
        instances = ec2.run_instances(
            ImageId="ami-12345678",
            MinCount=1,
            MaxCount=1,
            InstanceType="t2.micro",
            SubnetId=subnet["Subnet"]["SubnetId"],
            Placement={"AvailabilityZone": "us-east-1a"}
        )
        instance_id = instances["Instances"][0]["InstanceId"]

        # Create and attach a volume (will be low I/O but NOT unattached)
        attached_volume = ec2.create_volume(
            AvailabilityZone="us-east-1a", Size=100, VolumeType="gp2"
        )
        ec2.attach_volume(
            VolumeId=attached_volume["VolumeId"],
            InstanceId=instance_id,
            Device="/dev/sdf"
        )

        # Create an unattached volume (will be both unattached AND low I/O)
        ec2.create_volume(AvailabilityZone="us-east-1a", Size=200, VolumeType="gp2")

        scanner = EBSScanner(region="us-east-1", io_threshold=100)

        with patch.object(scanner.cloudwatch_client, "get_metric_statistics") as mock_metrics:
            mock_metrics.return_value = {"Datapoints": [{"Sum": 10.0}]}
            result = scanner.analyze_ebs_volumes(use_pricing_api=False)

        # Unattached: 1 volume (200 GB gp2) = $20
        assert result["unattached_volumes_count"] == 1
        assert result["unattached_volumes_monthly_cost"] == 20.0

        # Low I/O: 3 volumes (root + attached 100GB + unattached 200GB)
        # All have low I/O because we mocked CloudWatch to return low values
        assert result["low_io_volumes_count"] == 3

        # low_io_volumes_monthly_cost includes all low I/O volumes
        # Root volume (~8GB) + attached (100GB) + unattached (200GB) = ~$30.80
        assert result["low_io_volumes_monthly_cost"] > 30.0

        # Total savings = unattached + attached low-IO only (no double counting)
        # $20 (unattached) + root + $10 (attached 100GB)
        assert result["total_potential_monthly_savings"] > result["unattached_volumes_monthly_cost"]

    @mock_aws
    def test_avoids_double_counting_in_total_savings(self, aws_credentials):
        """Test total savings doesn't double count volumes in both lists."""
        ec2 = boto3.client("ec2", region_name="us-east-1")

        # Create an unattached volume (will appear in both lists)
        ec2.create_volume(AvailabilityZone="us-east-1a", Size=100, VolumeType="gp2")

        scanner = EBSScanner(region="us-east-1", io_threshold=100)

        with patch.object(scanner.cloudwatch_client, "get_metric_statistics") as mock_metrics:
            mock_metrics.return_value = {"Datapoints": [{"Sum": 10.0}]}
            result = scanner.analyze_ebs_volumes(use_pricing_api=False)

        # Volume in both lists but counted only once in savings
        assert result["unattached_volumes_count"] == 1
        assert result["low_io_volumes_count"] == 1
        assert result["total_potential_monthly_savings"] == 10.0  # Not 20.0

    @mock_aws
    def test_empty_results_when_no_volumes(self, aws_credentials):
        """Test returns zeros when no volumes exist."""
        scanner = EBSScanner(region="us-east-1")
        result = scanner.analyze_ebs_volumes(use_pricing_api=False)

        assert result["unattached_volumes_count"] == 0
        assert result["unattached_volumes_monthly_cost"] == 0
        assert result["low_io_volumes_count"] == 0
        assert result["low_io_volumes_monthly_cost"] == 0
        assert result["total_potential_monthly_savings"] == 0


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @mock_aws
    @pytest.mark.parametrize("read_io,write_io,threshold,should_flag", [
        (49, 50, 100, True),   # Total 99, just below threshold
        (50, 50, 100, False),  # Total 100, exactly at threshold
        (50, 51, 100, False),  # Total 101, just above threshold
        (0, 0, 100, True),     # Zero I/O
        (0, 0, 0, False),      # Zero threshold (nothing flagged)
    ])
    def test_io_threshold_boundaries(self, aws_credentials, read_io, write_io, threshold, should_flag):
        """Test I/O threshold boundary conditions with combined read+write."""
        ec2 = boto3.client("ec2", region_name="us-east-1")
        ec2.create_volume(AvailabilityZone="us-east-1a", Size=100, VolumeType="gp2")

        scanner = EBSScanner(region="us-east-1", io_threshold=threshold)

        def mock_metrics(**kwargs):
            metric_name = kwargs["MetricName"]
            if metric_name == "VolumeReadOps":
                return {"Datapoints": [{"Sum": float(read_io)}]}
            else:  # VolumeWriteOps
                return {"Datapoints": [{"Sum": float(write_io)}]}

        with patch.object(scanner.cloudwatch_client, "get_metric_statistics", side_effect=mock_metrics):
            volumes = scanner.get_low_io_volumes()

        assert (len(volumes) == 1) == should_flag

    @mock_aws
    def test_days_parameter_affects_cloudwatch_query(self, aws_credentials):
        """Test that days parameter is used in CloudWatch time range."""
        ec2 = boto3.client("ec2", region_name="us-east-1")
        ec2.create_volume(AvailabilityZone="us-east-1a", Size=100, VolumeType="gp2")

        scanner = EBSScanner(region="us-east-1", days=7)

        with patch.object(scanner.cloudwatch_client, "get_metric_statistics") as mock_metrics:
            mock_metrics.return_value = {"Datapoints": []}
            scanner.get_low_io_volumes()

            call_args = mock_metrics.call_args
            start_time = call_args.kwargs.get("StartTime") or call_args[1].get("StartTime")
            end_time = call_args.kwargs.get("EndTime") or call_args[1].get("EndTime")

            assert (end_time - start_time).days == 7
