"""
Cloud Cost Sentinel - Main Entry Point
Scans AWS resources for cost optimization opportunities.
"""

import logging
import sys
import boto3
from datetime import datetime, timezone
from scanners.ec2_scanner import EC2Scanner
from scanners.ebs_scanner import EBSScanner
from scanners.rds_scanner import RDSScanner
from scanners.s3_scanner import S3Scanner
from botocore.exceptions import ClientError, NoCredentialsError

# Configure logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


def verify_aws_credentials():
    """
    Verify AWS credentials are configured and working.
    Returns tuple: (success: bool, account_id: str, region: str, error: str)
    """
    try:
        # Create STS client to verify credentials
        sts_client = boto3.client("sts")

        # Get caller identity - this will fail if credentials are invalid
        response = sts_client.get_caller_identity()

        account_id = response["Account"]
        user_arn = response["Arn"]

        # Get current region
        session = boto3.session.Session()
        region = session.region_name or "us-east-1"  # Default to us-east-1 if not set

        logger.info("AWS credentials verified successfully")
        logger.info(f"  Account ID: {account_id}")
        logger.info(f"  User/Role ARN: {user_arn}")
        logger.info(f"  Region: {region}")

        return True, account_id, region, None

    except NoCredentialsError:
        error_msg = "No AWS credentials found. Please configure AWS credentials."
        logger.error(error_msg)
        return False, None, None, error_msg

    except ClientError as e:
        error_msg = f"AWS credentials verification failed: {e}"
        logger.error(error_msg)
        return False, None, None, error_msg

    except Exception as e:
        error_msg = f"Unexpected error verifying AWS credentials: {e}"
        logger.error(error_msg)
        return False, None, None, error_msg


def main():
    """Main function to initiate the cloud cost scanning process."""
    logger.info("=" * 60)
    logger.info("Cloud Cost Sentinel - Starting Scan")
    logger.info(f"Scan started at: {datetime.now(timezone.utc).strftime('%Y-%m-%d-T%H:%M:%SZ')}")
    logger.info("=" * 60)

    try:

        logger.info("Step 1: Verifying AWS credentials...")
        success, account_id, region, error = verify_aws_credentials()

        if not success:
            logger.error(f"Failed to verify AWS credentials: {error}")
            logger.error("Cannot proceed without valid AWS credentials.")
            return 1

        logger.info("✓ AWS credentials verified successfully")
        logger.info("")

        # EC2 Instance Scanning
        logger.info("Step 2: Scanning EC2 instances for idle resources...")
        logger.info("")

        ec2_scanner = EC2Scanner(region=region, days=7, idle_threshold=5.0)
        idle_instances = ec2_scanner.analyze_ec2_instances()
        ec2_summary = ec2_scanner.get_scan_summary()

        logger.info("")
        logger.info(f"EC2 Scan Results: {ec2_summary['idle_instances_count']} idle instances found")


        if idle_instances:
            logger.info("Idle instances detected:")
            for instance in idle_instances:
                logger.info(f"  - {instance['instance_id']} ({instance['instance_name']}): "
                           f"{instance['avg_cpu_percent']}% avg CPU")

        logger.info(f"Total estimated monthly cost of idle instances: ${ec2_summary['idle_instances_monthly_cost']}")
        logger.info("")

        # Ebs Volume Scanning
        logger.info("Step 3: Scanning EBS volumes for idle resources...")
        ebs_scanner = EBSScanner(region=region, days=14, io_threshold=99)
        ebs_summary = ebs_scanner.analyze_ebs_volumes()

        logger.info(f"EBS Scan Results: {ebs_summary['unattached_volumes_count']} unattached volumes, ")
        if ebs_summary['unattached_volumes_count'] > 0:

            for volume in ebs_summary['unattached_volumes']:
                logger.info(f"  - {volume['volume_id']} ({volume['size_gb']} GB, {volume['volume_type']})")

            logger.info(f"  - Total estimated monthly cost of unattached volumes: ${ebs_summary['unattached_volumes_monthly_cost']}")

        logger.info(f"{ebs_summary['low_io_volumes_count']} low I/O volumes found")
        if ebs_summary['low_io_volumes_count'] > 0:

            logger.info("")
            for volume in ebs_summary['low_io_volumes']:
                logger.info(f"  - {volume['volume_id']} ({volume['size_gb']} GB, {volume['volume_type']}): "
                        f"{volume['avg_io_operations']} avg I/O operations")

            logger.info(f"  - Total estimated monthly cost of low I/O volumes: ${ebs_summary['low_io_volumes_monthly_cost']}")

        logger.info("")
        logger.info("Step 3: Scanning RDS databases for idle resources...")

        rds_scanner = RDSScanner(region=region, days=7, cpu_threshold=5.0, connections_threshold=5)

        rds_scan_snapshots = rds_scanner.find_old_snapshots()
        rds_scan_instances = rds_scanner.analyze_rds_instances()
        rds_summary = rds_scanner.get_scan_summary()

        logger.info(f"RDS Scan Results: {rds_summary['idle_instances_count']} idle instances found")

        if rds_summary['idle_instances_count'] > 0:
            logger.info("Idle RDS instances detected:")
            for instance in rds_summary['idle_instances']:
                logger.info(f"  - {instance['db_instance_identifier']} ({instance['db_instance_class']}): "
                           f"{instance['avg_cpu_percent']}% avg CPU, {instance['avg_db_connections']} avg connections")

            logger.info(f"  - Total estimated monthly cost of idle RDS instances: ${rds_summary['idle_instances_monthly_cost']}")

        logger.info(f"{rds_summary['old_snapshots_count']} old snapshots found")
        if rds_summary['old_snapshots_count'] > 0:
            logger.info(f"{rds_summary['old_snapshots_count']} old snapshots found:")
            for snapshot in rds_summary['old_snapshots']:
                logger.info(f"  - {snapshot['db_snapshot_identifier']} (DB: {snapshot['db_instance_identifier']}), "
                           f"created on {snapshot['snapshot_create_time']}")

            logger.info(f"  - Total estimated monthly cost of old snapshots: ${rds_summary['old_snapshots_monthly_cost']}")

        logger.info("")
        logger.info("Step 4: Scanning S3 buckets for idle resources...")
        s3_scanner = S3Scanner(region=region, days=60, access_threshold=10)
        s3_buckets_scan = s3_scanner.analyze_s3_buckets()
        s3_summary = s3_scanner.get_scan_summary()

        logger.info(f"S3 Scan Results: {s3_summary['idle_buckets_count']} idle buckets found")
        if s3_summary['idle_buckets_count'] > 0:
            logger.info("Idle S3 buckets detected:")
            for bucket in s3_summary['idle_buckets']:
                logger.info(f"  - {bucket['bucket_name']} (created on {bucket['creation_date']}): "
                           f"{bucket['avg_access_count']} avg accesses")

            logger.info(f"  - Total estimated monthly cost of idle S3 buckets: ${s3_summary['idle_buckets_monthly_cost']}")

        # Collect all findings
        all_findings = {
            "account_id": account_id,
            "region": region,
            "scan_timestamp": datetime.now(timezone.utc).isoformat(),
            "ec2": ec2_summary,
            "ebs": ebs_summary,
            "rds": rds_summary,
            "s3": s3_summary,
        }

        # Success
        logger.info("=" * 60)
        logger.info("Scan completed successfully.")
        logger.info(f"Total idle EC2 instances: {ec2_summary['idle_instances_count']}")
        logger.info(f"Scan finished at: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
        logger.info("=" * 60)

        return 0

    except Exception as e:
        logger.error("An unexpected error occurred during the scan.", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
