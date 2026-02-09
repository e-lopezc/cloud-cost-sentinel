"""
EC2 Scanner Module for Cloud Cost Sentinel.

Scans for idle EC2 instances based on CPU utilization metrics from CloudWatch.
Identifies instances that may be candidates for downsizing or termination.
"""

import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timedelta, timezone
import logging

from src.utils.aws_ec2_pricing import calculate_ec2_monthly_cost

logger = logging.getLogger(__name__)


class EC2Scanner:
    """
    EC2 Scanner to analyze running instances and their CPU utilization.
    Identifies idle instances based on configurable thresholds.
    """

    def __init__(self, region, days=14, idle_threshold=5.0):
        """
        Initialize the EC2 Scanner.

        Args:
            region (str): AWS region to scan
            days (int): Number of days to analyze for CPU metrics (default: 14)
            idle_threshold (float): CPU percentage below which instance is considered idle (default: 5.0)
        """
        self.region = region
        self.days = days
        self.idle_threshold = idle_threshold
        self.ec2_client = boto3.client("ec2", region_name=self.region)
        self.cloudwatch_client = boto3.client("cloudwatch", region_name=self.region)
        self.idle_instances = []

    def get_running_ec2_instances(self):
        """
        Get a list of running EC2 instances in the specified region.

        Returns:
            list: List of instance dictionaries with metadata
        """
        instances = []
        try:
            paginator = self.ec2_client.get_paginator("describe_instances")
            page_iterator = paginator.paginate(
                Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
            )

            for page in page_iterator:
                for reservation in page["Reservations"]:
                    for instance in reservation["Instances"]:
                        # Extract instance name from tags
                        instance_name = "N/A"
                        for tag in instance.get("Tags", []):
                            if tag["Key"] == "Name":
                                instance_name = tag["Value"]
                                break

                        instances.append({
                            "instance_id": instance["InstanceId"],
                            "instance_type": instance["InstanceType"],
                            "instance_name": instance_name,
                            "launch_time": instance["LaunchTime"],
                            "private_ip": instance.get("PrivateIpAddress", "N/A"),
                            "public_ip": instance.get("PublicIpAddress", "N/A"),
                        })

            logger.info(f"Found {len(instances)} running EC2 instances in {self.region}")
            return instances

        except ClientError as e:
            logger.error(f"Error fetching EC2 instances: {e}")
            return []

    def get_ec2_cpu_utilization(self, instance_id):
        """
        Get CPU Utilization metrics for the specified EC2 instance.

        Args:
            instance_id (str): The EC2 instance ID

        Returns:
            list: List of CloudWatch datapoints with CPU utilization
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.days)

        try:
            response = self.cloudwatch_client.get_metric_statistics(
                Namespace="AWS/EC2",
                MetricName="CPUUtilization",
                Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,  # 1 hour periods for efficiency
                Statistics=["Average"],
            )
            return response["Datapoints"]
        except ClientError as e:
            logger.error(f"Error fetching CPU utilization for {instance_id}: {e}")
            return []

    def calculate_average_cpu(self, datapoints):
        """
        Calculate the average CPU utilization from CloudWatch datapoints.

        Args:
            datapoints (list): List of CloudWatch datapoints

        Returns:
            float or None: Average CPU utilization, or None if no data
        """
        if not datapoints:
            return None

        return sum(dp["Average"] for dp in datapoints) / len(datapoints)

    def calculate_monthly_cost(self, instance_type, use_api=True):
        """
        Calculate the estimated monthly cost of an EC2 instance.

        Args:
            instance_type (str): EC2 instance type (e.g., 't3.micro', 'm5.large')
            use_api (bool): Whether to use the AWS Price List API (default: True)

        Returns:
            float: Estimated monthly cost in USD
        """
        return calculate_ec2_monthly_cost(
            instance_type=instance_type,
            region=self.region,
            operating_system="Linux",
            use_api=use_api,
        )

    def analyze_ec2_instances(self, use_pricing_api=True):
        """
        Analyze running EC2 instances and identify idle ones.

        Args:
            use_pricing_api (bool): Whether to use the AWS Price List API for cost calculation (default: True)

        Returns:
            list: List of dictionaries containing idle instance details
        """
        self.idle_instances = []  # Reset for fresh scan
        instances = self.get_running_ec2_instances()

        if not instances:
            logger.info("No running EC2 instances found.")
            return self.idle_instances

        logger.info(f"Analyzing {len(instances)} instances for idle detection (threshold: {self.idle_threshold}% CPU)")

        for instance in instances:
            instance_id = instance["instance_id"]
            cpu_data = self.get_ec2_cpu_utilization(instance_id)
            avg_cpu = self.calculate_average_cpu(cpu_data)

            if avg_cpu is not None:
                is_idle = avg_cpu <= self.idle_threshold

                if is_idle:
                    monthly_cost = self.calculate_monthly_cost(
                        instance["instance_type"], use_api=use_pricing_api
                    )
                    idle_instance = {
                        "instance_id": instance_id,
                        "instance_name": instance["instance_name"],
                        "instance_type": instance["instance_type"],
                        "launch_time": instance["launch_time"].isoformat() if hasattr(instance["launch_time"], 'isoformat') else str(instance["launch_time"]),
                        "private_ip": instance["private_ip"],
                        "public_ip": instance["public_ip"],
                        "avg_cpu_percent": round(avg_cpu, 2),
                        "estimated_monthly_cost": monthly_cost,
                        "analysis_period_days": self.days,
                        "idle_threshold": self.idle_threshold,
                        "recommendation": "Consider stopping or terminating this instance",
                    }
                    self.idle_instances.append(idle_instance)
                    logger.warning(
                        f"IDLE: {instance_id} ({instance['instance_name']}) - "
                        f"Type: {instance['instance_type']}, "
                        f"Avg CPU: {avg_cpu:.2f}% over {self.days} days"
                    )
                else:
                    logger.info(
                        f"OK: {instance_id} ({instance['instance_name']}) - "
                        f"Avg CPU: {avg_cpu:.2f}% over {self.days} days"
                    )
            else:
                logger.warning(
                    f"NO DATA: {instance_id} ({instance['instance_name']}) - "
                    f"No CPU metrics available for the last {self.days} days"
                )

        logger.info(
            f"EC2 scan complete: {len(self.idle_instances)} idle instances found "
            f"out of {len(instances)} total running instances"
        )

        return self.idle_instances

    def get_scan_summary(self, use_pricing_api=True):
        """
        Get a summary of the scan results.

        Args:
            use_pricing_api (bool): Whether to use the AWS Price List API for cost calculation (default: True)

        Returns:
            dict: Summary of the EC2 scan including cost information
        """
        # Calculate total monthly cost of idle instances
        total_idle_cost = sum(
            instance.get("estimated_monthly_cost", 0)
            for instance in self.idle_instances
        )

        return {
            "scanner": "EC2Scanner",
            "region": self.region,
            "analysis_period_days": self.days,
            "idle_threshold_percent": self.idle_threshold,
            "idle_instances_count": len(self.idle_instances),
            "idle_instances_monthly_cost": round(total_idle_cost, 2),
            "idle_instances": self.idle_instances,
            "scan_timestamp": datetime.now(timezone.utc).isoformat(),
        }
