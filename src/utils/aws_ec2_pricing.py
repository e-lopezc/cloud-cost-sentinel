"""
AWS EC2 Pricing Utility Module for Cloud Cost Sentinel.

Provides functions to fetch real-time EC2 pricing from the AWS Price List API.
Uses the API with fallback to default prices when unavailable.

See README.md in this directory for limitations and considerations.
"""

import json
import logging
from functools import lru_cache
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

# Default EC2 on-demand prices per hour (Linux, US East N. Virginia)
# These are approximate prices as of 2024 - used as fallback if API fails
# Prices vary by region; these are us-east-1 baseline prices
DEFAULT_EC2_PRICES = {
    # General Purpose - T series (burstable)
    "t2.nano": 0.0058,
    "t2.micro": 0.0116,
    "t2.small": 0.023,
    "t2.medium": 0.0464,
    "t2.large": 0.0928,
    "t2.xlarge": 0.1856,
    "t2.2xlarge": 0.3712,
    "t3.nano": 0.0052,
    "t3.micro": 0.0104,
    "t3.small": 0.0208,
    "t3.medium": 0.0416,
    "t3.large": 0.0832,
    "t3.xlarge": 0.1664,
    "t3.2xlarge": 0.3328,
    "t3a.nano": 0.0047,
    "t3a.micro": 0.0094,
    "t3a.small": 0.0188,
    "t3a.medium": 0.0376,
    "t3a.large": 0.0752,
    "t3a.xlarge": 0.1504,
    "t3a.2xlarge": 0.3008,
    # General Purpose - M series
    "m5.large": 0.096,
    "m5.xlarge": 0.192,
    "m5.2xlarge": 0.384,
    "m5.4xlarge": 0.768,
    "m5.8xlarge": 1.536,
    "m5.12xlarge": 2.304,
    "m5.16xlarge": 3.072,
    "m5.24xlarge": 4.608,
    "m6i.large": 0.096,
    "m6i.xlarge": 0.192,
    "m6i.2xlarge": 0.384,
    "m6i.4xlarge": 0.768,
    "m6i.8xlarge": 1.536,
    "m6i.12xlarge": 2.304,
    "m6i.16xlarge": 3.072,
    "m6i.24xlarge": 4.608,
    "m7i.large": 0.1008,
    "m7i.xlarge": 0.2016,
    "m7i.2xlarge": 0.4032,
    "m7i.4xlarge": 0.8064,
    # Compute Optimized - C series
    "c5.large": 0.085,
    "c5.xlarge": 0.17,
    "c5.2xlarge": 0.34,
    "c5.4xlarge": 0.68,
    "c5.9xlarge": 1.53,
    "c5.12xlarge": 2.04,
    "c5.18xlarge": 3.06,
    "c5.24xlarge": 4.08,
    "c6i.large": 0.085,
    "c6i.xlarge": 0.17,
    "c6i.2xlarge": 0.34,
    "c6i.4xlarge": 0.68,
    "c6i.8xlarge": 1.36,
    "c6i.12xlarge": 2.04,
    "c6i.16xlarge": 2.72,
    "c6i.24xlarge": 4.08,
    # Memory Optimized - R series
    "r5.large": 0.126,
    "r5.xlarge": 0.252,
    "r5.2xlarge": 0.504,
    "r5.4xlarge": 1.008,
    "r5.8xlarge": 2.016,
    "r5.12xlarge": 3.024,
    "r5.16xlarge": 4.032,
    "r5.24xlarge": 6.048,
    "r6i.large": 0.126,
    "r6i.xlarge": 0.252,
    "r6i.2xlarge": 0.504,
    "r6i.4xlarge": 1.008,
    "r6i.8xlarge": 2.016,
    "r6i.12xlarge": 3.024,
    "r6i.16xlarge": 4.032,
    "r6i.24xlarge": 6.048,
    # Storage Optimized - I series
    "i3.large": 0.156,
    "i3.xlarge": 0.312,
    "i3.2xlarge": 0.624,
    "i3.4xlarge": 1.248,
    "i3.8xlarge": 2.496,
    "i3.16xlarge": 4.992,
    # Graviton (ARM) instances
    "t4g.nano": 0.0042,
    "t4g.micro": 0.0084,
    "t4g.small": 0.0168,
    "t4g.medium": 0.0336,
    "t4g.large": 0.0672,
    "t4g.xlarge": 0.1344,
    "t4g.2xlarge": 0.2688,
    "m6g.large": 0.077,
    "m6g.xlarge": 0.154,
    "m6g.2xlarge": 0.308,
    "m6g.4xlarge": 0.616,
    "m7g.large": 0.0816,
    "m7g.xlarge": 0.1632,
    "m7g.2xlarge": 0.3264,
    "c6g.large": 0.068,
    "c6g.xlarge": 0.136,
    "c6g.2xlarge": 0.272,
    "c7g.large": 0.0725,
    "c7g.xlarge": 0.145,
    "c7g.2xlarge": 0.29,
    "r6g.large": 0.1008,
    "r6g.xlarge": 0.2016,
    "r6g.2xlarge": 0.4032,
    "r7g.large": 0.1071,
    "r7g.xlarge": 0.2142,
    "r7g.2xlarge": 0.4284,
}

# Hours in a month (average)
HOURS_PER_MONTH = 730


class AWSEC2PricingClient:
    """
    Client for fetching AWS EC2 pricing information using the Price List API.

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

    def get_ec2_price_per_hour(
        self,
        instance_type: str,
        region: str,
        operating_system: str = "Linux",
    ) -> Optional[float]:
        """
        Get the on-demand price per hour for an EC2 instance type.

        Args:
            instance_type: EC2 instance type (e.g., 't3.micro', 'm5.large')
            region: AWS region code (e.g., 'us-east-1', 'eu-west-1')
            operating_system: OS type ('Linux', 'Windows', 'RHEL', 'SUSE')

        Returns:
            Price per hour in USD, or None if not found
        """
        cache_key = f"ec2_{instance_type}_{region}_{operating_system}"
        if cache_key in self._price_cache:
            return self._price_cache[cache_key]

        try:
            response = self.pricing_client.get_products(
                ServiceCode="AmazonEC2",
                Filters=[
                    {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type},
                    {"Type": "TERM_MATCH", "Field": "regionCode", "Value": region},
                    {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": operating_system},
                    {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
                    {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"},
                    {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
                ],
                MaxResults=10,
            )

            for product_json in response.get("PriceList", []):
                product = json.loads(product_json)
                price = self._extract_price_from_product(product)
                if price is not None:
                    self._price_cache[cache_key] = price
                    logger.debug(
                        f"Fetched EC2 price for {instance_type} in {region}: ${price}/hour"
                    )
                    return price

            logger.warning(f"No pricing found for instance type {instance_type} in {region}")
            return None

        except (BotoCoreError, ClientError) as e:
            logger.error(f"Error fetching EC2 pricing: {e}")
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
            for term_key, term_value in terms.items():
                price_dimensions = term_value.get("priceDimensions", {})
                for dimension_key, dimension_value in price_dimensions.items():
                    price_per_unit = dimension_value.get("pricePerUnit", {})
                    usd_price = price_per_unit.get("USD")
                    if usd_price:
                        return float(usd_price)
        except (KeyError, ValueError, TypeError) as e:
            logger.debug(f"Error extracting price from product: {e}")
        return None


@lru_cache(maxsize=1)
def get_pricing_client() -> AWSEC2PricingClient:
    """Get a cached pricing client instance."""
    return AWSEC2PricingClient()


def get_ec2_price_per_hour(
    instance_type: str,
    region: str,
    operating_system: str = "Linux",
    use_api: bool = True,
) -> float:
    """
    Get the on-demand price per hour for an EC2 instance type.

    This is the main function to use for pricing lookups. It will try the
    AWS Price List API first (if use_api=True), then fall back to defaults.

    Args:
        instance_type: EC2 instance type (e.g., 't3.micro', 'm5.large')
        region: AWS region code (e.g., 'us-east-1')
        operating_system: OS type ('Linux', 'Windows', 'RHEL', 'SUSE')
        use_api: Whether to try the Price List API first (default: True)

    Returns:
        Price per hour in USD
    """
    if use_api:
        try:
            client = get_pricing_client()
            price = client.get_ec2_price_per_hour(instance_type, region, operating_system)
            if price is not None:
                return price
        except Exception as e:
            logger.warning(f"Failed to fetch pricing from API, using defaults: {e}")

    # Fall back to default prices
    # Default prices are for Linux in us-east-1
    default_price = DEFAULT_EC2_PRICES.get(instance_type)
    if default_price is not None:
        return default_price

    # If instance type not in defaults, estimate based on similar types
    logger.warning(f"No default price for {instance_type}, using t3.medium as fallback")
    return DEFAULT_EC2_PRICES.get("t3.medium", 0.0416)


def calculate_ec2_monthly_cost(
    instance_type: str,
    region: str,
    operating_system: str = "Linux",
    use_api: bool = True,
) -> float:
    """
    Calculate the estimated monthly cost for an EC2 instance.

    Assumes the instance runs 24/7 for the entire month (730 hours).

    Args:
        instance_type: EC2 instance type (e.g., 't3.micro', 'm5.large')
        region: AWS region code (e.g., 'us-east-1')
        operating_system: OS type ('Linux', 'Windows', 'RHEL', 'SUSE')
        use_api: Whether to use the Price List API

    Returns:
        Estimated monthly cost in USD
    """
    hourly_price = get_ec2_price_per_hour(instance_type, region, operating_system, use_api)
    monthly_cost = hourly_price * HOURS_PER_MONTH
    return round(monthly_cost, 2)


def calculate_ec2_daily_cost(
    instance_type: str,
    region: str,
    operating_system: str = "Linux",
    use_api: bool = True,
) -> float:
    """
    Calculate the estimated daily cost for an EC2 instance.

    Assumes the instance runs 24 hours.

    Args:
        instance_type: EC2 instance type (e.g., 't3.micro', 'm5.large')
        region: AWS region code (e.g., 'us-east-1')
        operating_system: OS type ('Linux', 'Windows', 'RHEL', 'SUSE')
        use_api: Whether to use the Price List API

    Returns:
        Estimated daily cost in USD
    """
    hourly_price = get_ec2_price_per_hour(instance_type, region, operating_system, use_api)
    daily_cost = hourly_price * 24
    return round(daily_cost, 2)


def get_instance_type_family(instance_type: str) -> str:
    """
    Extract the instance family from an instance type.

    Args:
        instance_type: EC2 instance type (e.g., 't3.micro', 'm5.large')

    Returns:
        Instance family (e.g., 't3', 'm5')
    """
    if "." in instance_type:
        return instance_type.split(".")[0]
    return instance_type


def get_instance_type_size(instance_type: str) -> str:
    """
    Extract the instance size from an instance type.

    Args:
        instance_type: EC2 instance type (e.g., 't3.micro', 'm5.large')

    Returns:
        Instance size (e.g., 'micro', 'large')
    """
    if "." in instance_type:
        return instance_type.split(".")[1]
    return "unknown"
