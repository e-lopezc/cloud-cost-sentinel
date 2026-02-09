"""
Cloud Cost Sentinel - Main Entry Point
Scans AWS resources for cost optimization opportunities.
"""

import logging
import sys
import boto3
from datetime import datetime, timezone
from scanners.ec2_scanner import EC2Scanner
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
        # Step 1: Verify AWS credentials
        logger.info("Step 1: Verifying AWS credentials...")
        success, account_id, region, error = verify_aws_credentials()

        if not success:
            logger.error(f"Failed to verify AWS credentials: {error}")
            logger.error("Cannot proceed without valid AWS credentials.")
            return 1

        logger.info("✓ AWS credentials verified successfully")
        logger.info("")

        # Step 2: EC2 Instance Scanning
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

        logger.info("")

        # Step 3: Placeholder for other scanners
        logger.info("  - EBS volume scanning: TODO")
        logger.info("Step 3: Other resource scanning (not yet implemented)")
        logger.info("  - RDS database scanning: TODO")
        logger.info("  - S3 bucket scanning: TODO")
        logger.info("")

        # Collect all findings
        all_findings = {
            "account_id": account_id,
            "region": region,
            "scan_timestamp": datetime.now(timezone.utc).isoformat(),
            "ec2": ec2_summary,
            "rds": None,  # TODO
            "ebs": None,  # TODO
            "s3": None,   # TODO
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
