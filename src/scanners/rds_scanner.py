"""
RDS Scanner Module for Cloud Cost Sentinel.

Scans for idle RDS PostgreSQL instances based on CPU utilization and database connections.
Also identifies old manual snapshots that may no longer be needed.
"""

import boto3
from botocore.exceptions import ClientError, BotoCoreError
from datetime import datetime, timedelta, timezone
import logging

from src.utils.aws_rds_pricing import calculate_rds_monthly_cost, calculate_snapshot_monthly_cost

logger = logging.getLogger(__name__)


class RDSScanner:
    """
    RDS Scanner to analyze RDS instances for cost optimization.
    Identifies idle instances and old snapshots.
    """

    def __init__(self, region, days=14, cpu_threshold=5.0, connections_threshold=1, snapshot_age_days=90):
        """
        Initialize the RDS Scanner.

        Args:
            region (str): AWS region to scan
            days (int): Number of days to analyze for metrics (default: 14)
            cpu_threshold (float): CPU percentage below which instance is considered idle (default: 5.0)
            connections_threshold (int): Avg connections below which instance is considered idle (default: 1)
            snapshot_age_days (int): Snapshots older than this are flagged (default: 90)
        """
        self.region = region
        self.days = days
        self.cpu_threshold = cpu_threshold
        self.connections_threshold = connections_threshold
        self.snapshot_age_days = snapshot_age_days
        self.rds_client = boto3.client("rds", region_name=self.region)
        self.cloudwatch_client = boto3.client("cloudwatch", region_name=self.region)
        self.idle_instances = []
        self.old_snapshots = []

    def get_rds_instances(self):
        """
        Get a list of RDS instances in the specified region.

        Returns:
            list: List of RDS instance dictionaries with metadata
        """
        instances = []
        try:
            paginator = self.rds_client.get_paginator("describe_db_instances")
            page_iterator = paginator.paginate()

            for page in page_iterator:
                for db_instance in page["DBInstances"]:
                    instances.append({
                        "db_instance_id": db_instance["DBInstanceIdentifier"],
                        "db_instance_class": db_instance["DBInstanceClass"],
                        "engine": db_instance["Engine"],
                        "engine_version": db_instance.get("EngineVersion", "N/A"),
                        "status": db_instance["DBInstanceStatus"],
                        "allocated_storage_gb": db_instance.get("AllocatedStorage", 0),
                        "multi_az": db_instance.get("MultiAZ", False),
                        "storage_type": db_instance.get("StorageType", "N/A"),
                    })

            logger.info(f"Found {len(instances)} RDS instances in {self.region}")
            return instances

        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error fetching RDS instances: {e}")
            return []

    def get_cpu_utilization(self, db_instance_id):
        """
        Get CPU Utilization metrics for the specified RDS instance.

        Args:
            db_instance_id (str): The RDS instance identifier

        Returns:
            list: List of CloudWatch datapoints with CPU utilization
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.days)

        try:
            response = self.cloudwatch_client.get_metric_statistics(
                Namespace="AWS/RDS",
                MetricName="CPUUtilization",
                Dimensions=[{"Name": "DBInstanceIdentifier", "Value": db_instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,  # 1 hour periods
                Statistics=["Average"],
            )
            return response.get("Datapoints", [])
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error fetching CPU utilization for {db_instance_id}: {e}")
            return []

    def get_database_connections(self, db_instance_id):
        """
        Get DatabaseConnections metrics for the specified RDS instance.

        Args:
            db_instance_id (str): The RDS instance identifier

        Returns:
            list: List of CloudWatch datapoints with connection counts
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.days)

        try:
            response = self.cloudwatch_client.get_metric_statistics(
                Namespace="AWS/RDS",
                MetricName="DatabaseConnections",
                Dimensions=[{"Name": "DBInstanceIdentifier", "Value": db_instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,  # 1 hour periods
                Statistics=["Average"],
            )
            return response.get("Datapoints", [])
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error fetching database connections for {db_instance_id}: {e}")
            return []

    def calculate_average(self, datapoints):
        """
        Calculate the average value from CloudWatch datapoints.

        Args:
            datapoints (list): List of CloudWatch datapoints

        Returns:
            float or None: Average value, or None if no data
        """
        if not datapoints:
            return None

        return sum(dp["Average"] for dp in datapoints) / len(datapoints)

    def is_instance_idle(self, avg_cpu, avg_connections):
        """
        Determine if an RDS instance is idle based on CPU and connections.

        Args:
            avg_cpu (float or None): Average CPU utilization
            avg_connections (float or None): Average database connections

        Returns:
            bool: True if instance is considered idle
        """
        if avg_cpu is None or avg_connections is None:
            return False

        return avg_cpu <= self.cpu_threshold and avg_connections <= self.connections_threshold

    def calculate_monthly_cost(self, instance, use_api=True):
        """
        Calculate the estimated monthly cost of an RDS instance.

        Args:
            instance (dict): RDS instance dictionary with metadata
            use_api (bool): Whether to use the AWS Price List API (default: True)

        Returns:
            float: Estimated monthly cost in USD
        """
        return calculate_rds_monthly_cost(
            db_instance_class=instance["db_instance_class"],
            region=self.region,
            multi_az=instance.get("multi_az", False),
            allocated_storage_gb=instance.get("allocated_storage_gb", 0),
            storage_type=instance.get("storage_type", "gp2"),
            use_api=use_api,
        )

    def get_manual_snapshots(self):
        """
        Get a list of manual RDS snapshots in the specified region.

        Returns:
            list: List of snapshot dictionaries with metadata
        """
        snapshots = []
        try:
            paginator = self.rds_client.get_paginator("describe_db_snapshots")
            page_iterator = paginator.paginate(SnapshotType="manual")

            for page in page_iterator:
                for snapshot in page["DBSnapshots"]:
                    snapshots.append({
                        "snapshot_id": snapshot["DBSnapshotIdentifier"],
                        "db_instance_id": snapshot.get("DBInstanceIdentifier", "N/A"),
                        "snapshot_create_time": snapshot.get("SnapshotCreateTime"),
                        "allocated_storage_gb": snapshot.get("AllocatedStorage", 0),
                        "engine": snapshot.get("Engine", "N/A"),
                        "status": snapshot.get("Status", "N/A"),
                    })

            logger.info(f"Found {len(snapshots)} manual RDS snapshots in {self.region}")
            return snapshots

        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error fetching RDS snapshots: {e}")
            return []

    def find_old_snapshots(self):
        """
        Find manual snapshots older than the configured threshold.

        Returns:
            list: List of old snapshot dictionaries
        """
        self.old_snapshots = []
        snapshots = self.get_manual_snapshots()
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.snapshot_age_days)

        for snapshot in snapshots:
            create_time = snapshot.get("snapshot_create_time")
            if create_time and create_time < cutoff_date:
                age_days = (datetime.now(timezone.utc) - create_time).days
                snapshot["age_days"] = age_days
                snapshot["snapshot_create_time"] = create_time.isoformat()
                snapshot["estimated_monthly_cost"] = calculate_snapshot_monthly_cost(
                    snapshot["allocated_storage_gb"]
                )
                snapshot["recommendation"] = "Consider deleting this old snapshot"
                self.old_snapshots.append(snapshot)
                logger.warning(
                    f"OLD SNAPSHOT: {snapshot['snapshot_id']} - "
                    f"Age: {age_days} days, Size: {snapshot['allocated_storage_gb']}GB"
                )

        logger.info(f"Found {len(self.old_snapshots)} snapshots older than {self.snapshot_age_days} days")
        return self.old_snapshots

    def analyze_rds_instances(self, use_pricing_api=True):
        """
        Analyze RDS instances and identify idle ones.

        Args:
            use_pricing_api (bool): Whether to use the AWS Price List API for cost calculation (default: True)

        Returns:
            list: List of dictionaries containing idle instance details
        """
        self.idle_instances = []
        instances = self.get_rds_instances()

        # Only analyze instances that are available
        available_instances = [i for i in instances if i["status"] == "available"]

        if not available_instances:
            logger.info("No available RDS instances found.")
            return self.idle_instances

        logger.info(
            f"Analyzing {len(available_instances)} RDS instances "
            f"(CPU threshold: {self.cpu_threshold}%, connections threshold: {self.connections_threshold})"
        )

        for instance in available_instances:
            db_instance_id = instance["db_instance_id"]

            cpu_data = self.get_cpu_utilization(db_instance_id)
            connections_data = self.get_database_connections(db_instance_id)

            avg_cpu = self.calculate_average(cpu_data)
            avg_connections = self.calculate_average(connections_data)

            if self.is_instance_idle(avg_cpu, avg_connections):
                monthly_cost = self.calculate_monthly_cost(instance, use_api=use_pricing_api)
                idle_instance = {
                    "db_instance_id": db_instance_id,
                    "db_instance_class": instance["db_instance_class"],
                    "engine": instance["engine"],
                    "engine_version": instance["engine_version"],
                    "allocated_storage_gb": instance["allocated_storage_gb"],
                    "storage_type": instance["storage_type"],
                    "multi_az": instance["multi_az"],
                    "avg_cpu_percent": round(avg_cpu, 2),
                    "avg_connections": round(avg_connections, 2),
                    "estimated_monthly_cost": monthly_cost,
                    "analysis_period_days": self.days,
                    "cpu_threshold": self.cpu_threshold,
                    "connections_threshold": self.connections_threshold,
                    "recommendation": "Consider stopping or terminating this idle RDS instance",
                }
                self.idle_instances.append(idle_instance)
                logger.warning(
                    f"IDLE: {db_instance_id} - "
                    f"Class: {instance['db_instance_class']}, "
                    f"Avg CPU: {avg_cpu:.2f}%, Avg Connections: {avg_connections:.2f}"
                )
            elif avg_cpu is not None and avg_connections is not None:
                logger.info(
                    f"OK: {db_instance_id} - "
                    f"Avg CPU: {avg_cpu:.2f}%, Avg Connections: {avg_connections:.2f}"
                )
            else:
                logger.warning(
                    f"NO DATA: {db_instance_id} - "
                    f"Insufficient metrics for the last {self.days} days"
                )

        logger.info(
            f"RDS scan complete: {len(self.idle_instances)} idle instances found "
            f"out of {len(available_instances)} available instances"
        )

        return self.idle_instances

    def get_scan_summary(self):
        """
        Get a summary of the scan results.

        Returns:
            dict: Summary of the RDS scan including cost information
        """
        # Calculate total monthly cost of idle instances
        total_idle_cost = sum(
            instance.get("estimated_monthly_cost", 0)
            for instance in self.idle_instances
        )

        # Calculate total monthly cost of old snapshots
        total_snapshot_cost = sum(
            snapshot.get("estimated_monthly_cost", 0)
            for snapshot in self.old_snapshots
        )

        return {
            "scanner": "RDSScanner",
            "region": self.region,
            "analysis_period_days": self.days,
            "cpu_threshold_percent": self.cpu_threshold,
            "connections_threshold": self.connections_threshold,
            "snapshot_age_threshold_days": self.snapshot_age_days,
            "idle_instances_count": len(self.idle_instances),
            "idle_instances_monthly_cost": round(total_idle_cost, 2),
            "idle_instances": self.idle_instances,
            "old_snapshots_count": len(self.old_snapshots),
            "old_snapshots_monthly_cost": round(total_snapshot_cost, 2),
            "old_snapshots": self.old_snapshots,
            "total_potential_monthly_savings": round(total_idle_cost + total_snapshot_cost, 2),
            "scan_timestamp": datetime.now(timezone.utc).isoformat(),
        }
