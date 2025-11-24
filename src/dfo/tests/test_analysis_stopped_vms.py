"""Tests for stopped VM analysis module."""
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

# Third-party
import pytest

# Internal
from dfo.analyze.stopped_vms import (
    analyze_stopped_vms,
    _estimate_disk_cost,
    _determine_action,
    _determine_severity,
    get_stopped_vms,
    get_stopped_vm_summary
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


def test_analyze_stopped_vms_success(test_db):
    """Test successful stopped VM analysis."""
    # Insert VM stopped for 45 days
    discovered_at = datetime.now(timezone.utc) - timedelta(days=45)

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
            "deallocated",
            "Linux",
            "Regular",
            "{}",
            "[]",
            discovered_at.isoformat()
        )
    )

    # Mock pricing call
    with patch('dfo.analyze.stopped_vms.get_vm_monthly_cost_with_metadata') as mock_pricing:
        mock_pricing.return_value = {
            "monthly_cost": 140.16,
            "equivalent_sku": None
        }

        # Run analysis
        count = analyze_stopped_vms(min_days=30)

        assert count == 1

    # Verify analysis stored
    results = test_db.query("SELECT * FROM vm_stopped_vms_analysis")
    assert len(results) == 1

    result = results[0]
    assert result[0] == "/subscriptions/test/vm1"  # vm_id
    assert result[1] == "deallocated"  # power_state
    assert result[2] == 45  # days_stopped
    assert result[3] == 14.016  # disk_cost_monthly (10% of 140.16)
    assert result[4] == 14.016  # estimated_monthly_savings
    assert result[5] == "Low"  # severity
    assert result[6] == "Review"  # recommended_action


def test_analyze_stopped_vms_delete_recommendation(test_db):
    """Test VM stopped for > 90 days gets Delete recommendation."""
    # Insert VM stopped for 100 days
    discovered_at = datetime.now(timezone.utc) - timedelta(days=100)

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
            "stopped",
            "Linux",
            "Regular",
            "{}",
            "[]",
            discovered_at.isoformat()
        )
    )

    # Mock pricing call
    with patch('dfo.analyze.stopped_vms.get_vm_monthly_cost_with_metadata') as mock_pricing:
        mock_pricing.return_value = {
            "monthly_cost": 140.16,
            "equivalent_sku": None
        }

        count = analyze_stopped_vms(min_days=30)

        assert count == 1

    # Verify Delete recommendation
    results = test_db.query("SELECT * FROM vm_stopped_vms_analysis")
    result = results[0]
    assert result[2] == 100  # days_stopped
    assert result[6] == "Delete"  # recommended_action


def test_analyze_stopped_vms_no_candidates(test_db):
    """Test analysis with no stopped VMs."""
    # Insert running VM
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
            datetime.now(timezone.utc).isoformat()
        )
    )

    count = analyze_stopped_vms(min_days=30)

    assert count == 0

    # Verify no results stored
    results = test_db.query("SELECT * FROM vm_stopped_vms_analysis")
    assert len(results) == 0


def test_analyze_stopped_vms_insufficient_days(test_db):
    """Test stopped VM under minimum threshold is skipped."""
    # Insert VM stopped for only 15 days (need 30)
    discovered_at = datetime.now(timezone.utc) - timedelta(days=15)

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
            "deallocated",
            "Linux",
            "Regular",
            "{}",
            "[]",
            discovered_at.isoformat()
        )
    )

    count = analyze_stopped_vms(min_days=30)

    assert count == 0


def test_analyze_stopped_vms_both_states(test_db):
    """Test analysis handles both stopped and deallocated states."""
    discovered_at = datetime.now(timezone.utc) - timedelta(days=45)

    # Insert stopped VM
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
            "stopped",
            "Linux",
            "Regular",
            "{}",
            "[]",
            discovered_at.isoformat()
        )
    )

    # Insert deallocated VM
    test_db.execute_query(
        """
        INSERT INTO vm_inventory
        (vm_id, name, resource_group, location, size, power_state, os_type,
         priority, tags, cpu_timeseries, discovered_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "/subscriptions/test/vm2",
            "test-vm-2",
            "rg1",
            "eastus",
            "Standard_D4s_v5",
            "deallocated",
            "Linux",
            "Regular",
            "{}",
            "[]",
            discovered_at.isoformat()
        )
    )

    # Mock pricing call
    with patch('dfo.analyze.stopped_vms.get_vm_monthly_cost_with_metadata') as mock_pricing:
        mock_pricing.return_value = {
            "monthly_cost": 140.16,
            "equivalent_sku": None
        }

        count = analyze_stopped_vms(min_days=30)

        assert count == 2

    # Verify both stored
    results = test_db.query("SELECT * FROM vm_stopped_vms_analysis ORDER BY vm_id")
    assert len(results) == 2
    assert results[0][1] == "stopped"  # power_state
    assert results[1][1] == "deallocated"  # power_state


def test_estimate_disk_cost():
    """Test disk cost estimation."""
    with patch('dfo.analyze.stopped_vms.get_vm_monthly_cost_with_metadata') as mock_pricing:
        mock_pricing.return_value = {
            "monthly_cost": 140.16,
            "equivalent_sku": None
        }

        disk_cost = _estimate_disk_cost(
            vm_size="Standard_D4s_v5",
            region="eastus",
            os_type="Linux"
        )

        # Should be 10% of total cost
        assert disk_cost == 14.016


def test_estimate_disk_cost_high_cost_vm():
    """Test disk cost estimation for expensive VM."""
    with patch('dfo.analyze.stopped_vms.get_vm_monthly_cost_with_metadata') as mock_pricing:
        mock_pricing.return_value = {
            "monthly_cost": 5000.0,
            "equivalent_sku": None
        }

        disk_cost = _estimate_disk_cost(
            vm_size="Standard_E64s_v5",
            region="eastus",
            os_type="Windows"
        )

        # Should be 10% of total cost
        assert disk_cost == 500.0


def test_determine_action_review():
    """Test recommended action for recently stopped VMs."""
    assert _determine_action(30) == "Review"
    assert _determine_action(45) == "Review"
    assert _determine_action(90) == "Review"


def test_determine_action_delete():
    """Test recommended action for long-term stopped VMs."""
    assert _determine_action(91) == "Delete"
    assert _determine_action(100) == "Delete"
    assert _determine_action(365) == "Delete"


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


def test_get_stopped_vms(test_db):
    """Test retrieving stopped VMs."""
    discovered_at = datetime.now(timezone.utc) - timedelta(days=45)

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
            "deallocated",
            "Linux",
            "Regular",
            "{}",
            "[]",
            discovered_at.isoformat()
        )
    )

    test_db.execute_query(
        """
        INSERT INTO vm_stopped_vms_analysis
        (vm_id, power_state, days_stopped, disk_cost_monthly,
         estimated_monthly_savings, severity, recommended_action, analyzed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "/subscriptions/test/vm1",
            "deallocated",
            45,
            14.016,
            14.016,
            "Low",
            "Review",
            datetime.now(timezone.utc)
        )
    )

    results = get_stopped_vms()
    assert len(results) == 1
    assert results[0]["name"] == "test-vm-1"
    assert results[0]["power_state"] == "deallocated"
    assert results[0]["days_stopped"] == 45
    assert results[0]["recommended_action"] == "Review"


def test_get_stopped_vms_filter_by_severity(test_db):
    """Test retrieving stopped VMs filtered by severity."""
    discovered_at = datetime.now(timezone.utc) - timedelta(days=45)

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
            "deallocated",
            "Linux",
            "Regular",
            "{}",
            "[]",
            discovered_at.isoformat()
        )
    )

    test_db.execute_query(
        """
        INSERT INTO vm_stopped_vms_analysis
        (vm_id, power_state, days_stopped, disk_cost_monthly,
         estimated_monthly_savings, severity, recommended_action, analyzed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "/subscriptions/test/vm1",
            "deallocated",
            45,
            14.016,
            14.016,
            "Low",
            "Review",
            datetime.now(timezone.utc)
        )
    )

    # Filter by Low severity
    results = get_stopped_vms(severity="Low")
    assert len(results) == 1

    # Filter by High severity (should return nothing)
    results = get_stopped_vms(severity="High")
    assert len(results) == 0


def test_get_stopped_vms_with_limit(test_db):
    """Test retrieving stopped VMs with limit."""
    discovered_at = datetime.now(timezone.utc) - timedelta(days=45)

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
                "deallocated",
                "Linux",
                "Regular",
                "{}",
                "[]",
                discovered_at.isoformat()
            )
        )

        test_db.execute_query(
            """
            INSERT INTO vm_stopped_vms_analysis
            (vm_id, power_state, days_stopped, disk_cost_monthly,
             estimated_monthly_savings, severity, recommended_action, analyzed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"/subscriptions/test/vm{i}",
                "deallocated",
                45,
                14.016,
                14.016,
                "Low",
                "Review",
                datetime.now(timezone.utc)
            )
        )

    results = get_stopped_vms(limit=1)
    assert len(results) == 1


def test_get_stopped_vm_summary_with_results(test_db):
    """Test getting summary with results."""
    discovered_at = datetime.now(timezone.utc) - timedelta(days=45)

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
            "deallocated",
            "Linux",
            "Regular",
            "{}",
            "[]",
            discovered_at.isoformat()
        )
    )

    test_db.execute_query(
        """
        INSERT INTO vm_stopped_vms_analysis
        (vm_id, power_state, days_stopped, disk_cost_monthly,
         estimated_monthly_savings, severity, recommended_action, analyzed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "/subscriptions/test/vm1",
            "deallocated",
            45,
            14.016,
            14.016,
            "Low",
            "Review",
            datetime.now(timezone.utc)
        )
    )

    summary = get_stopped_vm_summary()
    assert summary["total_stopped_vms"] == 1
    assert summary["total_potential_savings"] == 14.016
    assert "Low" in summary["by_severity"]
    assert summary["by_severity"]["Low"]["count"] == 1
    assert "Review" in summary["by_action"]
    assert summary["by_action"]["Review"]["count"] == 1
    assert "deallocated" in summary["by_power_state"]
    assert summary["by_power_state"]["deallocated"]["count"] == 1


def test_get_stopped_vm_summary_empty(test_db):
    """Test getting summary with no results."""
    summary = get_stopped_vm_summary()
    assert summary["total_stopped_vms"] == 0
    assert summary["total_potential_savings"] == 0.0
    assert summary["by_severity"] == {}
    assert summary["by_action"] == {}
    assert summary["by_power_state"] == {}


def test_get_stopped_vms_ordered_by_days(test_db):
    """Test stopped VMs are returned ordered by days stopped (desc)."""
    # Insert VM stopped for 100 days
    discovered_at_100 = datetime.now(timezone.utc) - timedelta(days=100)
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
            "stopped",
            "Linux",
            "Regular",
            "{}",
            "[]",
            discovered_at_100.isoformat()
        )
    )

    test_db.execute_query(
        """
        INSERT INTO vm_stopped_vms_analysis
        (vm_id, power_state, days_stopped, disk_cost_monthly,
         estimated_monthly_savings, severity, recommended_action, analyzed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "/subscriptions/test/vm1",
            "stopped",
            100,
            14.016,
            14.016,
            "Low",
            "Delete",
            datetime.now(timezone.utc)
        )
    )

    # Insert VM stopped for 45 days
    discovered_at_45 = datetime.now(timezone.utc) - timedelta(days=45)
    test_db.execute_query(
        """
        INSERT INTO vm_inventory
        (vm_id, name, resource_group, location, size, power_state, os_type,
         priority, tags, cpu_timeseries, discovered_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "/subscriptions/test/vm2",
            "test-vm-2",
            "rg1",
            "eastus",
            "Standard_D4s_v5",
            "deallocated",
            "Linux",
            "Regular",
            "{}",
            "[]",
            discovered_at_45.isoformat()
        )
    )

    test_db.execute_query(
        """
        INSERT INTO vm_stopped_vms_analysis
        (vm_id, power_state, days_stopped, disk_cost_monthly,
         estimated_monthly_savings, severity, recommended_action, analyzed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "/subscriptions/test/vm2",
            "deallocated",
            45,
            14.016,
            14.016,
            "Low",
            "Review",
            datetime.now(timezone.utc)
        )
    )

    results = get_stopped_vms()
    assert len(results) == 2
    # First result should be the one stopped longer (100 days)
    assert results[0]["days_stopped"] == 100
    assert results[1]["days_stopped"] == 45
