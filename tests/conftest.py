"""
Pytest configuration and shared fixtures for Cloud Cost Sentinel tests.
"""

import os
import sys
import pytest
import boto3
from moto import mock_aws

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture(scope="function")
def aws_credentials():
    """
    Mock AWS credentials for moto.

    This fixture sets up fake AWS credentials that moto requires
    to work properly. These are not real credentials.
    """
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

    yield

    # Cleanup (optional, as each test gets fresh environment)
    for key in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
                "AWS_SECURITY_TOKEN", "AWS_SESSION_TOKEN"]:
        os.environ.pop(key, None)


@pytest.fixture(scope="function")
def mock_ec2(aws_credentials):
    """
    Create a mocked EC2 environment with a VPC and subnet.

    Returns:
        dict: Contains ec2_client, vpc_id, and subnet_id
    """
    with mock_aws():
        ec2_client = boto3.client("ec2", region_name="us-east-1")

        # Create VPC
        vpc_response = ec2_client.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc_response["Vpc"]["VpcId"]

        # Create subnet
        subnet_response = ec2_client.create_subnet(
            VpcId=vpc_id,
            CidrBlock="10.0.1.0/24"
        )
        subnet_id = subnet_response["Subnet"]["SubnetId"]

        yield {
            "ec2_client": ec2_client,
            "vpc_id": vpc_id,
            "subnet_id": subnet_id,
        }


@pytest.fixture(scope="function")
def mock_cloudwatch(aws_credentials):
    """
    Create a mocked CloudWatch client.

    Returns:
        boto3.client: Mocked CloudWatch client
    """
    with mock_aws():
        yield boto3.client("cloudwatch", region_name="us-east-1")


@pytest.fixture(scope="function")
def mock_rds(aws_credentials):
    """
    Create a mocked RDS client.

    Returns:
        boto3.client: Mocked RDS client
    """
    with mock_aws():
        yield boto3.client("rds", region_name="us-east-1")


@pytest.fixture(scope="function")
def mock_s3(aws_credentials):
    """
    Create a mocked S3 client.

    Returns:
        boto3.client: Mocked S3 client
    """
    with mock_aws():
        yield boto3.client("s3", region_name="us-east-1")


@pytest.fixture(scope="function")
def sample_ec2_instance():
    """
    Provide sample EC2 instance data for testing.

    Returns:
        dict: Sample instance metadata
    """
    from datetime import datetime, timezone

    return {
        "instance_id": "i-1234567890abcdef0",
        "instance_name": "test-instance",
        "instance_type": "t3.medium",
        "launch_time": datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        "private_ip": "10.0.1.100",
        "public_ip": "54.123.45.67",
    }


@pytest.fixture(scope="function")
def sample_cpu_datapoints():
    """
    Provide sample CloudWatch CPU datapoints for testing.

    Returns:
        list: Sample CPU utilization datapoints
    """
    from datetime import datetime, timedelta, timezone

    base_time = datetime.now(timezone.utc)

    return [
        {"Timestamp": base_time - timedelta(hours=i), "Average": 2.0 + (i * 0.5)}
        for i in range(24)
    ]


@pytest.fixture(scope="function")
def sample_idle_instance(sample_ec2_instance):
    """
    Provide sample idle instance finding data.

    Returns:
        dict: Sample idle instance with all fields
    """
    return {
        **sample_ec2_instance,
        "launch_time": sample_ec2_instance["launch_time"].isoformat(),
        "avg_cpu_percent": 2.5,
        "analysis_period_days": 7,
        "idle_threshold": 5.0,
        "recommendation": "Consider stopping or terminating this instance",
    }
