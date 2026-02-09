"""
S3 Scanner Module for Cloud Cost Sentinel.

Scans for unused S3 buckets based on CloudWatch request metrics.
Identifies buckets with zero activity over a configurable period.
Buckets without request metrics enabled are reported separately.
"""

import boto3
from botocore.exceptions import ClientError, BotoCoreError
from datetime import datetime, timedelta, timezone
import logging

from src.utils.aws_s3_pricing import calculate_bucket_monthly_cost, format_bytes

logger = logging.getLogger(__name__)


class S3Scanner:
    """
    S3 Scanner to analyze S3 buckets for cost optimization.
    Identifies unused buckets based on request activity.
    """

    def __init__(self, region, days=30, request_threshold=10):
        """
        Initialize the S3 Scanner.

        Args:
            region (str): AWS region for CloudWatch queries
            days (int): Number of days to analyze for request metrics (default: 30)
            request_threshold (int): Total requests below which bucket is considered unused (default: 10)
        """
        self.region = region
        self.days = days
        self.request_threshold = request_threshold
        self.s3_client = boto3.client("s3", region_name=self.region)
        self.cloudwatch_client = boto3.client("cloudwatch", region_name=self.region)
        self.unused_buckets = []
        self.buckets_without_metrics = []

    def get_all_buckets(self):
        """
        Get a list of all S3 buckets in the account.

        Returns:
            list: List of bucket dictionaries with metadata
        """
        buckets = []
        try:
            response = self.s3_client.list_buckets()

            for bucket in response.get("Buckets", []):
                bucket_name = bucket["Name"]
                creation_date = bucket.get("CreationDate")

                # Get bucket region
                bucket_region = self._get_bucket_region(bucket_name)

                buckets.append({
                    "bucket_name": bucket_name,
                    "creation_date": creation_date,
                    "region": bucket_region,
                })

            logger.info(f"Found {len(buckets)} S3 buckets in account")
            return buckets

        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error fetching S3 buckets: {e}")
            return []

    def _get_bucket_region(self, bucket_name):
        """
        Get the region of a specific bucket.

        Args:
            bucket_name (str): Name of the bucket

        Returns:
            str: Region name or 'us-east-1' for None response
        """
        try:
            response = self.s3_client.get_bucket_location(Bucket=bucket_name)
            # LocationConstraint is None for us-east-1
            location = response.get("LocationConstraint")
            return location if location else "us-east-1"
        except (ClientError, BotoCoreError) as e:
            logger.warning(f"Could not get region for bucket {bucket_name}: {e}")
            return "unknown"

    def get_bucket_request_metrics(self, bucket_name, bucket_region):
        """
        Get request metrics for a bucket from CloudWatch.

        Note: Request metrics must be enabled on the bucket for this to return data.

        Args:
            bucket_name (str): Name of the bucket
            bucket_region (str): Region of the bucket

        Returns:
            dict: Contains 'has_metrics' boolean and 'total_requests' count
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.days)

        # Use regional CloudWatch client for the bucket's region
        try:
            regional_cw = boto3.client("cloudwatch", region_name=bucket_region)
        except (ClientError, BotoCoreError):
            regional_cw = self.cloudwatch_client

        try:
            # AllRequests metric requires request metrics to be enabled
            response = regional_cw.get_metric_statistics(
                Namespace="AWS/S3",
                MetricName="AllRequests",
                Dimensions=[
                    {"Name": "BucketName", "Value": bucket_name},
                    {"Name": "FilterId", "Value": "EntireBucket"},
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # Daily data points
                Statistics=["Sum"],
            )

            datapoints = response.get("Datapoints", [])

            if not datapoints:
                # No datapoints could mean metrics not enabled OR zero requests
                # We need to check if metrics are configured
                return {"has_metrics": False, "total_requests": 0}

            total_requests = sum(dp.get("Sum", 0) for dp in datapoints)
            return {"has_metrics": True, "total_requests": int(total_requests)}

        except (ClientError, BotoCoreError) as e:
            logger.warning(f"Error fetching metrics for bucket {bucket_name}: {e}")
            return {"has_metrics": False, "total_requests": 0}

    def get_bucket_storage_metrics(self, bucket_name, bucket_region):
        """
        Get storage metrics for a bucket from CloudWatch.

        These metrics are published daily by S3 automatically (free).

        Args:
            bucket_name (str): Name of the bucket
            bucket_region (str): Region of the bucket

        Returns:
            dict: Contains 'size_bytes' and 'object_count'
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=2)  # Need at least 1 day of data

        try:
            regional_cw = boto3.client("cloudwatch", region_name=bucket_region)
        except (ClientError, BotoCoreError):
            regional_cw = self.cloudwatch_client

        size_bytes = 0
        object_count = 0

        try:
            # Get bucket size
            size_response = regional_cw.get_metric_statistics(
                Namespace="AWS/S3",
                MetricName="BucketSizeBytes",
                Dimensions=[
                    {"Name": "BucketName", "Value": bucket_name},
                    {"Name": "StorageType", "Value": "StandardStorage"},
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=["Average"],
            )
            if size_response.get("Datapoints"):
                size_bytes = int(size_response["Datapoints"][-1].get("Average", 0))

            # Get object count
            count_response = regional_cw.get_metric_statistics(
                Namespace="AWS/S3",
                MetricName="NumberOfObjects",
                Dimensions=[
                    {"Name": "BucketName", "Value": bucket_name},
                    {"Name": "StorageType", "Value": "AllStorageTypes"},
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=["Average"],
            )
            if count_response.get("Datapoints"):
                object_count = int(count_response["Datapoints"][-1].get("Average", 0))

        except (ClientError, BotoCoreError) as e:
            logger.warning(f"Error fetching storage metrics for {bucket_name}: {e}")

        return {"size_bytes": size_bytes, "object_count": object_count}

    def is_bucket_unused(self, total_requests):
        """
        Determine if a bucket is unused based on request count.

        Args:
            total_requests (int): Total requests over the analysis period

        Returns:
            bool: True if bucket is considered unused
        """
        return total_requests <= self.request_threshold

    def analyze_s3_buckets(self):
        """
        Analyze S3 buckets and identify unused ones.

        Returns:
            list: List of dictionaries containing unused bucket details
        """
        self.unused_buckets = []
        self.buckets_without_metrics = []

        buckets = self.get_all_buckets()

        if not buckets:
            logger.info("No S3 buckets found.")
            return self.unused_buckets

        logger.info(f"Analyzing {len(buckets)} S3 buckets for activity")

        for bucket in buckets:
            bucket_name = bucket["bucket_name"]
            bucket_region = bucket["region"]
            creation_date = bucket["creation_date"]

            if bucket_region == "unknown":
                logger.warning(f"Skipping bucket {bucket_name}: unknown region")
                continue

            # Get request metrics
            request_metrics = self.get_bucket_request_metrics(bucket_name, bucket_region)

            # Get storage metrics (always available)
            storage_metrics = self.get_bucket_storage_metrics(bucket_name, bucket_region)

            # Calculate estimated monthly cost
            estimated_cost = calculate_bucket_monthly_cost(
                size_bytes=storage_metrics["size_bytes"],
                object_count=storage_metrics["object_count"],
            )

            bucket_info = {
                "bucket_name": bucket_name,
                "region": bucket_region,
                "creation_date": creation_date.isoformat() if creation_date else "N/A",
                "size_bytes": storage_metrics["size_bytes"],
                "size_formatted": format_bytes(storage_metrics["size_bytes"]),
                "object_count": storage_metrics["object_count"],
                "estimated_monthly_cost": estimated_cost,
                "analysis_period_days": self.days,
            }

            if not request_metrics["has_metrics"]:
                # Metrics not enabled - report separately
                bucket_info["status"] = "metrics_not_enabled"
                bucket_info["recommendation"] = "Enable request metrics to monitor bucket activity"
                self.buckets_without_metrics.append(bucket_info)
                logger.info(f"NO METRICS: {bucket_name} - Request metrics not enabled")

            elif self.is_bucket_unused(request_metrics["total_requests"]):
                # Unused bucket
                bucket_info["total_requests"] = request_metrics["total_requests"]
                bucket_info["request_threshold"] = self.request_threshold
                bucket_info["status"] = "unused"
                bucket_info["recommendation"] = "Consider archiving or deleting this unused bucket"
                self.unused_buckets.append(bucket_info)
                logger.warning(
                    f"UNUSED: {bucket_name} - "
                    f"Requests: {request_metrics['total_requests']} over {self.days} days"
                )
            else:
                logger.info(
                    f"ACTIVE: {bucket_name} - "
                    f"Requests: {request_metrics['total_requests']} over {self.days} days"
                )

        logger.info(
            f"S3 scan complete: {len(self.unused_buckets)} unused buckets, "
            f"{len(self.buckets_without_metrics)} buckets without metrics"
        )

        return self.unused_buckets

    def get_scan_summary(self):
        """
        Get a summary of the scan results.

        Returns:
            dict: Summary of the S3 scan including cost information
        """
        # Calculate total monthly cost of unused buckets
        total_unused_cost = sum(
            bucket.get("estimated_monthly_cost", 0)
            for bucket in self.unused_buckets
        )

        return {
            "scanner": "S3Scanner",
            "region": self.region,
            "analysis_period_days": self.days,
            "request_threshold": self.request_threshold,
            "unused_buckets_count": len(self.unused_buckets),
            "unused_buckets_monthly_cost": round(total_unused_cost, 2),
            "unused_buckets": self.unused_buckets,
            "buckets_without_metrics_count": len(self.buckets_without_metrics),
            "buckets_without_metrics": self.buckets_without_metrics,
            "total_potential_monthly_savings": round(total_unused_cost, 2),
            "scan_timestamp": datetime.now(timezone.utc).isoformat(),
        }
