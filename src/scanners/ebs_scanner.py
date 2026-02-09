"""
EBS Volumes Scanner Module for Cloud Cost Sentinel.

The idea is to warn users about EBS volumes that are not attached to any
EC2 instances or have low I/O activity over a specified period.
"""

from datetime import datetime, timezone, timedelta
import logging
import boto3
from botocore.exceptions import BotoCoreError, ClientError

from src.utils.aws_ebs_pricing import calculate_ebs_monthly_cost

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

        Checks both read and write operations to determine total I/O.

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

                    # Get read operations
                    read_metrics = self.cloudwatch_client.get_metric_statistics(
                        Namespace="AWS/EBS",
                        MetricName="VolumeReadOps",
                        Dimensions=[{"Name": "VolumeId", "Value": volume_id}],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=86400,  # Daily data points
                        Statistics=["Sum"],
                    )

                    # Get write operations
                    write_metrics = self.cloudwatch_client.get_metric_statistics(
                        Namespace="AWS/EBS",
                        MetricName="VolumeWriteOps",
                        Dimensions=[{"Name": "VolumeId", "Value": volume_id}],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=86400,  # Daily data points
                        Statistics=["Sum"],
                    )

                    total_read_io = sum(dp["Sum"] for dp in read_metrics.get("Datapoints", []))
                    total_write_io = sum(dp["Sum"] for dp in write_metrics.get("Datapoints", []))
                    total_io = total_read_io + total_write_io

                    if total_io < self.io_threshold:
                        low_io_volumes.append(volume)

            logger.info(f"Found {len(low_io_volumes)} low I/O EBS volumes.")
            return low_io_volumes

        except (BotoCoreError, ClientError) as e:
            logger.error(f"Error fetching low I/O EBS volumes: {e}")
            return []

    def calculate_monthly_cost(self, volume, use_api=True):
        """
        Calculate the estimated monthly cost of an EBS volume based on its type and size.
        Uses the AWS Price List API to fetch current pricing (falls back to defaults if unavailable).

        Args:
            volume (dict): EBS volume dictionary with metadata
            use_api (bool): Whether to use the AWS Price List API (default: True)
        Returns:
            float: Estimated monthly cost in USD
        """
        volume_type = volume.get("VolumeType", "standard")
        size_gb = volume.get("Size", 0)
        iops = volume.get("Iops")
        throughput = volume.get("Throughput")  # MB/s for gp3

        return calculate_ebs_monthly_cost(
            volume_type=volume_type,
            size_gb=size_gb,
            region=self.region,
            iops=iops,
            throughput_mbps=throughput,
            use_api=use_api,
        )

    def analyze_ebs_volumes(self, use_pricing_api=True):
        """
        Analyze EBS volumes for unattached and low I/O activity.

        Args:
            use_pricing_api (bool): Whether to use the AWS Price List API for cost calculation (default: True)

        Returns:
            dict: Summary of EBS volume analysis with counts, details, and estimated costs
        """
        self.unattached_volumes = self.get_unattached_volumes()
        self.low_io_volumes = self.get_low_io_volumes()

        # Calculate total monthly cost for unattached volumes
        unattached_volumes_cost = sum(
            self.calculate_monthly_cost(volume, use_api=use_pricing_api)
            for volume in self.unattached_volumes
        )

        # Calculate total monthly cost for low I/O volumes
        low_io_volumes_cost = sum(
            self.calculate_monthly_cost(volume, use_api=use_pricing_api)
            for volume in self.low_io_volumes
        )

        # Total potential savings (unattached + low I/O, excluding duplicates)
        unattached_ids = {v["VolumeId"] for v in self.unattached_volumes}
        low_io_only_volumes = [v for v in self.low_io_volumes if v["VolumeId"] not in unattached_ids]
        low_io_only_cost = sum(
            self.calculate_monthly_cost(volume, use_api=use_pricing_api)
            for volume in low_io_only_volumes
        )
        total_potential_savings = unattached_volumes_cost + low_io_only_cost

        return {
            "unattached_volumes_count": len(self.unattached_volumes),
            "unattached_volumes_monthly_cost": round(unattached_volumes_cost, 2),
            "low_io_volumes_count": len(self.low_io_volumes),
            "low_io_volumes_monthly_cost": round(low_io_volumes_cost, 2),
            "total_potential_monthly_savings": round(total_potential_savings, 2),
            "unattached_volumes": self.unattached_volumes,
            "low_io_volumes": self.low_io_volumes,
        }
