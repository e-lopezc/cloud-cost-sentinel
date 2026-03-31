"""
Unit tests for SNSPublisher.

Uses moto to mock SNS API calls. Verifies correct subject formatting,
graceful failure when the topic ARN env var is missing, and graceful
failure on AWS errors.
"""

import os
import pytest
import boto3
from moto import mock_aws
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError, BotoCoreError

from notifications.sns_publisher import SNSPublisher, _ENV_VAR


# ------------------------------------------------------------------ #
# Shared fixtures
# ------------------------------------------------------------------ #

REGION = "us-east-1"
ACCOUNT_ID = "123456789012"
TOPIC_NAME = "sentinel-dev-cost-alerts"


@pytest.fixture
def sample_findings():
    return {
        "account_id": ACCOUNT_ID,
        "region": REGION,
        "scan_timestamp": "2025-06-15T02:00:00+00:00",
        "ec2": {"idle_instances_count": 1, "idle_instances_monthly_cost": 60.00},
        "ebs": {"unattached_volumes_monthly_cost": 10.00, "low_io_volumes_monthly_cost": 5.00},
        "rds": {"idle_instances_monthly_cost": 80.00, "old_snapshots_monthly_cost": 2.00},
        "s3": {"unused_buckets_monthly_cost": 3.00},
    }


@pytest.fixture
def sample_html():
    return "<html><body><p>Cost Report</p></body></html>"


@pytest.fixture(autouse=True)
def clear_env():
    """Ensure SENTINEL_SNS_TOPIC_ARN is unset between tests."""
    os.environ.pop(_ENV_VAR, None)
    yield
    os.environ.pop(_ENV_VAR, None)


# ------------------------------------------------------------------ #
# Helper
# ------------------------------------------------------------------ #

def _create_topic(region=REGION):
    """Create a mock SNS topic and return its ARN."""
    client = boto3.client("sns", region_name=region)
    response = client.create_topic(Name=TOPIC_NAME)
    return response["TopicArn"]


# ------------------------------------------------------------------ #
# No-op when env var is missing
# ------------------------------------------------------------------ #

class TestMissingEnvVar:
    def test_returns_false_when_env_var_not_set(self, sample_findings, sample_html):
        publisher = SNSPublisher(region=REGION)
        result = publisher.publish_report(sample_findings, sample_html)
        assert result is False

    def test_returns_false_when_env_var_is_blank(self, sample_findings, sample_html):
        os.environ[_ENV_VAR] = "   "
        publisher = SNSPublisher(region=REGION)
        result = publisher.publish_report(sample_findings, sample_html)
        assert result is False

    def test_logs_warning_when_env_var_not_set(self, sample_findings, sample_html, caplog):
        import logging
        with caplog.at_level(logging.WARNING, logger="notifications.sns_publisher"):
            SNSPublisher(region=REGION).publish_report(sample_findings, sample_html)
        assert _ENV_VAR in caplog.text


# ------------------------------------------------------------------ #
# Successful publish
# ------------------------------------------------------------------ #

@mock_aws
class TestSuccessfulPublish:
    def test_returns_true_on_success(self, sample_findings, sample_html):
        topic_arn = _create_topic()
        os.environ[_ENV_VAR] = topic_arn
        result = SNSPublisher(region=REGION).publish_report(sample_findings, sample_html)
        assert result is True

    def test_publishes_to_correct_topic(self, sample_findings, sample_html):
        topic_arn = _create_topic()
        os.environ[_ENV_VAR] = topic_arn

        publisher = SNSPublisher(region=REGION)
        publisher.publish_report(sample_findings, sample_html)

        # Verify the message landed on the topic
        sqs = boto3.client("sqs", region_name=REGION)
        sns = boto3.client("sns", region_name=REGION)

        queue = sqs.create_queue(QueueName="test-queue")
        queue_url = queue["QueueUrl"]
        queue_arn = sqs.get_queue_attributes(
            QueueUrl=queue_url, AttributeNames=["QueueArn"]
        )["Attributes"]["QueueArn"]

        sns.subscribe(TopicArn=topic_arn, Protocol="sqs", Endpoint=queue_arn)
        publisher.publish_report(sample_findings, sample_html)

        messages = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1)
        assert "Messages" in messages

    def test_html_report_is_message_body(self, sample_findings, sample_html):
        """The full HTML string must be the SNS Message payload."""
        topic_arn = _create_topic()
        os.environ[_ENV_VAR] = topic_arn

        publisher = SNSPublisher(region=REGION)
        with patch.object(publisher._client, "publish", wraps=publisher._client.publish) as mock_pub:
            publisher.publish_report(sample_findings, sample_html)
            call_kwargs = mock_pub.call_args[1]
            assert call_kwargs["Message"] == sample_html
            assert call_kwargs["TopicArn"] == topic_arn


# ------------------------------------------------------------------ #
# Subject line
# ------------------------------------------------------------------ #

class TestSubjectLine:
    def test_subject_contains_account_id(self, sample_findings):
        publisher = SNSPublisher(region=REGION)
        subject = publisher._build_subject(sample_findings)
        assert ACCOUNT_ID in subject

    def test_subject_contains_total_savings(self, sample_findings):
        publisher = SNSPublisher(region=REGION)
        subject = publisher._build_subject(sample_findings)
        # 60 + 10 + 5 + 80 + 2 + 3 = 160.0
        assert "160.00" in subject

    def test_subject_is_at_most_100_chars(self, sample_findings):
        publisher = SNSPublisher(region=REGION)
        subject = publisher._build_subject(sample_findings)
        assert len(subject) <= 100

    def test_subject_handles_missing_account_id(self):
        publisher = SNSPublisher(region=REGION)
        subject = publisher._build_subject({})
        assert "unknown" in subject

    def test_subject_handles_missing_cost_fields(self):
        publisher = SNSPublisher(region=REGION)
        subject = publisher._build_subject({"account_id": "111"})
        assert "0.00" in subject


# ------------------------------------------------------------------ #
# Total savings calculation
# ------------------------------------------------------------------ #

class TestTotalSavings:
    def test_sums_all_cost_fields(self, sample_findings):
        total = SNSPublisher._total_savings(sample_findings)
        assert total == 160.0

    def test_returns_zero_for_empty_findings(self):
        assert SNSPublisher._total_savings({}) == 0.0

    def test_handles_partial_findings(self):
        findings = {"ec2": {"idle_instances_monthly_cost": 42.50}}
        assert SNSPublisher._total_savings(findings) == 42.50

    def test_rounds_to_two_decimal_places(self):
        findings = {"ec2": {"idle_instances_monthly_cost": 0.001}}
        assert SNSPublisher._total_savings(findings) == 0.0


# ------------------------------------------------------------------ #
# Graceful failure on AWS errors
# ------------------------------------------------------------------ #

@mock_aws
class TestGracefulFailure:
    def test_returns_false_on_client_error(self, sample_findings, sample_html):
        topic_arn = _create_topic()
        os.environ[_ENV_VAR] = topic_arn

        publisher = SNSPublisher(region=REGION)
        with patch.object(
            publisher._client,
            "publish",
            side_effect=ClientError(
                {"Error": {"Code": "AuthorizationError", "Message": "Access Denied"}},
                "Publish",
            ),
        ):
            result = publisher.publish_report(sample_findings, sample_html)
        assert result is False

    def test_returns_false_on_unexpected_exception(self, sample_findings, sample_html):
        topic_arn = _create_topic()
        os.environ[_ENV_VAR] = topic_arn

        publisher = SNSPublisher(region=REGION)
        with patch.object(publisher._client, "publish", side_effect=RuntimeError("boom")):
            result = publisher.publish_report(sample_findings, sample_html)
        assert result is False

    def test_logs_error_on_client_error(self, sample_findings, sample_html, caplog):
        import logging
        topic_arn = _create_topic()
        os.environ[_ENV_VAR] = topic_arn

        publisher = SNSPublisher(region=REGION)
        with patch.object(
            publisher._client,
            "publish",
            side_effect=ClientError(
                {"Error": {"Code": "AuthorizationError", "Message": "Access Denied"}},
                "Publish",
            ),
        ):
            with caplog.at_level(logging.ERROR, logger="notifications.sns_publisher"):
                publisher.publish_report(sample_findings, sample_html)
        assert "SNS publish failed" in caplog.text
