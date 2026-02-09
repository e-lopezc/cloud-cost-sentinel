"""
AWS RDS Pricing Utility Module for Cloud Cost Sentinel.

Provides functions to fetch real-time RDS PostgreSQL pricing from the AWS Price List API.
Uses the API with fallback to default prices when unavailable.

Note: This module focuses on PostgreSQL instances only.
Prices are approximate and may vary. Always verify with AWS Pricing Calculator.
"""

import json
import logging
from functools import lru_cache
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

# Default RDS PostgreSQL on-demand prices per hour (US East N. Virginia)
# Prices as of 2025 - used as fallback if API fails
# Source: https://aws.amazon.com/rds/postgresql/pricing/
# Prices are for Single-AZ deployments; Multi-AZ is roughly 2x
DEFAULT_RDS_POSTGRES_PRICES = {
    # T4g instances (Graviton2, burstable)
    "db.t4g.micro": 0.016,
    "db.t4g.small": 0.032,
    "db.t4g.medium": 0.065,
    "db.t4g.large": 0.129,
    "db.t4g.xlarge": 0.258,
    "db.t4g.2xlarge": 0.516,
    # T3 instances (burstable)
    "db.t3.micro": 0.017,
    "db.t3.small": 0.034,
    "db.t3.medium": 0.068,
    "db.t3.large": 0.136,
    "db.t3.xlarge": 0.272,
    "db.t3.2xlarge": 0.544,
    # M6g instances (Graviton2, general purpose)
    "db.m6g.large": 0.154,
    "db.m6g.xlarge": 0.308,
    "db.m6g.2xlarge": 0.616,
    "db.m6g.4xlarge": 1.232,
    "db.m6g.8xlarge": 2.464,
    "db.m6g.12xlarge": 3.696,
    "db.m6g.16xlarge": 4.928,
    # M6i instances (general purpose)
    "db.m6i.large": 0.171,
    "db.m6i.xlarge": 0.342,
    "db.m6i.2xlarge": 0.684,
    "db.m6i.4xlarge": 1.368,
    "db.m6i.8xlarge": 2.736,
    "db.m6i.12xlarge": 4.104,
    "db.m6i.16xlarge": 5.472,
    "db.m6i.24xlarge": 8.208,
    # M7g instances (Graviton3, general purpose)
    "db.m7g.large": 0.168,
    "db.m7g.xlarge": 0.336,
    "db.m7g.2xlarge": 0.672,
    "db.m7g.4xlarge": 1.344,
    "db.m7g.8xlarge": 2.688,
    "db.m7g.12xlarge": 4.032,
    "db.m7g.16xlarge": 5.376,
    # M5 instances (general purpose)
    "db.m5.large": 0.171,
    "db.m5.xlarge": 0.342,
    "db.m5.2xlarge": 0.684,
    "db.m5.4xlarge": 1.368,
    "db.m5.8xlarge": 2.736,
    "db.m5.12xlarge": 4.104,
    "db.m5.16xlarge": 5.472,
    "db.m5.24xlarge": 8.208,
    # R6g instances (Graviton2, memory optimized)
    "db.r6g.large": 0.216,
    "db.r6g.xlarge": 0.432,
    "db.r6g.2xlarge": 0.864,
    "db.r6g.4xlarge": 1.728,
    "db.r6g.8xlarge": 3.456,
    "db.r6g.12xlarge": 5.184,
    "db.r6g.16xlarge": 6.912,
    # R6i instances (memory optimized)
    "db.r6i.large": 0.24,
    "db.r6i.xlarge": 0.48,
    "db.r6i.2xlarge": 0.96,
    "db.r6i.4xlarge": 1.92,
    "db.r6i.8xlarge": 3.84,
    "db.r6i.12xlarge": 5.76,
    "db.r6i.16xlarge": 7.68,
    "db.r6i.24xlarge": 11.52,
    # R7g instances (Graviton3, memory optimized)
    "db.r7g.large": 0.2352,
    "db.r7g.xlarge": 0.4704,
    "db.r7g.2xlarge": 0.9408,
    "db.r7g.4xlarge": 1.8816,
    "db.r7g.8xlarge": 3.7632,
    "db.r7g.12xlarge": 5.6448,
    "db.r7g.16xlarge": 7.5264,
    # R5 instances (memory optimized)
    "db.r5.large": 0.24,
    "db.r5.xlarge": 0.48,
    "db.r5.2xlarge": 0.96,
    "db.r5.4xlarge": 1.92,
    "db.r5.8xlarge": 3.84,
    "db.r5.12xlarge": 5.76,
    "db.r5.16xlarge": 7.68,
    "db.r5.24xlarge": 11.52,
}

# RDS storage prices per GB-month (US East N. Virginia)
DEFAULT_RDS_STORAGE_PRICES = {
    "gp2": 0.115,
    "gp3": 0.08,
    "io1": 0.125,
    "io2": 0.125,
    "standard": 0.10,  # magnetic
}

# RDS snapshot storage price per GB-month
DEFAULT_SNAPSHOT_PRICE_PER_GB = 0.095

# Hours in a month (average)
HOURS_PER_MONTH = 730


class AWSRDSPricingClient:
    """
    Client for fetching AWS RDS PostgreSQL pricing using the Price List API.

    Note: The Price List API is only available in us-east-1 and ap-south-1 regions,
    but it can fetch prices for any region.
    """

    def __init__(self, pricing_region: str = "us-east-1"):
        """
        Initialize the pricing client.

        Args:
            pricing_region: Region for the Pricing API endpoint (us-east-1 or ap-south-1)
        """
        self.pricing_client = boto3.client("pricing", region_name=pricing_region)
        self._price_cache = {}

    def get_rds_price_per_hour(
        self,
        db_instance_class: str,
        region: str,
        deployment_option: str = "Single-AZ",
    ) -> Optional[float]:
        """
        Get the on-demand price per hour for an RDS PostgreSQL instance.

        Args:
            db_instance_class: RDS instance class (e.g., 'db.t4g.micro', 'db.m6g.large')
            region: AWS region code (e.g., 'us-east-1', 'eu-west-1')
            deployment_option: 'Single-AZ' or 'Multi-AZ'

        Returns:
            Price per hour in USD, or None if not found
        """
        cache_key = f"rds_postgres_{db_instance_class}_{region}_{deployment_option}"
        if cache_key in self._price_cache:
            return self._price_cache[cache_key]

        try:
            response = self.pricing_client.get_products(
                ServiceCode="AmazonRDS",
                Filters=[
                    {"Type": "TERM_MATCH", "Field": "instanceType", "Value": db_instance_class},
                    {"Type": "TERM_MATCH", "Field": "regionCode", "Value": region},
                    {"Type": "TERM_MATCH", "Field": "databaseEngine", "Value": "PostgreSQL"},
                    {"Type": "TERM_MATCH", "Field": "deploymentOption", "Value": deployment_option},
                ],
                MaxResults=10,
            )

            for product_json in response.get("PriceList", []):
                product = json.loads(product_json)
                price = self._extract_price_from_product(product)
                if price is not None:
                    self._price_cache[cache_key] = price
                    logger.debug(
                        f"Fetched RDS PostgreSQL price for {db_instance_class} in {region}: ${price}/hour"
                    )
                    return price

            logger.warning(f"No pricing found for RDS PostgreSQL {db_instance_class} in {region}")
            return None

        except (BotoCoreError, ClientError) as e:
            logger.error(f"Error fetching RDS pricing: {e}")
            return None

    def _extract_price_from_product(self, product: dict) -> Optional[float]:
        """
        Extract the USD price from an AWS pricing product response.

        Args:
            product: Product dictionary from the Price List API

        Returns:
            Price as float, or None if not found
        """
        try:
            terms = product.get("terms", {}).get("OnDemand", {})
            for term_value in terms.values():
                price_dimensions = term_value.get("priceDimensions", {})
                for dimension_value in price_dimensions.values():
                    price_per_unit = dimension_value.get("pricePerUnit", {})
                    usd_price = price_per_unit.get("USD")
                    if usd_price:
                        return float(usd_price)
        except (KeyError, ValueError, TypeError) as e:
            logger.debug(f"Error extracting price from product: {e}")
        return None


@lru_cache(maxsize=1)
def get_pricing_client() -> AWSRDSPricingClient:
    """Get a cached pricing client instance."""
    return AWSRDSPricingClient()


def get_rds_price_per_hour(
    db_instance_class: str,
    region: str,
    multi_az: bool = False,
    use_api: bool = True,
) -> float:
    """
    Get the on-demand price per hour for an RDS PostgreSQL instance.

    Tries the AWS Price List API first (if use_api=True), then falls back to defaults.

    Args:
        db_instance_class: RDS instance class (e.g., 'db.t4g.micro', 'db.m6g.large')
        region: AWS region code (e.g., 'us-east-1')
        multi_az: Whether this is a Multi-AZ deployment
        use_api: Whether to try the Price List API first (default: True)

    Returns:
        Price per hour in USD
    """
    deployment_option = "Multi-AZ" if multi_az else "Single-AZ"

    if use_api:
        try:
            client = get_pricing_client()
            price = client.get_rds_price_per_hour(db_instance_class, region, deployment_option)
            if price is not None:
                return price
        except Exception as e:
            logger.warning(f"Failed to fetch RDS pricing from API, using defaults: {e}")

    # Fall back to default prices
    default_price = DEFAULT_RDS_POSTGRES_PRICES.get(db_instance_class)
    if default_price is not None:
        if multi_az:
            default_price *= 2
        return default_price

    # If instance class not in defaults, use db.t4g.medium as fallback
    logger.warning(f"No default price for {db_instance_class}, using db.t4g.medium as fallback")
    fallback_price = DEFAULT_RDS_POSTGRES_PRICES.get("db.t4g.medium", 0.065)
    if multi_az:
        fallback_price *= 2
    return fallback_price


def get_rds_storage_price_per_gb(storage_type: str) -> float:
    """
    Get the storage price per GB-month for RDS.

    Args:
        storage_type: Storage type ('gp2', 'gp3', 'io1', 'io2', 'standard')

    Returns:
        Price per GB-month in USD
    """
    return DEFAULT_RDS_STORAGE_PRICES.get(storage_type.lower(), 0.115)


def calculate_rds_monthly_cost(
    db_instance_class: str,
    region: str,
    multi_az: bool = False,
    allocated_storage_gb: int = 0,
    storage_type: str = "gp2",
    use_api: bool = True,
) -> float:
    """
    Calculate the estimated monthly cost for an RDS PostgreSQL instance.

    Includes both compute and storage costs.

    Args:
        db_instance_class: RDS instance class (e.g., 'db.t4g.micro', 'db.m6g.large')
        region: AWS region code (e.g., 'us-east-1')
        multi_az: Whether this is a Multi-AZ deployment
        allocated_storage_gb: Allocated storage in GB
        storage_type: Storage type ('gp2', 'gp3', 'io1', 'io2', 'standard')
        use_api: Whether to use the Price List API

    Returns:
        Estimated monthly cost in USD
    """
    # Compute cost
    hourly_price = get_rds_price_per_hour(db_instance_class, region, multi_az, use_api)
    compute_cost = hourly_price * HOURS_PER_MONTH

    # Storage cost
    storage_price_per_gb = get_rds_storage_price_per_gb(storage_type)
    storage_cost = storage_price_per_gb * allocated_storage_gb
    if multi_az:
        storage_cost *= 2

    total_cost = compute_cost + storage_cost
    return round(total_cost, 2)


def calculate_snapshot_monthly_cost(snapshot_size_gb: int) -> float:
    """
    Calculate the estimated monthly cost for storing an RDS snapshot.

    Args:
        snapshot_size_gb: Size of the snapshot in GB

    Returns:
        Estimated monthly cost in USD
    """
    cost = DEFAULT_SNAPSHOT_PRICE_PER_GB * snapshot_size_gb
    return round(cost, 2)
