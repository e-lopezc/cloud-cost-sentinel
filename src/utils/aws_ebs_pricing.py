"""
AWS EBS Pricing Utility Module for Cloud Cost Sentinel.

Provides functions to fetch real-time EBS pricing from the AWS Price List API.
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

# Default EBS prices per GB/month (used as fallback if API fails)
# These are approximate US East (N. Virginia) prices as of 2024
DEFAULT_EBS_PRICES = {
    "standard": 0.05,
    "gp2": 0.10,
    "gp3": 0.08,
    "io1": 0.125,
    "io2": 0.125,
    "sc1": 0.015,
    "st1": 0.045,
}

# IOPS pricing for provisioned IOPS volumes (per IOPS/month)
DEFAULT_IOPS_PRICES = {
    "io1": 0.065,
    "io2": 0.065,
    "gp3": 0.005,  # Only for IOPS above 3000
}

# Throughput pricing for gp3 (per MB/s/month above 125 MB/s)
DEFAULT_GP3_THROUGHPUT_PRICE = 0.06


class AWSPricingClient:
    """
    Client for fetching AWS pricing information using the Price List API.

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

    def get_ebs_price_per_gb(self, volume_type: str, region: str) -> Optional[float]:
        """
        Get the price per GB/month for an EBS volume type in a specific region.

        Args:
            volume_type: EBS volume type (gp2, gp3, io1, io2, st1, sc1, standard)
            region: AWS region code (e.g., 'us-east-1', 'eu-west-1')

        Returns:
            Price per GB/month in USD, or None if not found
        """
        cache_key = f"ebs_{volume_type}_{region}"
        if cache_key in self._price_cache:
            return self._price_cache[cache_key]

        try:
            # Map volume type to the API's volumeApiName
            volume_api_name = volume_type if volume_type != "standard" else "standard"

            response = self.pricing_client.get_products(
                ServiceCode="AmazonEC2",
                Filters=[
                    {"Type": "TERM_MATCH", "Field": "productFamily", "Value": "Storage"},
                    {"Type": "TERM_MATCH", "Field": "volumeApiName", "Value": volume_api_name},
                    {"Type": "TERM_MATCH", "Field": "regionCode", "Value": region},
                ],
                MaxResults=10,
            )

            for product_json in response.get("PriceList", []):
                product = json.loads(product_json)
                price = self._extract_price_from_product(product)
                if price is not None:
                    self._price_cache[cache_key] = price
                    logger.debug(f"Fetched EBS price for {volume_type} in {region}: ${price}/GB/month")
                    return price

            logger.warning(f"No pricing found for volume type {volume_type} in {region}")
            return None

        except (BotoCoreError, ClientError) as e:
            logger.error(f"Error fetching EBS pricing: {e}")
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

    def get_ebs_iops_price(self, volume_type: str, region: str) -> Optional[float]:
        """
        Get the price per provisioned IOPS/month for io1, io2, or gp3 volumes.

        Args:
            volume_type: EBS volume type (io1, io2, gp3)
            region: AWS region code

        Returns:
            Price per IOPS/month in USD, or None if not applicable
        """
        if volume_type not in ("io1", "io2", "gp3"):
            return None

        cache_key = f"ebs_iops_{volume_type}_{region}"
        if cache_key in self._price_cache:
            return self._price_cache[cache_key]

        try:
            # IOPS pricing uses different product family
            product_family = "System Operation" if volume_type in ("io1", "io2") else "Storage"

            response = self.pricing_client.get_products(
                ServiceCode="AmazonEC2",
                Filters=[
                    {"Type": "TERM_MATCH", "Field": "productFamily", "Value": product_family},
                    {"Type": "TERM_MATCH", "Field": "regionCode", "Value": region},
                    {"Type": "TERM_MATCH", "Field": "usagetype", "Value": f"EBS:VolumeUsage.piops"},
                ],
                MaxResults=10,
            )

            for product_json in response.get("PriceList", []):
                product = json.loads(product_json)
                price = self._extract_price_from_product(product)
                if price is not None:
                    self._price_cache[cache_key] = price
                    return price

            return None

        except (BotoCoreError, ClientError) as e:
            logger.error(f"Error fetching IOPS pricing: {e}")
            return None


@lru_cache(maxsize=1)
def get_pricing_client() -> AWSPricingClient:
    """Get a cached pricing client instance."""
    return AWSPricingClient()


def get_ebs_cost_per_gb(volume_type: str, region: str, use_api: bool = True) -> float:
    """
    Get the cost per GB/month for an EBS volume type.

    This is the main function to use for pricing lookups. It will try the
    AWS Price List API first (if use_api=True), then fall back to defaults.

    Args:
        volume_type: EBS volume type (gp2, gp3, io1, io2, st1, sc1, standard)
        region: AWS region code (e.g., 'us-east-1')
        use_api: Whether to try the Price List API first (default: True)

    Returns:
        Price per GB/month in USD
    """
    if use_api:
        try:
            client = get_pricing_client()
            price = client.get_ebs_price_per_gb(volume_type, region)
            if price is not None:
                return price
        except Exception as e:
            logger.warning(f"Failed to fetch pricing from API, using defaults: {e}")

    # Fall back to default prices
    return DEFAULT_EBS_PRICES.get(volume_type, DEFAULT_EBS_PRICES["gp2"])


def calculate_ebs_monthly_cost(
    volume_type: str,
    size_gb: int,
    region: str,
    iops: Optional[int] = None,
    throughput_mbps: Optional[int] = None,
    use_api: bool = True,
) -> float:
    """
    Calculate the total monthly cost for an EBS volume including IOPS and throughput.

    Args:
        volume_type: EBS volume type
        size_gb: Volume size in GB
        region: AWS region code
        iops: Provisioned IOPS (for io1, io2, gp3)
        throughput_mbps: Provisioned throughput in MB/s (for gp3)
        use_api: Whether to use the Price List API

    Returns:
        Total monthly cost in USD
    """
    # Base storage cost
    price_per_gb = get_ebs_cost_per_gb(volume_type, region, use_api)
    total_cost = size_gb * price_per_gb

    # Add IOPS cost for provisioned IOPS volumes
    if volume_type in ("io1", "io2") and iops:
        iops_price = DEFAULT_IOPS_PRICES.get(volume_type, 0.065)
        total_cost += iops * iops_price
    elif volume_type == "gp3" and iops and iops > 3000:
        # gp3 includes 3000 IOPS free
        extra_iops = iops - 3000
        iops_price = DEFAULT_IOPS_PRICES.get("gp3", 0.005)
        total_cost += extra_iops * iops_price

    # Add throughput cost for gp3
    if volume_type == "gp3" and throughput_mbps and throughput_mbps > 125:
        # gp3 includes 125 MB/s free
        extra_throughput = throughput_mbps - 125
        total_cost += extra_throughput * DEFAULT_GP3_THROUGHPUT_PRICE

    return round(total_cost, 2)
