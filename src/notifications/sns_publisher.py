"""
SNS Notification Publisher for Cloud Cost Sentinel.
Sends the HTML cost report as an email via an SNS topic.

The topic ARN is read from the SENTINEL_SNS_TOPIC_ARN environment variable.
If the variable is not set or publishing fails, the error is logged and the
function returns gracefully without raising — the overall scan exit code is
not affected.
"""

import logging
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

_ENV_VAR = "SENTINEL_SNS_TOPIC_ARN"


class SNSPublisher:
    """Publishes the cost report as an email notification via SNS."""

    def __init__(self, region: str):
        self.region = region
        self.topic_arn = os.environ.get(_ENV_VAR, "").strip()
        self._client = boto3.client("sns", region_name=region)

    # ------------------------------------------------------------------ #
    # Public interface
    # ------------------------------------------------------------------ #

    def publish_report(self, all_findings: dict, html_report: str) -> bool:
        """
        Publish the HTML cost report to the configured SNS topic.

        The message subject includes the account ID and total potential savings
        so recipients can triage the email without opening it.

        Args:
            all_findings: The raw findings dict from main.py.
            html_report:  The rendered HTML string from HTMLReporter.

        Returns:
            True if the message was published successfully, False otherwise.
        """
        if not self.topic_arn:
            logger.warning(
                f"Skipping SNS notification: {_ENV_VAR} environment variable is not set."
            )
            return False

        subject = self._build_subject(all_findings)

        try:
            self._client.publish(
                TopicArn=self.topic_arn,
                Subject=subject,
                Message=html_report,
            )
            logger.info(f"SNS notification sent → {self.topic_arn}")
            return True
        except (BotoCoreError, ClientError) as e:
            logger.error(f"SNS publish failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error publishing SNS notification: {e}")
            return False

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _build_subject(self, all_findings: dict) -> str:
        """
        Build a concise email subject line.
        SNS subjects are capped at 100 characters.
        """
        account_id = all_findings.get("account_id", "unknown")
        total_savings = self._total_savings(all_findings)
        subject = f"Cloud Cost Sentinel | Account {account_id} | ${total_savings:.2f}/mo potential savings"
        return subject[:100]

    @staticmethod
    def _total_savings(all_findings: dict) -> float:
        """Sum up monthly cost estimates across all scanner summaries."""
        keys = [
            ("ec2", "idle_instances_monthly_cost"),
            ("ebs", "unattached_volumes_monthly_cost"),
            ("ebs", "low_io_volumes_monthly_cost"),
            ("rds", "idle_instances_monthly_cost"),
            ("rds", "old_snapshots_monthly_cost"),
            ("s3", "unused_buckets_monthly_cost"),
        ]
        total = 0.0
        for scanner, field in keys:
            total += all_findings.get(scanner, {}).get(field, 0.0)
        return round(total, 2)
