"""Azure VM pricing module using Azure Retail Prices API.

This module provides functions to fetch and cache Azure VM pricing data
from the public Azure Retail Prices API. Pricing varies by VM size, region,
and OS type (Linux vs Windows).

API Reference: https://prices.azure.com/api/retail/prices
Documentation: docs/azure_pricing.md
"""
from typing import Optional
from datetime import datetime, timezone, timedelta
import logging

# Third-party
import requests

# Internal
from dfo.core.config import get_settings
from dfo.db.duck import DuckDBManager
from dfo.analyze.compute_mapper import resolve_equivalent_sku

logger = logging.getLogger(__name__)


def fetch_vm_price(
    vm_size: str,
    region: str,
    os_type: str = "Linux"
) -> Optional[float]:
    """Fetch VM retail price from Azure Retail Prices API.

    Uses Azure public API: https://prices.azure.com/api/retail/prices
    No authentication required.

    Args:
        vm_size: ARM SKU name (e.g., "Standard_D2s_v3")
        region: Azure region (e.g., "eastus")
        os_type: Operating system type ("Linux" or "Windows")

    Returns:
        Hourly price in USD, or None if not found

    API Query:
        serviceName eq 'Virtual Machines'
        and armRegionName eq '<region>'
        and armSkuName eq '<vm_size>'
        and priceType eq 'Consumption'
        and (productName contains 'Linux' or productName contains 'Windows')
    """
    settings = get_settings()
    base_url = settings.dfo_azure_pricing_api_url

    # Build OData filter for Azure Retail Prices API
    # Note: We don't filter by OS type in the query because 'contains' operator
    # causes 400 errors. Instead, we filter results after fetching.
    filter_query = (
        f"serviceName eq 'Virtual Machines' "
        f"and armRegionName eq '{region}' "
        f"and armSkuName eq '{vm_size}' "
        f"and priceType eq 'Consumption'"
    )

    params = {
        "$filter": filter_query,
        "api-version": "2023-01-01-preview"
    }

    try:
        logger.debug(f"Fetching price for {vm_size} in {region} ({os_type})")

        # Handle pagination (API returns up to ~1000 records per page)
        url = base_url
        all_items = []

        while url:
            response = requests.get(
                url,
                params=params if url == base_url else None,
                timeout=10
            )
            response.raise_for_status()

            data = response.json()
            items = data.get("Items", [])
            all_items.extend(items)

            # Check for next page
            url = data.get("NextPageLink")

        if not all_items:
            logger.warning(f"No pricing data found for {vm_size} in {region} ({os_type})")
            return None

        # Filter by OS type in product name
        # Product names include OS type (e.g., "Virtual Machines Dv3 Series Windows")
        os_matched_items = [
            item for item in all_items
            if os_type.lower() in item.get("productName", "").lower()
        ]

        # If no OS-specific match, use first item (often Linux or base price)
        if not os_matched_items:
            logger.debug(
                f"No {os_type}-specific pricing found for {vm_size}, "
                f"using first available price"
            )
            os_matched_items = all_items

        # Return the first matching price
        first_item = os_matched_items[0]
        hourly_price = first_item.get("retailPrice")
        currency = first_item.get("currencyCode", "USD")

        if hourly_price is None:
            logger.warning(f"retailPrice is None for {vm_size}")
            return None

        logger.info(
            f"Found price for {vm_size} in {region} ({os_type}): "
            f"{hourly_price} {currency}/hour"
        )

        return float(hourly_price)

    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed for {vm_size}: {e}")
        return None
    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"Failed to parse pricing response: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching price for {vm_size}: {e}")
        return None


def get_vm_monthly_cost_with_metadata(
    vm_size: str,
    region: str,
    os_type: str = "Linux",
    use_cache: bool = True
) -> dict:
    """Get estimated monthly cost with SKU equivalence metadata.

    Args:
        vm_size: VM size/SKU (e.g., "Standard_B1s")
        region: Azure region (e.g., "eastus")
        os_type: Operating system ("Linux" or "Windows")
        use_cache: Check cache first (default: True)

    Returns:
        Dict with:
            - monthly_cost: float (estimated monthly cost in USD)
            - equivalent_sku: str or None (if legacy SKU was resolved)
            - hourly_price: float (hourly rate used)

    Example:
        >>> result = get_vm_monthly_cost_with_metadata("Standard_B1s", "eastus")
        >>> result
        {
            "monthly_cost": 6.07,
            "equivalent_sku": "Standard_B2ls_v2",
            "hourly_price": 0.00832
        }
    """
    settings = get_settings()

    # Normalize os_type
    os_type = os_type or "Linux"
    if os_type not in ["Linux", "Windows"]:
        logger.warning(f"Unknown os_type '{os_type}', defaulting to Linux")
        os_type = "Linux"

    hourly_price = None
    equivalent_sku = None

    # Step 0: Check if this SKU has a known equivalent (even if cached)
    # This ensures we always track equivalence for legacy SKUs
    equivalent_sku = resolve_equivalent_sku(vm_size)
    if equivalent_sku:
        logger.debug(f"Legacy SKU detected: {vm_size} → {equivalent_sku}")

    # Step 1: Check cache if enabled
    if use_cache:
        hourly_price = _get_cached_price(vm_size, region, os_type)
        if hourly_price is not None:
            logger.debug(f"Cache hit for {vm_size} in {region} ({os_type})")

    # Step 2: Fetch from API if not in cache
    if hourly_price is None:
        hourly_price = fetch_vm_price(vm_size, region, os_type)

        # Step 3: If not found, try equivalent SKU (for legacy VMs)
        if hourly_price is None and equivalent_sku:
            logger.info(
                f"SKU {vm_size} not found in pricing API, "
                f"trying equivalent: {equivalent_sku}"
            )
            hourly_price = fetch_vm_price(equivalent_sku, region, os_type)

            if hourly_price is not None:
                logger.info(
                    f"Using equivalent SKU pricing: {vm_size} → {equivalent_sku}"
                )

        # Step 4: Cache the result (using original SKU as key)
        if hourly_price is not None:
            _cache_price(vm_size, region, os_type, hourly_price)

    # Step 5: Calculate monthly cost
    if hourly_price is None:
        logger.warning(
            f"Could not determine pricing for {vm_size} in {region} ({os_type}), "
            f"returning 0.0"
        )
        return {
            "monthly_cost": 0.0,
            "equivalent_sku": equivalent_sku,
            "hourly_price": 0.0
        }

    # Monthly cost: hourly_rate * 730 hours/month (standard calculation)
    monthly_cost = hourly_price * 730

    logger.debug(
        f"Monthly cost for {vm_size} in {region} ({os_type}): ${monthly_cost:.2f}"
        + (f" (using equivalent: {equivalent_sku})" if equivalent_sku else "")
    )

    return {
        "monthly_cost": monthly_cost,
        "equivalent_sku": equivalent_sku,
        "hourly_price": hourly_price
    }


def get_vm_monthly_cost(
    vm_size: str,
    region: str,
    os_type: str = "Linux",
    use_cache: bool = True
) -> float:
    """Get estimated monthly cost for a VM.

    Args:
        vm_size: VM size/SKU (e.g., "Standard_B1s")
        region: Azure region (e.g., "eastus")
        os_type: Operating system ("Linux" or "Windows")
        use_cache: Check cache first (default: True)

    Returns:
        Estimated monthly cost in USD (hourly_rate * 730 hours)
        Returns 0.0 if pricing not found (with warning log)

    Note:
        This function wraps get_vm_monthly_cost_with_metadata() for backwards
        compatibility. Use get_vm_monthly_cost_with_metadata() if you need
        to know whether an equivalent SKU was used.
    """
    result = get_vm_monthly_cost_with_metadata(vm_size, region, os_type, use_cache)
    return result["monthly_cost"]


def _get_cached_price(
    vm_size: str,
    region: str,
    os_type: str
) -> Optional[float]:
    """Get price from cache if not expired.

    Args:
        vm_size: VM size/SKU
        region: Azure region
        os_type: Operating system

    Returns:
        Cached hourly price, or None if not found or expired
    """
    settings = get_settings()
    db = DuckDBManager()

    # Calculate expiration threshold
    ttl_days = settings.dfo_pricing_cache_ttl_days
    expiration_date = datetime.now(timezone.utc) - timedelta(days=ttl_days)

    try:
        rows = db.query(
            """
            SELECT hourly_price, fetched_at
            FROM vm_pricing_cache
            WHERE vm_size = ?
              AND region = ?
              AND os_type = ?
              AND fetched_at > ?
            """,
            (vm_size, region, os_type, expiration_date)
        )

        if rows:
            hourly_price = rows[0][0]
            return float(hourly_price) if hourly_price is not None else None

        return None

    except Exception as e:
        logger.error(f"Failed to read from pricing cache: {e}")
        return None


def _cache_price(
    vm_size: str,
    region: str,
    os_type: str,
    hourly_price: float,
    currency: str = "USD"
) -> None:
    """Store price in cache with timestamp.

    Args:
        vm_size: VM size/SKU
        region: Azure region
        os_type: Operating system
        hourly_price: Hourly price in USD
        currency: Currency code (default: USD)
    """
    db = DuckDBManager()

    try:
        # Insert or replace (upsert)
        db.execute_query(
            """
            INSERT OR REPLACE INTO vm_pricing_cache
            (vm_size, region, os_type, hourly_price, currency, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                vm_size,
                region,
                os_type,
                hourly_price,
                currency,
                datetime.now(timezone.utc)
            )
        )

        logger.debug(f"Cached price for {vm_size} in {region} ({os_type})")

    except Exception as e:
        logger.error(f"Failed to cache price: {e}")


def refresh_pricing_cache(force: bool = False) -> int:
    """Refresh prices in cache.

    Args:
        force: Refresh even if not expired (default: False)

    Returns:
        Number of prices refreshed

    Note:
        This function refreshes all cached prices by re-fetching from the API.
        Use sparingly to avoid rate limiting.
    """
    db = DuckDBManager()
    settings = get_settings()

    # Get all cached entries
    if force:
        query = "SELECT vm_size, region, os_type FROM vm_pricing_cache"
        rows = db.query(query)
    else:
        # Only refresh expired entries
        ttl_days = settings.dfo_pricing_cache_ttl_days
        expiration_date = datetime.now(timezone.utc) - timedelta(days=ttl_days)

        query = """
            SELECT vm_size, region, os_type
            FROM vm_pricing_cache
            WHERE fetched_at <= ?
        """
        rows = db.query(query, (expiration_date,))

    refreshed_count = 0

    for row in rows:
        vm_size, region, os_type = row

        # Fetch new price
        hourly_price = fetch_vm_price(vm_size, region, os_type)

        if hourly_price is not None:
            _cache_price(vm_size, region, os_type, hourly_price)
            refreshed_count += 1

    logger.info(f"Refreshed {refreshed_count} pricing entries")

    return refreshed_count


def clear_pricing_cache() -> None:
    """Clear all pricing cache entries.

    Useful for testing or when prices need to be re-fetched from scratch.
    """
    db = DuckDBManager()

    try:
        db.execute_query("DELETE FROM vm_pricing_cache")
        logger.info("Pricing cache cleared")
    except Exception as e:
        logger.error(f"Failed to clear pricing cache: {e}")
