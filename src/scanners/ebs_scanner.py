"""
EBS Volumes Scanner Module for Cloud Cost Sentinel.

The idea is to warn users about EBS volumes that are not attached to any
EC2 instances or have low I/O activity over a specified period.
"""

from datetime import datetime, timezone, timedelta
import logging
import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

class EBSScanner:
    """
    EBS Scanner to analyze EBS volumes for cost optimization.
    Identifies unattached volumes and those with low I/O activity.
    """

    def __init__(self, region, days=14, io_threshold=100):
        """
        Initialize the EBS Scanner.

        Args:
            region (str): AWS region to scan
            days (int): Number of days to analyze for I/O metrics (default: 14)
            io_threshold (int): I/O operations below which volume is considered low activity (default: 100)
        """
        self.region = region
        self.days = days
        self.io_threshold = io_threshold
        self.ec2_client = boto3.client("ec2", region_name=self.region)
        self.cloudwatch_client = boto3.client("cloudwatch", region_name=self.region)
        self.unattached_volumes = []
        self.low_io_volumes = []

    def get_unattached_volumes(self):
        """
        Get a list of unattached EBS volumes in the specified region.

        Returns:
            list: List of unattached volume dictionaries with metadata
        """
        volumes = []
        try:
            paginator = self.ec2_client.get_paginator("describe_volumes")
            page_iterator = paginator.paginate(
                Filters=[{"Name": "status", "Values": ["available"]}]
            )

            for page in page_iterator:
                for volume in page["Volumes"]:
                    volumes.append(volume)

            logger.info(f"Found {len(volumes)} unattached EBS volumes.")
            return volumes

        except (BotoCoreError, ClientError) as e:
            logger.error(f"Error fetching unattached EBS volumes: {e}")
            return []

    def get_low_io_volumes(self):
        """
        Get a list of EBS volumes with low I/O activity.

        Returns:
            list: List of low I/O volume dictionaries with metadata
        """
        low_io_volumes = []
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.days)

        try:
            paginator = self.ec2_client.get_paginator("describe_volumes")
            page_iterator = paginator.paginate()

            for page in page_iterator:
                for volume in page["Volumes"]:
                    volume_id = volume["VolumeId"]

                    metrics = self.cloudwatch_client.get_metric_statistics(
                        Namespace="AWS/EBS",
                        MetricName="VolumeReadOps",
                        Dimensions=[{"Name": "VolumeId", "Value": volume_id}],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=86400,  # Daily data points
                        Statistics=["Sum"],
                    )

                    total_io = sum(dp["Sum"] for dp in metrics.get("Datapoints", []))

                    if total_io < self.io_threshold:
                        low_io_volumes.append(volume)

            logger.info(f"Found {len(low_io_volumes)} low I/O EBS volumes.")
            return low_io_volumes

        except (BotoCoreError, ClientError) as e:
            logger.error(f"Error fetching low I/O EBS volumes: {e}")
            return []
