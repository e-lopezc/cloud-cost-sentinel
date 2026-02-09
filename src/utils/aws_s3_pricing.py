"""
AWS S3 Pricing Utility Module for Cloud Cost Sentinel.

Provides functions to calculate S3 storage costs.
Uses default pricing with fallback estimates.

Note: S3 pricing is region-dependent and varies by storage class.
Prices are approximate and may vary. Always verify with AWS Pricing Calculator.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Default S3 storage prices per GB-month (US East N. Virginia)
# Prices as of 2025 - Source: https://aws.amazon.com/s3/pricing/
DEFAULT_S3_STORAGE_PRICES = {
    # Standard storage
    "STANDARD": 0.023,
    # Intelligent-Tiering (frequent access tier)
    "INTELLIGENT_TIERING": 0.023,
    # Standard-IA (Infrequent Access)
    "STANDARD_IA": 0.0125,
    # One Zone-IA
    "ONEZONE_IA": 0.01,
    # Glacier Instant Retrieval
    "GLACIER_IR": 0.004,
    # Glacier Flexible Retrieval
    "GLACIER": 0.0036,
    # Glacier Deep Archive
    "DEEP_ARCHIVE": 0.00099,
    # Reduced Redundancy (legacy, not recommended)
    "REDUCED_REDUNDANCY": 0.024,
}

# S3 request prices per 1,000 requests (US East N. Virginia)
DEFAULT_S3_REQUEST_PRICES = {
    "STANDARD": {
        "PUT_COPY_POST_LIST": 0.005,  # per 1,000 requests
        "GET_SELECT": 0.0004,  # per 1,000 requests
    },
    "STANDARD_IA": {
        "PUT_COPY_POST_LIST": 0.01,
        "GET_SELECT": 0.001,
    },
    "GLACIER": {
        "PUT_COPY_POST_LIST": 0.03,
        "GET_SELECT": 0.0004,
    },
}


def get_storage_price_per_gb(
    storage_class: str = "STANDARD",
    region: str = "us-east-1",
) -> float:
    """
    Get the storage price per GB-month for an S3 storage class.

    Args:
        storage_class: S3 storage class (e.g., 'STANDARD', 'GLACIER', 'STANDARD_IA')
        region: AWS region code (prices may vary by region)

    Returns:
        Price per GB-month in USD
    """
    # Normalize storage class name
    storage_class_upper = storage_class.upper().replace("-", "_")

    price = DEFAULT_S3_STORAGE_PRICES.get(storage_class_upper)
    if price is not None:
        return price

    # Default to STANDARD if unknown storage class
    logger.warning(f"Unknown storage class '{storage_class}', using STANDARD pricing")
    return DEFAULT_S3_STORAGE_PRICES["STANDARD"]


def calculate_storage_monthly_cost(
    size_bytes: int,
    storage_class: str = "STANDARD",
    region: str = "us-east-1",
) -> float:
    """
    Calculate the estimated monthly storage cost for S3 data.

    Args:
        size_bytes: Size of data in bytes
        storage_class: S3 storage class (e.g., 'STANDARD', 'GLACIER')
        region: AWS region code

    Returns:
        Estimated monthly cost in USD
    """
    size_gb = size_bytes / (1024 ** 3)  # Convert bytes to GB
    price_per_gb = get_storage_price_per_gb(storage_class, region)
    cost = size_gb * price_per_gb
    return round(cost, 2)


def calculate_bucket_monthly_cost(
    size_bytes: int,
    object_count: int = 0,
    storage_class: str = "STANDARD",
    region: str = "us-east-1",
) -> float:
    """
    Calculate the estimated monthly cost for an S3 bucket.

    This is a simplified calculation based on storage only.
    Request costs depend on actual usage patterns.

    Args:
        size_bytes: Total size of bucket in bytes
        object_count: Number of objects in the bucket (for reference, not used in cost)
        storage_class: Primary storage class of the bucket
        region: AWS region code

    Returns:
        Estimated monthly storage cost in USD
    """
    return calculate_storage_monthly_cost(size_bytes, storage_class, region)


def format_bytes(size_bytes: int) -> str:
    """
    Format bytes into a human-readable string.

    Args:
        size_bytes: Size in bytes

    Returns:
        Human-readable size string (e.g., '1.5 GB', '500 MB')
    """
    if size_bytes < 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    unit_index = 0
    size = float(size_bytes)

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.2f} {units[unit_index]}"


def get_storage_class_display_name(storage_class: str) -> str:
    """
    Get a display-friendly name for an S3 storage class.

    Args:
        storage_class: Storage class identifier from AWS

    Returns:
        Display-friendly storage class name
    """
    display_names = {
        "STANDARD": "S3 Standard",
        "INTELLIGENT_TIERING": "S3 Intelligent-Tiering",
        "STANDARD_IA": "S3 Standard-IA",
        "ONEZONE_IA": "S3 One Zone-IA",
        "GLACIER_IR": "S3 Glacier Instant Retrieval",
        "GLACIER": "S3 Glacier Flexible Retrieval",
        "DEEP_ARCHIVE": "S3 Glacier Deep Archive",
        "REDUCED_REDUNDANCY": "Reduced Redundancy (Legacy)",
    }
    storage_class_upper = storage_class.upper().replace("-", "_")
    return display_names.get(storage_class_upper, storage_class)
