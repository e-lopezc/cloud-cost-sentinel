"""
Unit tests for RDS Scanner Module.

Tests cover:
- Initialization
- Getting RDS instances
- CloudWatch metrics retrieval (CPU and connections)
- Average calculation
- Idle instance detection
- Old snapshot detection
- Scan summary
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError, BotoCoreError

from src.scanners.rds_scanner import RDSScanner


class TestRDSScannerInit:
    """Tests for RDSScanner initialization."""

    def test_init_with_defaults(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1")

        assert scanner.region == "us-east-1"
        assert scanner.days == 14
        assert scanner.cpu_threshold == 5.0
        assert scanner.connections_threshold == 1
        assert scanner.snapshot_age_days == 90
        assert scanner.idle_instances == []
        assert scanner.old_snapshots == []

    def test_init_with_custom_values(self):
        with patch("boto3.client"):
            scanner = RDSScanner(
                region="eu-west-1",
                days=7,
                cpu_threshold=10.0,
                connections_threshold=5,
                snapshot_age_days=60,
            )

        assert scanner.region == "eu-west-1"
        assert scanner.days == 7
        assert scanner.cpu_threshold == 10.0
        assert scanner.connections_threshold == 5
        assert scanner.snapshot_age_days == 60

    def test_init_creates_boto3_clients(self):
        with patch("boto3.client") as mock_client:
            RDSScanner(region="us-west-2")

        calls = mock_client.call_args_list
        assert any(call[0] == ("rds",) for call in calls)
        assert any(call[0] == ("cloudwatch",) for call in calls)


class TestGetRDSInstances:
    """Tests for get_rds_instances method."""

    def test_returns_empty_list_when_no_instances(self):
        with patch("boto3.client") as mock_client:
            scanner = RDSScanner(region="us-east-1")
            mock_paginator = MagicMock()
            mock_paginator.paginate.return_value = [{"DBInstances": []}]
            scanner.rds_client.get_paginator.return_value = mock_paginator

            result = scanner.get_rds_instances()

        assert result == []

    def test_returns_rds_instances(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1")
            mock_paginator = MagicMock()
            mock_paginator.paginate.return_value = [
                {
                    "DBInstances": [
                        {
                            "DBInstanceIdentifier": "my-database",
                            "DBInstanceClass": "db.t3.micro",
                            "Engine": "mysql",
                            "EngineVersion": "8.0.35",
                            "DBInstanceStatus": "available",
                            "AllocatedStorage": 20,
                            "MultiAZ": False,
                            "StorageType": "gp2",
                        }
                    ]
                }
            ]
            scanner.rds_client.get_paginator.return_value = mock_paginator

            result = scanner.get_rds_instances()

        assert len(result) == 1
        assert result[0]["db_instance_id"] == "my-database"
        assert result[0]["db_instance_class"] == "db.t3.micro"
        assert result[0]["engine"] == "mysql"
        assert result[0]["status"] == "available"

    def test_handles_api_error_gracefully(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1")
            scanner.rds_client.get_paginator.side_effect = ClientError(
                {"Error": {"Code": "500", "Message": "Internal Error"}},
                "DescribeDBInstances",
            )

            result = scanner.get_rds_instances()

        assert result == []


class TestGetCPUUtilization:
    """Tests for get_cpu_utilization method."""

    def test_returns_datapoints(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1")
            scanner.cloudwatch_client.get_metric_statistics.return_value = {
                "Datapoints": [{"Average": 2.5}, {"Average": 3.0}]
            }

            result = scanner.get_cpu_utilization("my-database")

        assert len(result) == 2
        assert result[0]["Average"] == 2.5

    def test_returns_empty_list_on_error(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1")
            scanner.cloudwatch_client.get_metric_statistics.side_effect = ClientError(
                {"Error": {"Code": "500", "Message": "Error"}},
                "GetMetricStatistics",
            )

            result = scanner.get_cpu_utilization("my-database")

        assert result == []


class TestGetDatabaseConnections:
    """Tests for get_database_connections method."""

    def test_returns_datapoints(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1")
            scanner.cloudwatch_client.get_metric_statistics.return_value = {
                "Datapoints": [{"Average": 0.5}, {"Average": 0.8}]
            }

            result = scanner.get_database_connections("my-database")

        assert len(result) == 2

    def test_returns_empty_list_on_error(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1")
            scanner.cloudwatch_client.get_metric_statistics.side_effect = BotoCoreError()

            result = scanner.get_database_connections("my-database")

        assert result == []


class TestCalculateAverage:
    """Tests for calculate_average method."""

    def test_returns_none_for_empty_datapoints(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1")

        assert scanner.calculate_average([]) is None

    def test_calculates_correct_average(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1")
            datapoints = [{"Average": 2.0}, {"Average": 4.0}, {"Average": 6.0}]

            result = scanner.calculate_average(datapoints)

        assert result == 4.0

    def test_handles_single_datapoint(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1")

        assert scanner.calculate_average([{"Average": 5.5}]) == 5.5


class TestIsInstanceIdle:
    """Tests for is_instance_idle method."""

    def test_idle_when_below_thresholds(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1", cpu_threshold=5.0, connections_threshold=1)

            result = scanner.is_instance_idle(avg_cpu=2.0, avg_connections=0.5)

        assert result is True

    def test_not_idle_when_cpu_above_threshold(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1", cpu_threshold=5.0, connections_threshold=1)

            result = scanner.is_instance_idle(avg_cpu=10.0, avg_connections=0.5)

        assert result is False

    def test_not_idle_when_connections_above_threshold(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1", cpu_threshold=5.0, connections_threshold=1)

            result = scanner.is_instance_idle(avg_cpu=2.0, avg_connections=5.0)

        assert result is False

    def test_not_idle_when_cpu_is_none(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1")

            result = scanner.is_instance_idle(avg_cpu=None, avg_connections=0.5)

        assert result is False

    def test_not_idle_when_connections_is_none(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1")

            result = scanner.is_instance_idle(avg_cpu=2.0, avg_connections=None)

        assert result is False

    def test_idle_at_exact_threshold(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1", cpu_threshold=5.0, connections_threshold=1)

            result = scanner.is_instance_idle(avg_cpu=5.0, avg_connections=1.0)

        assert result is True


class TestGetManualSnapshots:
    """Tests for get_manual_snapshots method."""

    def test_returns_manual_snapshots(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1")
            mock_paginator = MagicMock()
            mock_paginator.paginate.return_value = [
                {
                    "DBSnapshots": [
                        {
                            "DBSnapshotIdentifier": "my-snapshot",
                            "DBInstanceIdentifier": "my-database",
                            "SnapshotCreateTime": datetime(2024, 1, 1, tzinfo=timezone.utc),
                            "AllocatedStorage": 20,
                            "Engine": "mysql",
                            "Status": "available",
                        }
                    ]
                }
            ]
            scanner.rds_client.get_paginator.return_value = mock_paginator

            result = scanner.get_manual_snapshots()

        assert len(result) == 1
        assert result[0]["snapshot_id"] == "my-snapshot"
        assert result[0]["db_instance_id"] == "my-database"

    def test_returns_empty_list_on_error(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1")
            scanner.rds_client.get_paginator.side_effect = ClientError(
                {"Error": {"Code": "500", "Message": "Error"}},
                "DescribeDBSnapshots",
            )

            result = scanner.get_manual_snapshots()

        assert result == []


class TestFindOldSnapshots:
    """Tests for find_old_snapshots method."""

    def test_finds_old_snapshots(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1", snapshot_age_days=90)
            mock_paginator = MagicMock()
            old_date = datetime.now(timezone.utc) - timedelta(days=100)
            mock_paginator.paginate.return_value = [
                {
                    "DBSnapshots": [
                        {
                            "DBSnapshotIdentifier": "old-snapshot",
                            "DBInstanceIdentifier": "my-database",
                            "SnapshotCreateTime": old_date,
                            "AllocatedStorage": 20,
                            "Engine": "mysql",
                            "Status": "available",
                        }
                    ]
                }
            ]
            scanner.rds_client.get_paginator.return_value = mock_paginator

            result = scanner.find_old_snapshots()

        assert len(result) == 1
        assert result[0]["snapshot_id"] == "old-snapshot"
        assert result[0]["age_days"] >= 100

    def test_ignores_recent_snapshots(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1", snapshot_age_days=90)
            mock_paginator = MagicMock()
            recent_date = datetime.now(timezone.utc) - timedelta(days=30)
            mock_paginator.paginate.return_value = [
                {
                    "DBSnapshots": [
                        {
                            "DBSnapshotIdentifier": "recent-snapshot",
                            "DBInstanceIdentifier": "my-database",
                            "SnapshotCreateTime": recent_date,
                            "AllocatedStorage": 20,
                            "Engine": "mysql",
                            "Status": "available",
                        }
                    ]
                }
            ]
            scanner.rds_client.get_paginator.return_value = mock_paginator

            result = scanner.find_old_snapshots()

        assert len(result) == 0

    def test_resets_old_snapshots_on_each_call(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1")
            scanner.old_snapshots = [{"snapshot_id": "previous"}]
            mock_paginator = MagicMock()
            mock_paginator.paginate.return_value = [{"DBSnapshots": []}]
            scanner.rds_client.get_paginator.return_value = mock_paginator

            result = scanner.find_old_snapshots()

        assert result == []
        assert scanner.old_snapshots == []


class TestAnalyzeRDSInstances:
    """Tests for analyze_rds_instances method."""

    def test_returns_empty_list_when_no_instances(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1")
            mock_paginator = MagicMock()
            mock_paginator.paginate.return_value = [{"DBInstances": []}]
            scanner.rds_client.get_paginator.return_value = mock_paginator

            result = scanner.analyze_rds_instances()

        assert result == []

    def test_identifies_idle_instance(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1", cpu_threshold=5.0, connections_threshold=1)
            mock_paginator = MagicMock()
            mock_paginator.paginate.return_value = [
                {
                    "DBInstances": [
                        {
                            "DBInstanceIdentifier": "idle-db",
                            "DBInstanceClass": "db.t3.micro",
                            "Engine": "mysql",
                            "EngineVersion": "8.0",
                            "DBInstanceStatus": "available",
                            "AllocatedStorage": 20,
                            "MultiAZ": False,
                            "StorageType": "gp2",
                        }
                    ]
                }
            ]
            scanner.rds_client.get_paginator.return_value = mock_paginator
            scanner.cloudwatch_client.get_metric_statistics.return_value = {
                "Datapoints": [{"Average": 1.0}]
            }

            result = scanner.analyze_rds_instances()

        assert len(result) == 1
        assert result[0]["db_instance_id"] == "idle-db"
        assert result[0]["avg_cpu_percent"] == 1.0

    def test_does_not_flag_active_instance(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1", cpu_threshold=5.0, connections_threshold=1)
            mock_paginator = MagicMock()
            mock_paginator.paginate.return_value = [
                {
                    "DBInstances": [
                        {
                            "DBInstanceIdentifier": "active-db",
                            "DBInstanceClass": "db.t3.micro",
                            "Engine": "mysql",
                            "EngineVersion": "8.0",
                            "DBInstanceStatus": "available",
                            "AllocatedStorage": 20,
                            "MultiAZ": False,
                            "StorageType": "gp2",
                        }
                    ]
                }
            ]
            scanner.rds_client.get_paginator.return_value = mock_paginator
            # High CPU and connections
            scanner.cloudwatch_client.get_metric_statistics.return_value = {
                "Datapoints": [{"Average": 50.0}]
            }

            result = scanner.analyze_rds_instances()

        assert len(result) == 0

    def test_skips_non_available_instances(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1")
            mock_paginator = MagicMock()
            mock_paginator.paginate.return_value = [
                {
                    "DBInstances": [
                        {
                            "DBInstanceIdentifier": "stopped-db",
                            "DBInstanceClass": "db.t3.micro",
                            "Engine": "mysql",
                            "DBInstanceStatus": "stopped",
                            "AllocatedStorage": 20,
                        }
                    ]
                }
            ]
            scanner.rds_client.get_paginator.return_value = mock_paginator

            result = scanner.analyze_rds_instances()

        assert result == []

    def test_resets_idle_instances_on_each_scan(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1")
            scanner.idle_instances = [{"db_instance_id": "old-idle"}]
            mock_paginator = MagicMock()
            mock_paginator.paginate.return_value = [{"DBInstances": []}]
            scanner.rds_client.get_paginator.return_value = mock_paginator

            result = scanner.analyze_rds_instances()

        assert result == []
        assert scanner.idle_instances == []

    def test_idle_instance_contains_required_fields(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1")
            mock_paginator = MagicMock()
            mock_paginator.paginate.return_value = [
                {
                    "DBInstances": [
                        {
                            "DBInstanceIdentifier": "test-db",
                            "DBInstanceClass": "db.t3.micro",
                            "Engine": "postgres",
                            "EngineVersion": "15.4",
                            "DBInstanceStatus": "available",
                            "AllocatedStorage": 50,
                            "MultiAZ": True,
                            "StorageType": "gp3",
                        }
                    ]
                }
            ]
            scanner.rds_client.get_paginator.return_value = mock_paginator
            scanner.cloudwatch_client.get_metric_statistics.return_value = {
                "Datapoints": [{"Average": 0.5}]
            }

            result = scanner.analyze_rds_instances()

        assert len(result) == 1
        idle_instance = result[0]
        required_fields = [
            "db_instance_id",
            "db_instance_class",
            "engine",
            "engine_version",
            "allocated_storage_gb",
            "storage_type",
            "multi_az",
            "avg_cpu_percent",
            "avg_connections",
            "estimated_monthly_cost",
            "analysis_period_days",
            "cpu_threshold",
            "connections_threshold",
            "recommendation",
        ]
        for field in required_fields:
            assert field in idle_instance


class TestGetScanSummary:
    """Tests for get_scan_summary method."""

    def test_returns_correct_summary_structure(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1")

            result = scanner.get_scan_summary()

        assert "scanner" in result
        assert "region" in result
        assert "analysis_period_days" in result
        assert "cpu_threshold_percent" in result
        assert "connections_threshold" in result
        assert "snapshot_age_threshold_days" in result
        assert "idle_instances_count" in result
        assert "idle_instances_monthly_cost" in result
        assert "idle_instances" in result
        assert "old_snapshots_count" in result
        assert "old_snapshots_monthly_cost" in result
        assert "old_snapshots" in result
        assert "total_potential_monthly_savings" in result
        assert "scan_timestamp" in result

    def test_summary_reflects_scanner_config(self):
        with patch("boto3.client"):
            scanner = RDSScanner(
                region="eu-central-1",
                days=7,
                cpu_threshold=10.0,
                connections_threshold=5,
                snapshot_age_days=60,
            )

            result = scanner.get_scan_summary()

        assert result["scanner"] == "RDSScanner"
        assert result["region"] == "eu-central-1"
        assert result["analysis_period_days"] == 7
        assert result["cpu_threshold_percent"] == 10.0
        assert result["connections_threshold"] == 5
        assert result["snapshot_age_threshold_days"] == 60

    def test_summary_includes_idle_instances_and_snapshots(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1")
            scanner.idle_instances = [
                {"db_instance_id": "idle-1"},
                {"db_instance_id": "idle-2"},
            ]
            scanner.old_snapshots = [{"snapshot_id": "old-snap-1"}]

            result = scanner.get_scan_summary()

        assert result["idle_instances_count"] == 2
        assert result["old_snapshots_count"] == 1
        assert len(result["idle_instances"]) == 2
        assert len(result["old_snapshots"]) == 1

    def test_summary_timestamp_is_valid_iso_format(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1")

            result = scanner.get_scan_summary()

        # Should not raise an exception
        datetime.fromisoformat(result["scan_timestamp"].replace("Z", "+00:00"))


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_cpu_threshold_boundary(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1", cpu_threshold=5.0, connections_threshold=1)

            # At threshold - should be idle
            assert scanner.is_instance_idle(5.0, 1.0) is True
            # Just above threshold - not idle
            assert scanner.is_instance_idle(5.01, 0.5) is False

    def test_connections_threshold_boundary(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1", cpu_threshold=5.0, connections_threshold=1)

            # At threshold - should be idle
            assert scanner.is_instance_idle(2.0, 1.0) is True
            # Just above threshold - not idle
            assert scanner.is_instance_idle(2.0, 1.01) is False

    def test_zero_thresholds(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1", cpu_threshold=0, connections_threshold=0)

            assert scanner.is_instance_idle(0, 0) is True
            assert scanner.is_instance_idle(0.1, 0) is False

    def test_snapshot_age_exactly_at_threshold(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1", snapshot_age_days=90)
            mock_paginator = MagicMock()
            # 89 days old (just under threshold)
            just_under_90_days = datetime.now(timezone.utc) - timedelta(days=89)
            mock_paginator.paginate.return_value = [
                {
                    "DBSnapshots": [
                        {
                            "DBSnapshotIdentifier": "edge-snapshot",
                            "DBInstanceIdentifier": "db",
                            "SnapshotCreateTime": just_under_90_days,
                            "AllocatedStorage": 20,
                            "Engine": "mysql",
                            "Status": "available",
                        }
                    ]
                }
            ]
            scanner.rds_client.get_paginator.return_value = mock_paginator

            result = scanner.find_old_snapshots()

        # 89 days old is NOT older than 90, so should not be flagged
        assert len(result) == 0

    def test_snapshot_just_over_threshold(self):
        with patch("boto3.client"):
            scanner = RDSScanner(region="us-east-1", snapshot_age_days=90)
            mock_paginator = MagicMock()
            # 91 days old
            over_threshold = datetime.now(timezone.utc) - timedelta(days=91)
            mock_paginator.paginate.return_value = [
                {
                    "DBSnapshots": [
                        {
                            "DBSnapshotIdentifier": "old-snapshot",
                            "DBInstanceIdentifier": "db",
                            "SnapshotCreateTime": over_threshold,
                            "AllocatedStorage": 20,
                            "Engine": "mysql",
                            "Status": "available",
                        }
                    ]
                }
            ]
            scanner.rds_client.get_paginator.return_value = mock_paginator

            result = scanner.find_old_snapshots()

        assert len(result) == 1
