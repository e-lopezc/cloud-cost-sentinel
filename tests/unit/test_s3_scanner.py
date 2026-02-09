"""
Unit tests for S3 Scanner Module.

Tests cover:
- Initialization
- Getting S3 buckets
- Bucket region detection
- CloudWatch request metrics retrieval
- CloudWatch storage metrics retrieval
- Unused bucket detection
- Buckets without metrics handling
- Scan summary
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError, BotoCoreError

from src.scanners.s3_scanner import S3Scanner


class TestS3ScannerInit:
    """Tests for S3Scanner initialization."""

    def test_init_with_defaults(self):
        with patch("boto3.client"):
            scanner = S3Scanner(region="us-east-1")

        assert scanner.region == "us-east-1"
        assert scanner.days == 30
        assert scanner.request_threshold == 10
        assert scanner.unused_buckets == []
        assert scanner.buckets_without_metrics == []

    def test_init_with_custom_values(self):
        with patch("boto3.client"):
            scanner = S3Scanner(
                region="eu-west-1",
                days=60,
                request_threshold=5,
            )

        assert scanner.region == "eu-west-1"
        assert scanner.days == 60
        assert scanner.request_threshold == 5

    def test_init_creates_boto3_clients(self):
        with patch("boto3.client") as mock_client:
            S3Scanner(region="us-west-2")

        calls = mock_client.call_args_list
        assert any(call[0] == ("s3",) for call in calls)
        assert any(call[0] == ("cloudwatch",) for call in calls)


class TestGetAllBuckets:
    """Tests for get_all_buckets method."""

    def test_returns_empty_list_when_no_buckets(self):
        with patch("boto3.client"):
            scanner = S3Scanner(region="us-east-1")
            scanner.s3_client.list_buckets.return_value = {"Buckets": []}
            scanner.s3_client.get_bucket_location.return_value = {"LocationConstraint": None}

            result = scanner.get_all_buckets()

        assert result == []

    def test_returns_buckets_with_metadata(self):
        with patch("boto3.client"):
            scanner = S3Scanner(region="us-east-1")
            creation_date = datetime(2024, 1, 15, tzinfo=timezone.utc)
            scanner.s3_client.list_buckets.return_value = {
                "Buckets": [
                    {"Name": "my-bucket", "CreationDate": creation_date}
                ]
            }
            scanner.s3_client.get_bucket_location.return_value = {"LocationConstraint": "us-west-2"}

            result = scanner.get_all_buckets()

        assert len(result) == 1
        assert result[0]["bucket_name"] == "my-bucket"
        assert result[0]["creation_date"] == creation_date
        assert result[0]["region"] == "us-west-2"

    def test_handles_api_error_gracefully(self):
        with patch("boto3.client"):
            scanner = S3Scanner(region="us-east-1")
            scanner.s3_client.list_buckets.side_effect = ClientError(
                {"Error": {"Code": "500", "Message": "Internal Error"}},
                "ListBuckets",
            )

            result = scanner.get_all_buckets()

        assert result == []


class TestGetBucketRegion:
    """Tests for _get_bucket_region method."""

    def test_returns_region_from_location_constraint(self):
        with patch("boto3.client"):
            scanner = S3Scanner(region="us-east-1")
            scanner.s3_client.get_bucket_location.return_value = {"LocationConstraint": "eu-central-1"}

            result = scanner._get_bucket_region("my-bucket")

        assert result == "eu-central-1"

    def test_returns_us_east_1_for_none_location(self):
        with patch("boto3.client"):
            scanner = S3Scanner(region="us-east-1")
            scanner.s3_client.get_bucket_location.return_value = {"LocationConstraint": None}

            result = scanner._get_bucket_region("my-bucket")

        assert result == "us-east-1"

    def test_returns_unknown_on_error(self):
        with patch("boto3.client"):
            scanner = S3Scanner(region="us-east-1")
            scanner.s3_client.get_bucket_location.side_effect = ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
                "GetBucketLocation",
            )

            result = scanner._get_bucket_region("my-bucket")

        assert result == "unknown"


class TestGetBucketRequestMetrics:
    """Tests for get_bucket_request_metrics method."""

    def test_returns_metrics_when_available(self):
        with patch("boto3.client") as mock_client:
            scanner = S3Scanner(region="us-east-1")
            mock_regional_cw = MagicMock()
            mock_client.return_value = mock_regional_cw
            mock_regional_cw.get_metric_statistics.return_value = {
                "Datapoints": [{"Sum": 100}, {"Sum": 200}]
            }

            result = scanner.get_bucket_request_metrics("my-bucket", "us-east-1")

        assert result["has_metrics"] is True
        assert result["total_requests"] == 300

    def test_returns_no_metrics_when_datapoints_empty(self):
        with patch("boto3.client") as mock_client:
            scanner = S3Scanner(region="us-east-1")
            mock_regional_cw = MagicMock()
            mock_client.return_value = mock_regional_cw
            mock_regional_cw.get_metric_statistics.return_value = {"Datapoints": []}

            result = scanner.get_bucket_request_metrics("my-bucket", "us-east-1")

        assert result["has_metrics"] is False
        assert result["total_requests"] == 0

    def test_handles_api_error_gracefully(self):
        with patch("boto3.client") as mock_client:
            scanner = S3Scanner(region="us-east-1")
            mock_regional_cw = MagicMock()
            mock_client.return_value = mock_regional_cw
            mock_regional_cw.get_metric_statistics.side_effect = ClientError(
                {"Error": {"Code": "500", "Message": "Error"}},
                "GetMetricStatistics",
            )

            result = scanner.get_bucket_request_metrics("my-bucket", "us-east-1")

        assert result["has_metrics"] is False
        assert result["total_requests"] == 0


class TestGetBucketStorageMetrics:
    """Tests for get_bucket_storage_metrics method."""

    def test_returns_storage_metrics(self):
        with patch("boto3.client") as mock_client:
            scanner = S3Scanner(region="us-east-1")
            mock_regional_cw = MagicMock()
            mock_client.return_value = mock_regional_cw
            mock_regional_cw.get_metric_statistics.side_effect = [
                {"Datapoints": [{"Average": 1024000}]},  # size
                {"Datapoints": [{"Average": 50}]},  # count
            ]

            result = scanner.get_bucket_storage_metrics("my-bucket", "us-east-1")

        assert result["size_bytes"] == 1024000
        assert result["object_count"] == 50

    def test_returns_zeros_when_no_datapoints(self):
        with patch("boto3.client") as mock_client:
            scanner = S3Scanner(region="us-east-1")
            mock_regional_cw = MagicMock()
            mock_client.return_value = mock_regional_cw
            mock_regional_cw.get_metric_statistics.return_value = {"Datapoints": []}

            result = scanner.get_bucket_storage_metrics("my-bucket", "us-east-1")

        assert result["size_bytes"] == 0
        assert result["object_count"] == 0

    def test_handles_api_error_gracefully(self):
        with patch("boto3.client") as mock_client:
            scanner = S3Scanner(region="us-east-1")
            mock_regional_cw = MagicMock()
            mock_client.return_value = mock_regional_cw
            mock_regional_cw.get_metric_statistics.side_effect = BotoCoreError()

            result = scanner.get_bucket_storage_metrics("my-bucket", "us-east-1")

        assert result["size_bytes"] == 0
        assert result["object_count"] == 0


class TestIsBucketUnused:
    """Tests for is_bucket_unused method."""

    def test_unused_when_below_threshold(self):
        with patch("boto3.client"):
            scanner = S3Scanner(region="us-east-1", request_threshold=10)

            result = scanner.is_bucket_unused(5)

        assert result is True

    def test_unused_when_at_threshold(self):
        with patch("boto3.client"):
            scanner = S3Scanner(region="us-east-1", request_threshold=10)

            result = scanner.is_bucket_unused(10)

        assert result is True

    def test_not_unused_when_above_threshold(self):
        with patch("boto3.client"):
            scanner = S3Scanner(region="us-east-1", request_threshold=10)

            result = scanner.is_bucket_unused(11)

        assert result is False

    def test_unused_when_zero_requests(self):
        with patch("boto3.client"):
            scanner = S3Scanner(region="us-east-1", request_threshold=10)

            result = scanner.is_bucket_unused(0)

        assert result is True


class TestAnalyzeS3Buckets:
    """Tests for analyze_s3_buckets method."""

    def test_returns_empty_list_when_no_buckets(self):
        with patch("boto3.client"):
            scanner = S3Scanner(region="us-east-1")
            scanner.s3_client.list_buckets.return_value = {"Buckets": []}

            result = scanner.analyze_s3_buckets()

        assert result == []

    def test_identifies_unused_bucket(self):
        with patch("boto3.client") as mock_client:
            scanner = S3Scanner(region="us-east-1", request_threshold=10)
            creation_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
            scanner.s3_client.list_buckets.return_value = {
                "Buckets": [{"Name": "unused-bucket", "CreationDate": creation_date}]
            }
            scanner.s3_client.get_bucket_location.return_value = {"LocationConstraint": "us-east-1"}

            # Mock CloudWatch responses
            mock_regional_cw = MagicMock()
            mock_client.return_value = mock_regional_cw
            mock_regional_cw.get_metric_statistics.side_effect = [
                {"Datapoints": [{"Sum": 5}]},  # request metrics (has_metrics=True, low count)
                {"Datapoints": [{"Average": 1024}]},  # size
                {"Datapoints": [{"Average": 10}]},  # count
            ]

            result = scanner.analyze_s3_buckets()

        assert len(result) == 1
        assert result[0]["bucket_name"] == "unused-bucket"
        assert result[0]["status"] == "unused"

    def test_identifies_bucket_without_metrics(self):
        with patch("boto3.client") as mock_client:
            scanner = S3Scanner(region="us-east-1")
            creation_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
            scanner.s3_client.list_buckets.return_value = {
                "Buckets": [{"Name": "no-metrics-bucket", "CreationDate": creation_date}]
            }
            scanner.s3_client.get_bucket_location.return_value = {"LocationConstraint": "us-east-1"}

            mock_regional_cw = MagicMock()
            mock_client.return_value = mock_regional_cw
            mock_regional_cw.get_metric_statistics.side_effect = [
                {"Datapoints": []},  # no request metrics
                {"Datapoints": [{"Average": 0}]},  # size
                {"Datapoints": [{"Average": 0}]},  # count
            ]

            scanner.analyze_s3_buckets()

        assert len(scanner.buckets_without_metrics) == 1
        assert scanner.buckets_without_metrics[0]["bucket_name"] == "no-metrics-bucket"
        assert scanner.buckets_without_metrics[0]["status"] == "metrics_not_enabled"

    def test_does_not_flag_active_bucket(self):
        with patch("boto3.client") as mock_client:
            scanner = S3Scanner(region="us-east-1", request_threshold=10)
            creation_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
            scanner.s3_client.list_buckets.return_value = {
                "Buckets": [{"Name": "active-bucket", "CreationDate": creation_date}]
            }
            scanner.s3_client.get_bucket_location.return_value = {"LocationConstraint": "us-east-1"}

            mock_regional_cw = MagicMock()
            mock_client.return_value = mock_regional_cw
            mock_regional_cw.get_metric_statistics.side_effect = [
                {"Datapoints": [{"Sum": 1000}]},  # high request count
                {"Datapoints": [{"Average": 1024}]},  # size
                {"Datapoints": [{"Average": 10}]},  # count
            ]

            result = scanner.analyze_s3_buckets()

        assert len(result) == 0
        assert len(scanner.buckets_without_metrics) == 0

    def test_skips_bucket_with_unknown_region(self):
        with patch("boto3.client"):
            scanner = S3Scanner(region="us-east-1")
            creation_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
            scanner.s3_client.list_buckets.return_value = {
                "Buckets": [{"Name": "unknown-region-bucket", "CreationDate": creation_date}]
            }
            scanner.s3_client.get_bucket_location.side_effect = ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
                "GetBucketLocation",
            )

            result = scanner.analyze_s3_buckets()

        assert len(result) == 0
        assert len(scanner.buckets_without_metrics) == 0

    def test_resets_lists_on_each_scan(self):
        with patch("boto3.client"):
            scanner = S3Scanner(region="us-east-1")
            scanner.unused_buckets = [{"bucket_name": "old-unused"}]
            scanner.buckets_without_metrics = [{"bucket_name": "old-no-metrics"}]
            scanner.s3_client.list_buckets.return_value = {"Buckets": []}

            scanner.analyze_s3_buckets()

        assert scanner.unused_buckets == []
        assert scanner.buckets_without_metrics == []

    def test_unused_bucket_contains_required_fields(self):
        with patch("boto3.client") as mock_client:
            scanner = S3Scanner(region="us-east-1", request_threshold=10)
            creation_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
            scanner.s3_client.list_buckets.return_value = {
                "Buckets": [{"Name": "test-bucket", "CreationDate": creation_date}]
            }
            scanner.s3_client.get_bucket_location.return_value = {"LocationConstraint": "eu-west-1"}

            mock_regional_cw = MagicMock()
            mock_client.return_value = mock_regional_cw
            mock_regional_cw.get_metric_statistics.side_effect = [
                {"Datapoints": [{"Sum": 0}]},  # unused
                {"Datapoints": [{"Average": 2048}]},  # size
                {"Datapoints": [{"Average": 5}]},  # count
            ]

            result = scanner.analyze_s3_buckets()

        assert len(result) == 1
        bucket = result[0]
        required_fields = [
            "bucket_name",
            "region",
            "creation_date",
            "size_bytes",
            "size_formatted",
            "object_count",
            "estimated_monthly_cost",
            "total_requests",
            "request_threshold",
            "analysis_period_days",
            "status",
            "recommendation",
        ]
        for field in required_fields:
            assert field in bucket


class TestGetScanSummary:
    """Tests for get_scan_summary method."""

    def test_returns_correct_summary_structure(self):
        with patch("boto3.client"):
            scanner = S3Scanner(region="us-east-1")

            result = scanner.get_scan_summary()

        assert "scanner" in result
        assert "region" in result
        assert "analysis_period_days" in result
        assert "request_threshold" in result
        assert "unused_buckets_count" in result
        assert "unused_buckets_monthly_cost" in result
        assert "unused_buckets" in result
        assert "total_potential_monthly_savings" in result
        assert "buckets_without_metrics_count" in result
        assert "buckets_without_metrics" in result
        assert "scan_timestamp" in result

    def test_summary_reflects_scanner_config(self):
        with patch("boto3.client"):
            scanner = S3Scanner(
                region="ap-southeast-1",
                days=45,
                request_threshold=20,
            )

            result = scanner.get_scan_summary()

        assert result["scanner"] == "S3Scanner"
        assert result["region"] == "ap-southeast-1"
        assert result["analysis_period_days"] == 45
        assert result["request_threshold"] == 20

    def test_summary_includes_bucket_counts(self):
        with patch("boto3.client"):
            scanner = S3Scanner(region="us-east-1")
            scanner.unused_buckets = [
                {"bucket_name": "unused-1"},
                {"bucket_name": "unused-2"},
            ]
            scanner.buckets_without_metrics = [
                {"bucket_name": "no-metrics-1"},
            ]

            result = scanner.get_scan_summary()

        assert result["unused_buckets_count"] == 2
        assert result["buckets_without_metrics_count"] == 1
        assert len(result["unused_buckets"]) == 2
        assert len(result["buckets_without_metrics"]) == 1

    def test_summary_timestamp_is_valid_iso_format(self):
        with patch("boto3.client"):
            scanner = S3Scanner(region="us-east-1")

            result = scanner.get_scan_summary()

        # Should not raise an exception
        datetime.fromisoformat(result["scan_timestamp"].replace("Z", "+00:00"))


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_request_threshold_zero(self):
        with patch("boto3.client"):
            scanner = S3Scanner(region="us-east-1", request_threshold=0)

            assert scanner.is_bucket_unused(0) is True
            assert scanner.is_bucket_unused(1) is False

    def test_handles_multiple_buckets_in_different_regions(self):
        with patch("boto3.client") as mock_client:
            scanner = S3Scanner(region="us-east-1", request_threshold=10)
            creation_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
            scanner.s3_client.list_buckets.return_value = {
                "Buckets": [
                    {"Name": "bucket-us", "CreationDate": creation_date},
                    {"Name": "bucket-eu", "CreationDate": creation_date},
                ]
            }
            scanner.s3_client.get_bucket_location.side_effect = [
                {"LocationConstraint": None},  # us-east-1
                {"LocationConstraint": "eu-west-1"},
            ]

            mock_regional_cw = MagicMock()
            mock_client.return_value = mock_regional_cw
            # Both buckets unused
            mock_regional_cw.get_metric_statistics.side_effect = [
                {"Datapoints": [{"Sum": 0}]},  # bucket-us requests
                {"Datapoints": [{"Average": 100}]},  # bucket-us size
                {"Datapoints": [{"Average": 1}]},  # bucket-us count
                {"Datapoints": [{"Sum": 5}]},  # bucket-eu requests
                {"Datapoints": [{"Average": 200}]},  # bucket-eu size
                {"Datapoints": [{"Average": 2}]},  # bucket-eu count
            ]

            result = scanner.analyze_s3_buckets()

        assert len(result) == 2

    def test_handles_bucket_with_no_creation_date(self):
        with patch("boto3.client") as mock_client:
            scanner = S3Scanner(region="us-east-1", request_threshold=10)
            scanner.s3_client.list_buckets.return_value = {
                "Buckets": [{"Name": "no-date-bucket", "CreationDate": None}]
            }
            scanner.s3_client.get_bucket_location.return_value = {"LocationConstraint": "us-east-1"}

            mock_regional_cw = MagicMock()
            mock_client.return_value = mock_regional_cw
            mock_regional_cw.get_metric_statistics.side_effect = [
                {"Datapoints": [{"Sum": 0}]},
                {"Datapoints": []},
                {"Datapoints": []},
            ]

            result = scanner.analyze_s3_buckets()

        assert len(result) == 1
        assert result[0]["creation_date"] == "N/A"
