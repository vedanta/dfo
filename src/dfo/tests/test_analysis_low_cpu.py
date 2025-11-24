"""Tests for low-CPU analysis module."""
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import json

# Third-party
import pytest

# Internal
from dfo.analyze.low_cpu import (
    analyze_low_cpu_vms,
    _analyze_vm_cpu_for_rightsizing,
    _recommend_smaller_sku,
    _parse_sku,
    _determine_severity,
    get_low_cpu_vms,
    get_low_cpu_summary
)
from dfo.db.duck import get_db, reset_db
from dfo.core.config import reset_settings


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Create a test database."""
    db_file = tmp_path / "test.duckdb"
    monkeypatch.setenv("DFO_DUCKDB_FILE", str(db_file))
    monkeypatch.setenv("AZURE_TENANT_ID", "test")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test")

    # Reset singletons
    reset_settings()
    reset_db()

    db = get_db()
    db.initialize_schema()

    yield db

    db.close()
    reset_db()
    reset_settings()


def test_analyze_low_cpu_vms_success(test_db):
    """Test successful low-CPU analysis."""
    # Insert test VM with low CPU metrics
    test_db.execute_query(
        """
        INSERT INTO vm_inventory
        (vm_id, name, resource_group, location, size, power_state, os_type,
         priority, tags, cpu_timeseries, discovered_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "/subscriptions/test/vm1",
            "test-vm-1",
            "rg1",
            "eastus",
            "Standard_D4s_v5",
            "running",
            "Linux",
            "Regular",
            "{}",
            json.dumps([
                {"timestamp": f"2024-01-{i:02d}T12:00:00Z", "average": 15.0}
                for i in range(1, 16)  # 15 days of 15% CPU
            ]),
            datetime.now(timezone.utc)
        )
    )

    # Mock pricing calls
    with patch('dfo.analyze.low_cpu.get_vm_monthly_cost_with_metadata') as mock_pricing:
        def pricing_side_effect(vm_size, region, os_type, use_cache):
            if vm_size == "Standard_D4s_v5":
                return {"monthly_cost": 140.16, "equivalent_sku": None}
            elif vm_size == "Standard_D2s_v5":
                return {"monthly_cost": 70.08, "equivalent_sku": None}
            return {"monthly_cost": 0, "equivalent_sku": None}

        mock_pricing.side_effect = pricing_side_effect

        # Run analysis
        count = analyze_low_cpu_vms(threshold=20.0, min_days=14)

        assert count == 1

    # Verify analysis stored
    results = test_db.query("SELECT * FROM vm_low_cpu_analysis")
    assert len(results) == 1

    result = results[0]
    assert result[0] == "/subscriptions/test/vm1"  # vm_id
    assert result[1] == 15.0  # cpu_avg
    assert result[2] == 15  # days_under_threshold
    assert result[3] == "Standard_D4s_v5"  # current_sku
    assert result[4] == "Standard_D2s_v5"  # recommended_sku
    assert result[5] == 140.16  # current_monthly_cost
    assert result[6] == 70.08  # recommended_monthly_cost
    assert result[7] == 70.08  # estimated_monthly_savings
    assert result[8] == 50.0  # savings_percentage
    assert result[9] == "Medium"  # severity


def test_analyze_low_cpu_vms_no_candidates(test_db):
    """Test analysis with no low-CPU VMs."""
    # Insert VM with high CPU
    test_db.execute_query(
        """
        INSERT INTO vm_inventory
        (vm_id, name, resource_group, location, size, power_state, os_type,
         priority, tags, cpu_timeseries, discovered_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "/subscriptions/test/vm1",
            "test-vm-1",
            "rg1",
            "eastus",
            "Standard_D4s_v5",
            "running",
            "Linux",
            "Regular",
            "{}",
            json.dumps([
                {"timestamp": f"2024-01-{i:02d}T12:00:00Z", "average": 60.0}
                for i in range(1, 16)  # 15 days of 60% CPU
            ]),
            datetime.now(timezone.utc)
        )
    )

    # Run analysis
    count = analyze_low_cpu_vms(threshold=20.0, min_days=14)

    assert count == 0

    # Verify no results stored
    results = test_db.query("SELECT * FROM vm_low_cpu_analysis")
    assert len(results) == 0


def test_analyze_low_cpu_vms_no_cpu_metrics(test_db):
    """Test analysis skips VMs without CPU metrics."""
    test_db.execute_query(
        """
        INSERT INTO vm_inventory
        (vm_id, name, resource_group, location, size, power_state, os_type,
         priority, tags, cpu_timeseries, discovered_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "/subscriptions/test/vm1",
            "test-vm-1",
            "rg1",
            "eastus",
            "Standard_D4s_v5",
            "running",
            "Linux",
            "Regular",
            "{}",
            None,  # No CPU metrics
            datetime.now(timezone.utc)
        )
    )

    count = analyze_low_cpu_vms(threshold=20.0, min_days=14)

    assert count == 0


def test_analyze_low_cpu_vms_insufficient_days(test_db):
    """Test analysis requires minimum days of data."""
    # Insert VM with only 5 days of data (need 14)
    test_db.execute_query(
        """
        INSERT INTO vm_inventory
        (vm_id, name, resource_group, location, size, power_state, os_type,
         priority, tags, cpu_timeseries, discovered_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "/subscriptions/test/vm1",
            "test-vm-1",
            "rg1",
            "eastus",
            "Standard_D4s_v5",
            "running",
            "Linux",
            "Regular",
            "{}",
            json.dumps([
                {"timestamp": f"2024-01-{i:02d}T12:00:00Z", "average": 15.0}
                for i in range(1, 6)  # Only 5 days
            ]),
            datetime.now(timezone.utc)
        )
    )

    count = analyze_low_cpu_vms(threshold=20.0, min_days=14)

    assert count == 0


def test_analyze_vm_cpu_for_rightsizing_candidate(test_db):
    """Test VM CPU analysis identifies right-sizing candidate."""
    cpu_timeseries = [
        {"timestamp": f"2024-01-{i:02d}T12:00:00Z", "average": 15.0}
        for i in range(1, 16)  # 15 days of 15% CPU
    ]

    result = _analyze_vm_cpu_for_rightsizing(
        vm_id="/subscriptions/test/vm1",
        name="test-vm",
        cpu_timeseries=cpu_timeseries,
        threshold=20.0,
        min_days=14
    )

    assert result is not None
    assert result["cpu_avg"] == 15.0
    assert result["days_under_threshold"] == 15
    assert result["total_days"] == 15


def test_analyze_vm_cpu_for_rightsizing_not_candidate(test_db):
    """Test VM with high CPU is not a candidate."""
    cpu_timeseries = [
        {"timestamp": f"2024-01-{i:02d}T12:00:00Z", "average": 60.0}
        for i in range(1, 16)  # 15 days of 60% CPU
    ]

    result = _analyze_vm_cpu_for_rightsizing(
        vm_id="/subscriptions/test/vm1",
        name="test-vm",
        cpu_timeseries=cpu_timeseries,
        threshold=20.0,
        min_days=14
    )

    assert result is None


def test_analyze_vm_cpu_for_rightsizing_empty_timeseries(test_db):
    """Test empty CPU timeseries returns None."""
    result = _analyze_vm_cpu_for_rightsizing(
        vm_id="/subscriptions/test/vm1",
        name="test-vm",
        cpu_timeseries=[],
        threshold=20.0,
        min_days=14
    )

    assert result is None


def test_analyze_vm_cpu_for_rightsizing_insufficient_days(test_db):
    """Test insufficient days returns None."""
    cpu_timeseries = [
        {"timestamp": f"2024-01-{i:02d}T12:00:00Z", "average": 15.0}
        for i in range(1, 6)  # Only 5 days
    ]

    result = _analyze_vm_cpu_for_rightsizing(
        vm_id="/subscriptions/test/vm1",
        name="test-vm",
        cpu_timeseries=cpu_timeseries,
        threshold=20.0,
        min_days=14
    )

    assert result is None


def test_recommend_smaller_sku_d_series():
    """Test SKU recommendation for D-series."""
    assert _recommend_smaller_sku("Standard_D4s_v5") == "Standard_D2s_v5"
    assert _recommend_smaller_sku("Standard_D8s_v5") == "Standard_D4s_v5"
    assert _recommend_smaller_sku("Standard_D16s_v5") == "Standard_D8s_v5"
    assert _recommend_smaller_sku("Standard_D32s_v5") == "Standard_D16s_v5"


def test_recommend_smaller_sku_e_series():
    """Test SKU recommendation for E-series."""
    assert _recommend_smaller_sku("Standard_E4s_v5") == "Standard_E2s_v5"
    assert _recommend_smaller_sku("Standard_E8s_v5") == "Standard_E4s_v5"
    assert _recommend_smaller_sku("Standard_E16s_v5") == "Standard_E8s_v5"


def test_recommend_smaller_sku_b_series():
    """Test SKU recommendation for B-series."""
    assert _recommend_smaller_sku("Standard_B2s") == "Standard_B1s"
    assert _recommend_smaller_sku("Standard_B4ms") == "Standard_B2ms"


def test_recommend_smaller_sku_minimum_size():
    """Test SKU at minimum size cannot be downsized."""
    assert _recommend_smaller_sku("Standard_D2s_v5") is None
    assert _recommend_smaller_sku("Standard_E2s_v5") is None


def test_recommend_smaller_sku_with_modifiers():
    """Test SKU recommendation preserves modifiers."""
    assert _recommend_smaller_sku("Standard_D4ds_v5") == "Standard_D2ds_v5"
    assert _recommend_smaller_sku("Standard_E8as_v5") == "Standard_E4as_v5"


def test_recommend_smaller_sku_old_generation():
    """Test SKU recommendation for older generations."""
    assert _recommend_smaller_sku("Standard_D4s_v3") == "Standard_D2s_v3"
    assert _recommend_smaller_sku("Standard_E8s_v4") == "Standard_E4s_v4"


def test_recommend_smaller_sku_invalid():
    """Test invalid SKU returns None."""
    assert _recommend_smaller_sku("InvalidSKU") is None
    assert _recommend_smaller_sku("") is None


def test_parse_sku_d_series():
    """Test parsing D-series SKU."""
    result = _parse_sku("Standard_D4s_v5")
    assert result["series"] == "D"
    assert result["size"] == 4
    assert result["modifiers"] == "s"
    assert result["generation"] == "5"


def test_parse_sku_e_series():
    """Test parsing E-series SKU."""
    result = _parse_sku("Standard_E8ds_v4")
    assert result["series"] == "E"
    assert result["size"] == 8
    assert result["modifiers"] == "ds"
    assert result["generation"] == "4"


def test_parse_sku_b_series_no_generation():
    """Test parsing B-series SKU without generation."""
    result = _parse_sku("Standard_B2ms")
    assert result["series"] == "B"
    assert result["size"] == 2
    assert result["modifiers"] == "ms"
    assert result["generation"] is None


def test_parse_sku_no_modifiers():
    """Test parsing SKU without modifiers."""
    result = _parse_sku("Standard_D4_v3")
    assert result["series"] == "D"
    assert result["size"] == 4
    assert result["modifiers"] == ""
    assert result["generation"] == "3"


def test_parse_sku_invalid():
    """Test parsing invalid SKU."""
    assert _parse_sku("InvalidSKU") is None
    assert _parse_sku("") is None
    assert _parse_sku("Standard_") is None


def test_determine_severity_critical():
    """Test severity determination for critical savings."""
    assert _determine_severity(500.0) == "Critical"
    assert _determine_severity(1000.0) == "Critical"


def test_determine_severity_high():
    """Test severity determination for high savings."""
    assert _determine_severity(200.0) == "High"
    assert _determine_severity(499.99) == "High"


def test_determine_severity_medium():
    """Test severity determination for medium savings."""
    assert _determine_severity(50.0) == "Medium"
    assert _determine_severity(199.99) == "Medium"


def test_determine_severity_low():
    """Test severity determination for low savings."""
    assert _determine_severity(0.0) == "Low"
    assert _determine_severity(49.99) == "Low"


def test_get_low_cpu_vms(test_db):
    """Test retrieving low-CPU VMs."""
    # Insert test data
    test_db.execute_query(
        """
        INSERT INTO vm_inventory
        (vm_id, name, resource_group, location, size, power_state, os_type,
         priority, tags, cpu_timeseries, discovered_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "/subscriptions/test/vm1",
            "test-vm-1",
            "rg1",
            "eastus",
            "Standard_D4s_v5",
            "running",
            "Linux",
            "Regular",
            "{}",
            "[]",
            datetime.now(timezone.utc)
        )
    )

    test_db.execute_query(
        """
        INSERT INTO vm_low_cpu_analysis
        (vm_id, cpu_avg, days_under_threshold, current_sku, recommended_sku,
         current_monthly_cost, recommended_monthly_cost,
         estimated_monthly_savings, savings_percentage, severity, analyzed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "/subscriptions/test/vm1",
            15.0,
            15,
            "Standard_D4s_v5",
            "Standard_D2s_v5",
            140.16,
            70.08,
            70.08,
            50.0,
            "Medium",
            datetime.now(timezone.utc)
        )
    )

    results = get_low_cpu_vms()
    assert len(results) == 1
    assert results[0]["name"] == "test-vm-1"
    assert results[0]["cpu_avg"] == 15.0
    assert results[0]["current_sku"] == "Standard_D4s_v5"
    assert results[0]["recommended_sku"] == "Standard_D2s_v5"


def test_get_low_cpu_vms_filter_by_severity(test_db):
    """Test retrieving low-CPU VMs filtered by severity."""
    # Insert test data with different severities
    test_db.execute_query(
        """
        INSERT INTO vm_inventory
        (vm_id, name, resource_group, location, size, power_state, os_type,
         priority, tags, cpu_timeseries, discovered_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "/subscriptions/test/vm1",
            "test-vm-1",
            "rg1",
            "eastus",
            "Standard_D4s_v5",
            "running",
            "Linux",
            "Regular",
            "{}",
            "[]",
            datetime.now(timezone.utc)
        )
    )

    test_db.execute_query(
        """
        INSERT INTO vm_low_cpu_analysis
        (vm_id, cpu_avg, days_under_threshold, current_sku, recommended_sku,
         current_monthly_cost, recommended_monthly_cost,
         estimated_monthly_savings, savings_percentage, severity, analyzed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "/subscriptions/test/vm1",
            15.0,
            15,
            "Standard_D4s_v5",
            "Standard_D2s_v5",
            140.16,
            70.08,
            70.08,
            50.0,
            "Medium",
            datetime.now(timezone.utc)
        )
    )

    # Filter by Medium severity
    results = get_low_cpu_vms(severity="Medium")
    assert len(results) == 1

    # Filter by High severity (should return nothing)
    results = get_low_cpu_vms(severity="High")
    assert len(results) == 0


def test_get_low_cpu_vms_with_limit(test_db):
    """Test retrieving low-CPU VMs with limit."""
    # Insert 2 VMs
    for i in range(1, 3):
        test_db.execute_query(
            """
            INSERT INTO vm_inventory
            (vm_id, name, resource_group, location, size, power_state, os_type,
             priority, tags, cpu_timeseries, discovered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"/subscriptions/test/vm{i}",
                f"test-vm-{i}",
                "rg1",
                "eastus",
                "Standard_D4s_v5",
                "running",
                "Linux",
                "Regular",
                "{}",
                "[]",
                datetime.now(timezone.utc)
            )
        )

        test_db.execute_query(
            """
            INSERT INTO vm_low_cpu_analysis
            (vm_id, cpu_avg, days_under_threshold, current_sku, recommended_sku,
             current_monthly_cost, recommended_monthly_cost,
             estimated_monthly_savings, savings_percentage, severity, analyzed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"/subscriptions/test/vm{i}",
                15.0,
                15,
                "Standard_D4s_v5",
                "Standard_D2s_v5",
                140.16,
                70.08,
                70.08,
                50.0,
                "Medium",
                datetime.now(timezone.utc)
            )
        )

    results = get_low_cpu_vms(limit=1)
    assert len(results) == 1


def test_get_low_cpu_summary_with_results(test_db):
    """Test getting summary with results."""
    # Insert test data
    test_db.execute_query(
        """
        INSERT INTO vm_inventory
        (vm_id, name, resource_group, location, size, power_state, os_type,
         priority, tags, cpu_timeseries, discovered_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "/subscriptions/test/vm1",
            "test-vm-1",
            "rg1",
            "eastus",
            "Standard_D4s_v5",
            "running",
            "Linux",
            "Regular",
            "{}",
            "[]",
            datetime.now(timezone.utc)
        )
    )

    test_db.execute_query(
        """
        INSERT INTO vm_low_cpu_analysis
        (vm_id, cpu_avg, days_under_threshold, current_sku, recommended_sku,
         current_monthly_cost, recommended_monthly_cost,
         estimated_monthly_savings, savings_percentage, severity, analyzed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "/subscriptions/test/vm1",
            15.0,
            15,
            "Standard_D4s_v5",
            "Standard_D2s_v5",
            140.16,
            70.08,
            70.08,
            50.0,
            "Medium",
            datetime.now(timezone.utc)
        )
    )

    summary = get_low_cpu_summary()
    assert summary["total_vms"] == 1
    assert summary["total_potential_savings"] == 70.08
    assert summary["average_savings_percentage"] == 50.0
    assert "Medium" in summary["by_severity"]
    assert summary["by_severity"]["Medium"]["count"] == 1


def test_get_low_cpu_summary_empty(test_db):
    """Test getting summary with no results."""
    summary = get_low_cpu_summary()
    assert summary["total_vms"] == 0
    assert summary["total_potential_savings"] == 0.0
    assert summary["average_savings_percentage"] == 0.0
    assert summary["by_severity"] == {}


def test_analyze_vm_cpu_mixed_days(test_db):
    """Test VM with mixed high/low CPU days but average below threshold."""
    cpu_timeseries = [
        {"timestamp": f"2024-01-{i:02d}T12:00:00Z", "average": 15.0 if i <= 12 else 25.0}
        for i in range(1, 16)  # 12 days low (15%), 3 days slightly higher (25%)
    ]

    result = _analyze_vm_cpu_for_rightsizing(
        vm_id="/subscriptions/test/vm1",
        name="test-vm",
        cpu_timeseries=cpu_timeseries,
        threshold=20.0,
        min_days=14
    )

    assert result is not None
    # Average: (12*15 + 3*25) / 15 = 17%
    assert result["cpu_avg"] == 17.0
    # 12 days under threshold
    assert result["days_under_threshold"] == 12
