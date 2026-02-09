# AWS Pricing Utilities

This directory contains utility modules for fetching AWS pricing information using the AWS Price List API.

## Modules

- **`aws_ebs_pricing.py`** - EBS volume pricing (storage, IOPS, throughput)
- **`aws_ec2_pricing.py`** - EC2 instance pricing (on-demand hourly rates)

## How It Works

These modules use a two-tier approach for pricing lookups:

1. **Primary**: AWS Price List API (free, real-time on-demand prices)
2. **Fallback**: Hardcoded default prices (US East N. Virginia, as of 2024)

The fallback ensures the scanners continue working even when the API is unavailable or returns unexpected data.

---

## AWS Price List API - Limitations and Considerations

### 1. API Availability

- The Price List API is **only available in `us-east-1` and `ap-south-1` regions**.
- If your application runs in other regions, it must make cross-region calls to fetch pricing data, which adds latency.

### 2. Response Complexity

- The API returns deeply nested JSON structures that are difficult to parse.
- Price extraction requires navigating through multiple levels of dictionaries.
- Response format may change without notice.

### 3. No Discount Information

The API only returns **on-demand (list) prices**. It does NOT include:

- Reserved Instance pricing
- Savings Plans discounts
- Enterprise Discount Program (EDP) pricing
- Any negotiated contract rates

**Actual costs may be significantly lower** if you have any of these discounts.

### 4. Rate Limits

- The API has rate limits (throttling) that may affect high-volume usage.
- Consider caching prices for extended periods (prices rarely change).
- Our implementation includes an in-memory cache to reduce API calls.

### 5. Region Code Mapping

- The API uses region codes (e.g., `us-east-1`) but some filters require location names (e.g., `US East (N. Virginia)`).
- This can cause confusion when constructing queries.

### 6. Data Freshness

- While prices are generally current, there may be delays in reflecting recent price changes.

### 7. No Historical Pricing

- The API only provides current prices, not historical pricing data.

### 8. Operating System Variations (EC2)

- EC2 prices vary by OS (Linux, Windows, RHEL, SLES, etc.).
- The EC2 pricing module defaults to Linux pricing.

---

## Alternative: AWS Cost Explorer API

For **actual cost tracking** (including discounts and real billing data), consider using the **AWS Cost Explorer API** instead.

**Trade-offs:**

| Feature | Price List API | Cost Explorer API |
|---------|----------------|-------------------|
| Cost | Free | ~$0.01 per request |
| Data | On-demand list prices | Actual billed costs |
| Discounts | Not included | Included |
| Time Range | Current only | Historical data |
| Use Case | Estimates | Real cost analysis |

---

## Default Prices

The fallback prices are based on **US East (N. Virginia)** region as of 2024. These are used when:

- The Price List API is unavailable
- The API returns no results for the requested resource
- An error occurs during the API call

### EBS Default Prices (per GB/month)

| Volume Type | Price |
|-------------|-------|
| standard (magnetic) | $0.05 |
| gp2 | $0.10 |
| gp3 | $0.08 |
| io1 / io2 | $0.125 |
| st1 | $0.045 |
| sc1 | $0.015 |

**Additional gp3 costs:**
- IOPS above 3,000: $0.005 per IOPS/month
- Throughput above 125 MB/s: $0.06 per MB/s/month

**Provisioned IOPS (io1/io2):**
- $0.065 per IOPS/month

### EC2 Default Prices (per hour, Linux)

See `aws_ec2_pricing.py` for the full list of supported instance types. Common examples:

| Instance Type | Price/Hour |
|---------------|------------|
| t3.micro | $0.0104 |
| t3.medium | $0.0416 |
| t3.large | $0.0832 |
| m5.large | $0.096 |
| m5.xlarge | $0.192 |
| c5.large | $0.085 |
| r5.large | $0.126 |

---

## Usage Examples

### EBS Pricing

```python
from src.utils.aws_ebs_pricing import calculate_ebs_monthly_cost, get_ebs_cost_per_gb

# Get price per GB for a volume type
price = get_ebs_cost_per_gb("gp3", "us-east-1", use_api=True)

# Calculate total monthly cost including IOPS and throughput
monthly_cost = calculate_ebs_monthly_cost(
    volume_type="gp3",
    size_gb=500,
    region="us-east-1",
    iops=5000,           # Optional: for io1/io2/gp3
    throughput_mbps=250,  # Optional: for gp3
    use_api=True,
)
```

### EC2 Pricing

```python
from src.utils.aws_ec2_pricing import calculate_ec2_monthly_cost, get_ec2_price_per_hour

# Get hourly price for an instance type
hourly_price = get_ec2_price_per_hour("m5.large", "us-east-1", use_api=True)

# Calculate monthly cost (assumes 730 hours/month)
monthly_cost = calculate_ec2_monthly_cost(
    instance_type="m5.large",
    region="us-east-1",
    operating_system="Linux",
    use_api=True,
)
```

---

## Caching

Both pricing modules use in-memory caching:

- **Instance-level cache**: Each `AWSPricingClient` / `AWSEC2PricingClient` instance maintains a cache of fetched prices.
- **Singleton pattern**: The `get_pricing_client()` functions use `@lru_cache` to return the same client instance, preserving the cache across calls.

For long-running applications or high-volume usage, consider:

1. Implementing a persistent cache (filesystem or Redis)
2. Setting a TTL (time-to-live) for cached prices
3. Pre-warming the cache at application startup