"""
Unit tests for S3Reporter.

Uses moto to mock S3 API calls. Verifies correct key paths, content types,
graceful failure when the bucket env var is missing, and graceful failure
on AWS errors.
"""

import json
import os
import pytest
import boto3
from moto import mock_aws
from unittest.mock import patch
from botocore.exceptions import ClientError

from reports.s3_reporter import S3Reporter, _ENV_VAR


# ------------------------------------------------------------------ #
# Shared fixtures
# ------------------------------------------------------------------ #

BUCKET_NAME = "sentinel-test-reports"
REGION = "us-east-1"
SCAN_DATE = "2025-06-15"

@pytest.fixture
def sample_findings():
    return {
        "account_id": "123456789012",
        "region": REGION,
        "scan_timestamp": f"{SCAN_DATE}T02:00:00+00:00",
        "ec2": {"idle_instances_count": 1, "idle_instances_monthly_cost": 60.00, "idle_instances": []},
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


@pytest.fixture
def sample_html():
    return "<html><body><p>Test report</p></body></html>"


@pytest.fixture(autouse=True)
def clear_bucket_env():
    """Ensure SENTINEL_REPORT_BUCKET is unset between tests."""
    os.environ.pop(_ENV_VAR, None)
    yield
    os.environ.pop(_ENV_VAR, None)


# ------------------------------------------------------------------ #
# Initialisation
# ------------------------------------------------------------------ #

class TestS3ReporterInit:
    """Tests for S3Reporter initialisation."""

    def test_reads_bucket_from_env(self):
        os.environ[_ENV_VAR] = BUCKET_NAME
        reporter = S3Reporter(region=REGION)
        assert reporter.bucket == BUCKET_NAME

    def test_bucket_empty_when_env_not_set(self):
        reporter = S3Reporter(region=REGION)
        assert reporter.bucket == ""

    def test_stores_region(self):
        reporter = S3Reporter(region="eu-west-1")
        assert reporter.region == "eu-west-1"

    def test_strips_whitespace_from_bucket_name(self):
        os.environ[_ENV_VAR] = f"  {BUCKET_NAME}  "
        reporter = S3Reporter(region=REGION)
        assert reporter.bucket == BUCKET_NAME


# ------------------------------------------------------------------ #
# Happy path — successful uploads
# ------------------------------------------------------------------ #

class TestS3ReporterUpload:
    """Tests for successful S3 upload behaviour."""

    @mock_aws
    def test_returns_true_on_success(self, aws_credentials, sample_findings, sample_html):
        os.environ[_ENV_VAR] = BUCKET_NAME
        s3 = boto3.client("s3", region_name=REGION)
        s3.create_bucket(Bucket=BUCKET_NAME)

        reporter = S3Reporter(region=REGION)
        result = reporter.upload_reports(sample_findings, sample_html)

        assert result is True

    @mock_aws
    def test_uploads_json_findings(self, aws_credentials, sample_findings, sample_html):
        os.environ[_ENV_VAR] = BUCKET_NAME
        s3 = boto3.client("s3", region_name=REGION)
        s3.create_bucket(Bucket=BUCKET_NAME)

        S3Reporter(region=REGION).upload_reports(sample_findings, sample_html)

        obj = s3.get_object(Bucket=BUCKET_NAME, Key=f"reports/{SCAN_DATE}/findings.json")
        body = json.loads(obj["Body"].read().decode("utf-8"))
        assert body["account_id"] == "123456789012"

    @mock_aws
    def test_uploads_html_report(self, aws_credentials, sample_findings, sample_html):
        os.environ[_ENV_VAR] = BUCKET_NAME
        s3 = boto3.client("s3", region_name=REGION)
        s3.create_bucket(Bucket=BUCKET_NAME)

        S3Reporter(region=REGION).upload_reports(sample_findings, sample_html)

        obj = s3.get_object(Bucket=BUCKET_NAME, Key=f"reports/{SCAN_DATE}/report.html")
        body = obj["Body"].read().decode("utf-8")
        assert "<html>" in body

    @mock_aws
    def test_json_key_uses_scan_date(self, aws_credentials, sample_findings, sample_html):
        os.environ[_ENV_VAR] = BUCKET_NAME
        s3 = boto3.client("s3", region_name=REGION)
        s3.create_bucket(Bucket=BUCKET_NAME)

        S3Reporter(region=REGION).upload_reports(sample_findings, sample_html)

        keys = [
            obj["Key"]
            for obj in s3.list_objects_v2(Bucket=BUCKET_NAME)["Contents"]
        ]
        assert f"reports/{SCAN_DATE}/findings.json" in keys
        assert f"reports/{SCAN_DATE}/report.html" in keys

    @mock_aws
    def test_json_content_type(self, aws_credentials, sample_findings, sample_html):
        os.environ[_ENV_VAR] = BUCKET_NAME
        s3 = boto3.client("s3", region_name=REGION)
        s3.create_bucket(Bucket=BUCKET_NAME)

        S3Reporter(region=REGION).upload_reports(sample_findings, sample_html)

        obj = s3.get_object(Bucket=BUCKET_NAME, Key=f"reports/{SCAN_DATE}/findings.json")
        assert obj["ContentType"] == "application/json"

    @mock_aws
    def test_html_content_type(self, aws_credentials, sample_findings, sample_html):
        os.environ[_ENV_VAR] = BUCKET_NAME
        s3 = boto3.client("s3", region_name=REGION)
        s3.create_bucket(Bucket=BUCKET_NAME)

        S3Reporter(region=REGION).upload_reports(sample_findings, sample_html)

        obj = s3.get_object(Bucket=BUCKET_NAME, Key=f"reports/{SCAN_DATE}/report.html")
        assert "text/html" in obj["ContentType"]

    @mock_aws
    def test_json_findings_are_complete(self, aws_credentials, sample_findings, sample_html):
        """All top-level keys from all_findings should be present in the uploaded JSON."""
        os.environ[_ENV_VAR] = BUCKET_NAME
        s3 = boto3.client("s3", region_name=REGION)
        s3.create_bucket(Bucket=BUCKET_NAME)

        S3Reporter(region=REGION).upload_reports(sample_findings, sample_html)

        obj = s3.get_object(Bucket=BUCKET_NAME, Key=f"reports/{SCAN_DATE}/findings.json")
        body = json.loads(obj["Body"].read().decode("utf-8"))
        for key in ("account_id", "region", "scan_timestamp", "ec2", "ebs", "rds", "s3"):
            assert key in body


# ------------------------------------------------------------------ #
# Graceful failure — no bucket configured
# ------------------------------------------------------------------ #

class TestS3ReporterNoBucket:
    """Tests for graceful handling when SENTINEL_REPORT_BUCKET is not set."""

    def test_returns_false_when_env_not_set(self, sample_findings, sample_html):
        reporter = S3Reporter(region=REGION)
        result = reporter.upload_reports(sample_findings, sample_html)
        assert result is False

    def test_does_not_raise_when_env_not_set(self, sample_findings, sample_html):
        reporter = S3Reporter(region=REGION)
        try:
            reporter.upload_reports(sample_findings, sample_html)
        except Exception as e:
            pytest.fail(f"upload_reports raised unexpectedly: {e}")


# ------------------------------------------------------------------ #
# Graceful failure — AWS errors
# ------------------------------------------------------------------ #

class TestS3ReporterAWSErrors:
    """Tests that AWS errors are caught and return False rather than raising."""

    @mock_aws
    def test_returns_false_on_client_error(self, aws_credentials, sample_findings, sample_html):
        """Upload to a non-existent bucket should return False, not raise."""
        os.environ[_ENV_VAR] = "bucket-that-does-not-exist"
        reporter = S3Reporter(region=REGION)
        result = reporter.upload_reports(sample_findings, sample_html)
        assert result is False

    def test_does_not_raise_on_client_error(self, sample_findings, sample_html):
        os.environ[_ENV_VAR] = BUCKET_NAME
        reporter = S3Reporter(region=REGION)

        with patch.object(reporter._client, "put_object", side_effect=ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "The bucket does not exist"}},
            "PutObject",
        )):
            try:
                result = reporter.upload_reports(sample_findings, sample_html)
            except Exception as e:
                pytest.fail(f"upload_reports raised unexpectedly: {e}")
            assert result is False

    def test_does_not_raise_on_unexpected_error(self, sample_findings, sample_html):
        os.environ[_ENV_VAR] = BUCKET_NAME
        reporter = S3Reporter(region=REGION)

        with patch.object(reporter._client, "put_object", side_effect=RuntimeError("unexpected")):
            try:
                result = reporter.upload_reports(sample_findings, sample_html)
            except Exception as e:
                pytest.fail(f"upload_reports raised unexpectedly: {e}")
            assert result is False

    def test_returns_false_when_json_ok_but_html_fails(self, sample_findings, sample_html):
        """Partial upload: JSON succeeds, HTML fails → returns False without raising."""
        os.environ[_ENV_VAR] = BUCKET_NAME
        reporter = S3Reporter(region=REGION)

        call_count = 0

        def _fail_on_second(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ClientError(
                    {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
                    "PutObject",
                )

        with patch.object(reporter._client, "put_object", side_effect=_fail_on_second):
            result = reporter.upload_reports(sample_findings, sample_html)

        assert result is False
        assert call_count == 2


# ------------------------------------------------------------------ #
# Date prefix helper
# ------------------------------------------------------------------ #

class TestS3ReporterDatePrefix:
    """Tests for the internal _date_prefix helper."""

    def test_extracts_date_from_iso_timestamp(self, sample_findings):
        reporter = S3Reporter(region=REGION)
        assert reporter._date_prefix(sample_findings) == SCAN_DATE

    def test_falls_back_to_today_on_missing_timestamp(self):
        from datetime import datetime, timezone
        reporter = S3Reporter(region=REGION)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert reporter._date_prefix({}) == today

    def test_falls_back_to_today_on_invalid_timestamp(self):
        from datetime import datetime, timezone
        reporter = S3Reporter(region=REGION)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert reporter._date_prefix({"scan_timestamp": "bad-value"}) == today

    def test_handles_z_suffix_timestamp(self):
        reporter = S3Reporter(region=REGION)
        findings = {"scan_timestamp": "2025-09-01T12:00:00Z"}
        assert reporter._date_prefix(findings) == "2025-09-01"
