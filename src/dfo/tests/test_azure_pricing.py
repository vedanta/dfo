"""Tests for Azure VM pricing module."""
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
import pytest

# Internal
from dfo.providers.azure.pricing import (
    fetch_vm_price,
    get_vm_monthly_cost,
    _get_cached_price,
    _cache_price,
    refresh_pricing_cache,
    clear_pricing_cache
)


@pytest.fixture
def mock_pricing_response():
    """Mock Azure Retail Prices API response."""
    return {
        "Items": [
            {
                "retailPrice": 0.0416,
                "unitPrice": 0.0416,
                "currencyCode": "USD",
                "armRegionName": "eastus",
                "armSkuName": "Standard_B1s",
                "productName": "Virtual Machines BS Series Linux",
                "unitOfMeasure": "1 Hour"
            }
        ],
        "NextPageLink": None
    }


@pytest.fixture
def mock_windows_pricing_response():
    """Mock Azure Retail Prices API response for Windows VM."""
    return {
        "Items": [
            {
                "retailPrice": 0.0591,
                "unitPrice": 0.0591,
                "currencyCode": "USD",
                "armRegionName": "eastus",
                "armSkuName": "Standard_B1s",
                "productName": "Virtual Machines BS Series Windows",
                "unitOfMeasure": "1 Hour"
            }
        ],
        "NextPageLink": None
    }


def test_fetch_vm_price_success(mock_pricing_response):
    """Test successful price fetch from API."""
    with patch('dfo.providers.azure.pricing.requests.get') as mock_get:
        mock_get.return_value.json.return_value = mock_pricing_response
        mock_get.return_value.raise_for_status = Mock()

        price = fetch_vm_price("Standard_B1s", "eastus", "Linux")

        assert price == 0.0416
        assert mock_get.called


def test_fetch_vm_price_windows(mock_windows_pricing_response):
    """Test price fetch for Windows VM (higher cost)."""
    with patch('dfo.providers.azure.pricing.requests.get') as mock_get:
        mock_get.return_value.json.return_value = mock_windows_pricing_response
        mock_get.return_value.raise_for_status = Mock()

        price = fetch_vm_price("Standard_B1s", "eastus", "Windows")

        assert price == 0.0591
        assert price > 0.0416  # Windows is more expensive than Linux


def test_fetch_vm_price_not_found():
    """Test price fetch when VM size not found."""
    with patch('dfo.providers.azure.pricing.requests.get') as mock_get:
        mock_get.return_value.json.return_value = {"Items": [], "NextPageLink": None}
        mock_get.return_value.raise_for_status = Mock()

        price = fetch_vm_price("Unknown_Size", "eastus", "Linux")

        assert price is None


def test_fetch_vm_price_api_error():
    """Test price fetch when API returns error."""
    with patch('dfo.providers.azure.pricing.requests.get') as mock_get:
        mock_get.side_effect = Exception("API Error")

        price = fetch_vm_price("Standard_B1s", "eastus", "Linux")

        assert price is None


def test_fetch_vm_price_pagination(mock_pricing_response):
    """Test price fetch with paginated API response."""
    # First page has NextPageLink, second page is final
    page1 = {"Items": [], "NextPageLink": "https://example.com/page2"}
    page2 = mock_pricing_response

    with patch('dfo.providers.azure.pricing.requests.get') as mock_get:
        mock_get.side_effect = [
            Mock(json=lambda: page1, raise_for_status=Mock()),
            Mock(json=lambda: page2, raise_for_status=Mock())
        ]

        price = fetch_vm_price("Standard_B1s", "eastus", "Linux")

        assert price == 0.0416
        assert mock_get.call_count == 2


def test_get_vm_monthly_cost_calculation(mock_pricing_response):
    """Test monthly cost calculation (hourly * 730)."""
    with patch('dfo.providers.azure.pricing.requests.get') as mock_get:
        mock_get.return_value.json.return_value = mock_pricing_response
        mock_get.return_value.raise_for_status = Mock()

        with patch('dfo.providers.azure.pricing._get_cached_price', return_value=None):
            with patch('dfo.providers.azure.pricing._cache_price'):
                monthly_cost = get_vm_monthly_cost("Standard_B1s", "eastus", "Linux", use_cache=False)

                expected = 0.0416 * 730  # $30.37/month
                assert abs(monthly_cost - expected) < 0.01


def test_get_vm_monthly_cost_with_cache_hit():
    """Test monthly cost retrieval from cache."""
    with patch('dfo.providers.azure.pricing._get_cached_price', return_value=0.0416):
        with patch('dfo.providers.azure.pricing.fetch_vm_price') as mock_fetch:
            monthly_cost = get_vm_monthly_cost("Standard_B1s", "eastus", "Linux")

            # Should use cache, not call API
            assert not mock_fetch.called
            expected = 0.0416 * 730
            assert abs(monthly_cost - expected) < 0.01


def test_get_vm_monthly_cost_cache_miss(mock_pricing_response):
    """Test monthly cost when cache miss occurs."""
    with patch('dfo.providers.azure.pricing._get_cached_price', return_value=None):
        with patch('dfo.providers.azure.pricing.requests.get') as mock_get:
            mock_get.return_value.json.return_value = mock_pricing_response
            mock_get.return_value.raise_for_status = Mock()

            with patch('dfo.providers.azure.pricing._cache_price') as mock_cache:
                monthly_cost = get_vm_monthly_cost("Standard_B1s", "eastus", "Linux")

                # Should fetch from API and cache result
                assert mock_get.called
                assert mock_cache.called
                assert monthly_cost > 0


def test_get_vm_monthly_cost_not_found():
    """Test monthly cost when pricing not found."""
    with patch('dfo.providers.azure.pricing._get_cached_price', return_value=None):
        with patch('dfo.providers.azure.pricing.fetch_vm_price', return_value=None):
            monthly_cost = get_vm_monthly_cost("Unknown_Size", "eastus", "Linux", use_cache=False)

            assert monthly_cost == 0.0


def test_get_vm_monthly_cost_unknown_os_type():
    """Test monthly cost with unknown OS type defaults to Linux."""
    with patch('dfo.providers.azure.pricing._get_cached_price', return_value=0.0416):
        monthly_cost = get_vm_monthly_cost("Standard_B1s", "eastus", "UnknownOS")

        # Should default to Linux and still work
        assert monthly_cost > 0


def test_cache_price(test_db):
    """Test caching price to database."""
    from dfo.db.duck import DuckDBManager

    db = DuckDBManager()

    _cache_price("Standard_B1s", "eastus", "Linux", 0.0416, "USD")

    # Verify cached
    rows = db.query(
        "SELECT hourly_price, currency FROM vm_pricing_cache WHERE vm_size = ?",
        ("Standard_B1s",)
    )

    assert len(rows) == 1
    assert rows[0][0] == 0.0416
    assert rows[0][1] == "USD"


def test_get_cached_price_found(test_db):
    """Test retrieving valid cached price."""
    from dfo.db.duck import DuckDBManager

    db = DuckDBManager()

    # Insert recent cache entry
    db.execute_query(
        """
        INSERT INTO vm_pricing_cache
        (vm_size, region, os_type, hourly_price, currency, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("Standard_B1s", "eastus", "Linux", 0.0416, "USD", datetime.now(timezone.utc))
    )

    price = _get_cached_price("Standard_B1s", "eastus", "Linux")

    assert price == 0.0416


def test_get_cached_price_expired(test_db):
    """Test that expired cache entries are not returned."""
    from dfo.db.duck import DuckDBManager

    db = DuckDBManager()

    # Insert expired cache entry (8 days old, TTL is 7)
    expired_date = datetime.now(timezone.utc) - timedelta(days=8)
    db.execute_query(
        """
        INSERT INTO vm_pricing_cache
        (vm_size, region, os_type, hourly_price, currency, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("Standard_B1s", "eastus", "Linux", 0.0416, "USD", expired_date)
    )

    price = _get_cached_price("Standard_B1s", "eastus", "Linux")

    assert price is None


def test_get_cached_price_not_found(test_db):
    """Test retrieving non-existent cached price."""
    price = _get_cached_price("NonExistent_Size", "eastus", "Linux")

    assert price is None


def test_refresh_pricing_cache(test_db, mock_pricing_response):
    """Test refreshing expired cache entries."""
    from dfo.db.duck import DuckDBManager

    db = DuckDBManager()

    # Insert expired entry
    expired_date = datetime.now(timezone.utc) - timedelta(days=8)
    db.execute_query(
        """
        INSERT INTO vm_pricing_cache
        (vm_size, region, os_type, hourly_price, currency, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("Standard_B1s", "eastus", "Linux", 0.0999, "USD", expired_date)
    )

    with patch('dfo.providers.azure.pricing.fetch_vm_price', return_value=0.0416):
        count = refresh_pricing_cache()

        assert count == 1

        # Verify price was updated
        rows = db.query(
            "SELECT hourly_price FROM vm_pricing_cache WHERE vm_size = ?",
            ("Standard_B1s",)
        )
        assert rows[0][0] == 0.0416


def test_refresh_pricing_cache_force(test_db):
    """Test force refresh of all cache entries."""
    from dfo.db.duck import DuckDBManager

    db = DuckDBManager()

    # Insert recent entry (not expired)
    db.execute_query(
        """
        INSERT INTO vm_pricing_cache
        (vm_size, region, os_type, hourly_price, currency, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("Standard_B1s", "eastus", "Linux", 0.0999, "USD", datetime.now(timezone.utc))
    )

    with patch('dfo.providers.azure.pricing.fetch_vm_price', return_value=0.0416):
        count = refresh_pricing_cache(force=True)

        # Should refresh even though not expired
        assert count == 1


def test_clear_pricing_cache(test_db):
    """Test clearing all cache entries."""
    from dfo.db.duck import DuckDBManager

    db = DuckDBManager()

    # Insert some entries
    db.execute_query(
        """
        INSERT INTO vm_pricing_cache
        (vm_size, region, os_type, hourly_price, currency, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("Standard_B1s", "eastus", "Linux", 0.0416, "USD", datetime.now(timezone.utc))
    )

    clear_pricing_cache()

    # Verify empty
    rows = db.query("SELECT COUNT(*) FROM vm_pricing_cache")
    assert rows[0][0] == 0


def test_different_regions_different_prices(test_db):
    """Test that prices can vary by region."""
    from dfo.db.duck import DuckDBManager

    db = DuckDBManager()

    # Cache different prices for different regions
    _cache_price("Standard_B1s", "eastus", "Linux", 0.0416, "USD")
    _cache_price("Standard_B1s", "westeurope", "Linux", 0.0500, "USD")

    price_east = _get_cached_price("Standard_B1s", "eastus", "Linux")
    price_west = _get_cached_price("Standard_B1s", "westeurope", "Linux")

    assert price_east == 0.0416
    assert price_west == 0.0500
    assert price_east != price_west


def test_linux_vs_windows_pricing(test_db):
    """Test that Linux and Windows have different prices."""
    # Cache prices for both OS types
    _cache_price("Standard_B1s", "eastus", "Linux", 0.0416, "USD")
    _cache_price("Standard_B1s", "eastus", "Windows", 0.0591, "USD")

    linux_price = _get_cached_price("Standard_B1s", "eastus", "Linux")
    windows_price = _get_cached_price("Standard_B1s", "eastus", "Windows")

    assert linux_price == 0.0416
    assert windows_price == 0.0591
    assert windows_price > linux_price  # Windows is more expensive
