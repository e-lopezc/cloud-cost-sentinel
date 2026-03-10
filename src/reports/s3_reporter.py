"""
S3 Report Uploader for Cloud Cost Sentinel.
Saves the JSON findings and HTML report to a configured S3 bucket.

Bucket name is read from the SENTINEL_REPORT_BUCKET environment variable.
If the variable is not set or the upload fails, the error is logged and
the function returns gracefully without raising — the overall scan exit
code is not affected.
"""

import json
import logging
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

_ENV_VAR = "SENTINEL_REPORT_BUCKET"


class S3Reporter:
    """Uploads JSON findings and HTML report to S3."""

    def __init__(self, region: str):
        self.region = region
        self.bucket = os.environ.get(_ENV_VAR, "").strip()

    # ------------------------------------------------------------------ #
    # Public interface
    # ------------------------------------------------------------------ #

    def upload_reports(self, all_findings: dict, html_report: str) -> bool:
        """
        Upload findings.json and report.html to S3.

        Args:
            all_findings: The raw findings dict from main.py.
            html_report:  The rendered HTML string from HTMLReporter.

        Returns:
            True if both files uploaded successfully, False otherwise.
        """
        if not self.bucket:
            logger.warning(
                f"Skipping S3 upload: {_ENV_VAR} environment variable is not set."
            )
            return False

        date_prefix = self._date_prefix(all_findings)
        json_key = f"reports/{date_prefix}/findings.json"
        html_key = f"reports/{date_prefix}/report.html"

        try:
            client = boto3.client("s3", region_name=self.region)

            self._put_object(
                client,
                key=json_key,
                body=json.dumps(all_findings, indent=2, default=str),
                content_type="application/json",
            )
            logger.info(f"Uploaded findings JSON → s3://{self.bucket}/{json_key}")

            self._put_object(
                client,
                key=html_key,
                body=html_report,
                content_type="text/html; charset=utf-8",
            )
            logger.info(f"Uploaded HTML report  → s3://{self.bucket}/{html_key}")

            return True

        except (ClientError, BotoCoreError) as e:
            logger.error(f"S3 upload failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during S3 upload: {e}")
            return False

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _put_object(self, client, key: str, body: str, content_type: str) -> None:
        client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body.encode("utf-8"),
            ContentType=content_type,
        )

    def _date_prefix(self, all_findings: dict) -> str:
        """Return a YYYY-MM-DD string from the scan timestamp, falling back to today."""
        ts = all_findings.get("scan_timestamp", "")
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return datetime.now(timezone.utc).strftime("%Y-%m-%d")
