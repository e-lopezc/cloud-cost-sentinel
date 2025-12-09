"""
Cloud Cost Sentinel - Main Entry Point
Scans AWS resources for cost optimization opportunities.
"""

import logging
import sys
from datetime import datetime, timezone
import boto3
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
        
        # Step 2: Placeholder for future scanning logic
        logger.info("Step 2: Resource scanning (not yet implemented)")
        logger.info("  - EC2 instance scanning: TODO")
        logger.info("  - RDS database scanning: TODO")
        logger.info("  - EBS volume scanning: TODO")
        logger.info("  - S3 bucket scanning: TODO")
        logger.info("")
        
        # Success
        logger.info("=" * 60)
        logger.info("Scan completed successfully.")
        logger.info(f"Scan finished at: {datetime.now(timezone.utc).strftime('%Y-%m-%d-T%H:%M:%SZ')}")
        logger.info("=" * 60)

        return 0

    except Exception as e:
        logger.error("An unexpected error occurred during the scan.", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
