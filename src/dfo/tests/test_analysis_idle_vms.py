"""Tests for idle VM analysis engine."""
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
import pytest
import json

# Internal
from dfo.analyze.idle_vms import (
    analyze_idle_vms,
    _analyze_vm_cpu,
    _determine_action,
    _calculate_savings,
    _determine_severity,
    get_idle_vms,
    get_idle_vm_summary
)


@pytest.fixture
def mock_vm_inventory_data():
    """Mock VM inventory data with CPU timeseries."""
    # Generate 14 days of hourly CPU metrics (very low usage)
    base_time = datetime.now(timezone.utc) - timedelta(days=14)
    cpu_timeseries = []

    for day in range(14):
        for hour in range(24):
            timestamp = base_time + timedelta(days=day, hours=hour)
            cpu_timeseries.append({
                "timestamp": timestamp.isoformat(),
                "average": 2.5  # Below 5% threshold
            })

    return [
        (
            "vm-123",  # vm_id
            "idle-vm-1",  # name
            "test-rg",  # resource_group
            "eastus",  # location
            "Standard_B1s",  # size
            "VM running",  # power_state
            "Linux",  # os_type
            "Regular",  # priority
            json.dumps(cpu_timeseries)  # cpu_timeseries
        )
    ]


@pytest.fixture
def mock_high_cpu_vm():
    """Mock VM with high CPU usage (not idle)."""
    base_time = datetime.now(timezone.utc) - timedelta(days=14)
    cpu_timeseries = []

    for day in range(14):
        for hour in range(24):
            timestamp = base_time + timedelta(days=day, hours=hour)
            cpu_timeseries.append({
                "timestamp": timestamp.isoformat(),
                "average": 45.0  # Well above 5% threshold
            })

    return [
        (
            "vm-456",
            "busy-vm-1",
            "test-rg",
            "eastus",
            "Standard_B2s",
            "VM running",
            "Windows",
            "Regular",
            json.dumps(cpu_timeseries)
        )
    ]


def test_analyze_idle_vms_success(test_db, mock_vm_inventory_data):
    """Test successful idle VM analysis."""
    from dfo.db.duck import DuckDBManager

    db = DuckDBManager()

    # Insert mock VM into inventory
    vm_data = mock_vm_inventory_data[0]
    db.execute_query(
        """
        INSERT INTO vm_inventory
        (vm_id, name, resource_group, location, size, power_state,
         os_type, priority, cpu_timeseries, discovered_at, subscription_id, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (*vm_data, datetime.now(timezone.utc), "sub-123", "{}")
    )

    # Mock pricing API
    with patch('dfo.providers.azure.pricing.get_vm_monthly_cost_with_metadata', return_value=30.37):
        count = analyze_idle_vms(threshold=5.0, min_days=14)

    assert count == 1

    # Verify analysis result was stored
    results = db.query(
        "SELECT vm_id, cpu_avg, severity, recommended_action FROM vm_idle_analysis"
    )

    assert len(results) == 1
    assert results[0][0] == "vm-123"
    assert results[0][1] < 5.0  # CPU avg below threshold
    assert results[0][2] in ["Critical", "High", "Medium", "Low"]
    assert results[0][3] in ["Delete", "Deallocate", "Downsize"]


def test_analyze_idle_vms_no_idle_found(test_db, mock_high_cpu_vm):
    """Test analysis when no idle VMs found."""
    from dfo.db.duck import DuckDBManager

    db = DuckDBManager()

    # Insert busy VM
    vm_data = mock_high_cpu_vm[0]
    db.execute_query(
        """
        INSERT INTO vm_inventory
        (vm_id, name, resource_group, location, size, power_state,
         os_type, priority, cpu_timeseries, discovered_at, subscription_id, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (*vm_data, datetime.now(timezone.utc), "sub-123", "{}")
    )

    count = analyze_idle_vms(threshold=5.0, min_days=14)

    assert count == 0

    # Verify no analysis results stored
    results = db.query("SELECT COUNT(*) FROM vm_idle_analysis")
    assert results[0][0] == 0


def test_analyze_idle_vms_no_cpu_metrics(test_db):
    """Test analysis when no VMs have CPU metrics."""
    from dfo.db.duck import DuckDBManager

    db = DuckDBManager()

    # Insert VM without CPU metrics
    db.execute_query(
        """
        INSERT INTO vm_inventory
        (vm_id, name, resource_group, location, size, power_state,
         os_type, priority, cpu_timeseries, discovered_at, subscription_id, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "vm-789", "no-metrics-vm", "test-rg", "eastus", "Standard_B1s",
            "VM running", "Linux", "Regular", None,  # No CPU timeseries
            datetime.now(timezone.utc), "sub-123", "{}"
        )
    )

    count = analyze_idle_vms()

    assert count == 0


def test_analyze_idle_vms_insufficient_days(test_db):
    """Test analysis when insufficient days of data."""
    from dfo.db.duck import DuckDBManager

    db = DuckDBManager()

    # Generate only 5 days of data (less than default 14)
    base_time = datetime.now(timezone.utc) - timedelta(days=5)
    cpu_timeseries = []

    for day in range(5):
        for hour in range(24):
            timestamp = base_time + timedelta(days=day, hours=hour)
            cpu_timeseries.append({
                "timestamp": timestamp.isoformat(),
                "average": 2.5
            })

    db.execute_query(
        """
        INSERT INTO vm_inventory
        (vm_id, name, resource_group, location, size, power_state,
         os_type, priority, cpu_timeseries, discovered_at, subscription_id, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "vm-999", "short-data-vm", "test-rg", "eastus", "Standard_B1s",
            "VM running", "Linux", "Regular", json.dumps(cpu_timeseries),
            datetime.now(timezone.utc), "sub-123", "{}"
        )
    )

    # Require 14 days, but only have 5
    count = analyze_idle_vms(min_days=14)

    assert count == 0


def test_analyze_vm_cpu_idle():
    """Test CPU analysis for idle VM."""
    # Use midnight as base to avoid day boundary issues
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    cpu_timeseries = []

    # 14 days of low CPU (2.5% average)
    for day in range(14):
        for hour in range(24):
            timestamp = base_time + timedelta(days=day, hours=hour)
            cpu_timeseries.append({
                "timestamp": timestamp.isoformat(),
                "average": 2.5
            })

    result = _analyze_vm_cpu(
        vm_id="vm-123",
        name="test-vm",
        cpu_timeseries=cpu_timeseries,
        threshold=5.0,
        min_days=14
    )

    assert result is not None
    assert result["cpu_avg"] < 5.0
    assert result["days_under_threshold"] == 14
    assert result["total_days"] == 14


def test_analyze_vm_cpu_not_idle():
    """Test CPU analysis for busy VM."""
    base_time = datetime.now(timezone.utc) - timedelta(days=14)
    cpu_timeseries = []

    # 14 days of high CPU (45% average)
    for day in range(14):
        for hour in range(24):
            timestamp = base_time + timedelta(days=day, hours=hour)
            cpu_timeseries.append({
                "timestamp": timestamp.isoformat(),
                "average": 45.0
            })

    result = _analyze_vm_cpu(
        vm_id="vm-456",
        name="busy-vm",
        cpu_timeseries=cpu_timeseries,
        threshold=5.0,
        min_days=14
    )

    # Should return None for non-idle VM
    assert result is None


def test_analyze_vm_cpu_empty_timeseries():
    """Test CPU analysis with empty timeseries."""
    result = _analyze_vm_cpu(
        vm_id="vm-789",
        name="empty-vm",
        cpu_timeseries=[],
        threshold=5.0,
        min_days=14
    )

    assert result is None


def test_analyze_vm_cpu_insufficient_days():
    """Test CPU analysis with insufficient days."""
    base_time = datetime.now(timezone.utc) - timedelta(days=5)
    cpu_timeseries = []

    # Only 5 days of data
    for day in range(5):
        for hour in range(24):
            timestamp = base_time + timedelta(days=day, hours=hour)
            cpu_timeseries.append({
                "timestamp": timestamp.isoformat(),
                "average": 2.5
            })

    result = _analyze_vm_cpu(
        vm_id="vm-999",
        name="short-data-vm",
        cpu_timeseries=cpu_timeseries,
        threshold=5.0,
        min_days=14  # Require 14 days
    )

    # Should return None due to insufficient data
    assert result is None


def test_determine_action_delete():
    """Test action determination for very low CPU (<1%)."""
    action = _determine_action(cpu_avg=0.5, monthly_cost=30.0, priority="Regular")
    assert action == "Delete"


def test_determine_action_deallocate():
    """Test action determination for low CPU (1-3%)."""
    action = _determine_action(cpu_avg=2.0, monthly_cost=30.0, priority="Regular")
    assert action == "Deallocate"


def test_determine_action_downsize():
    """Test action determination for moderate CPU (3-5%)."""
    action = _determine_action(cpu_avg=4.0, monthly_cost=30.0, priority="Regular")
    assert action == "Downsize"


def test_calculate_savings_delete():
    """Test savings calculation for Delete action."""
    savings = _calculate_savings(action="Delete", monthly_cost=100.0)
    assert savings == 100.0  # 100% savings


def test_calculate_savings_deallocate():
    """Test savings calculation for Deallocate action."""
    savings = _calculate_savings(action="Deallocate", monthly_cost=100.0)
    assert savings == 90.0  # 90% savings


def test_calculate_savings_downsize():
    """Test savings calculation for Downsize action."""
    savings = _calculate_savings(action="Downsize", monthly_cost=100.0)
    assert savings == 50.0  # 50% savings


def test_determine_severity_critical():
    """Test severity determination for high savings ($500+)."""
    severity = _determine_severity(savings=600.0)
    assert severity == "Critical"


def test_determine_severity_high():
    """Test severity determination for medium-high savings ($200-$499)."""
    severity = _determine_severity(savings=300.0)
    assert severity == "High"


def test_determine_severity_medium():
    """Test severity determination for medium savings ($50-$199)."""
    severity = _determine_severity(savings=100.0)
    assert severity == "Medium"


def test_determine_severity_low():
    """Test severity determination for low savings (<$50)."""
    severity = _determine_severity(savings=25.0)
    assert severity == "Low"


def test_get_idle_vms(test_db):
    """Test retrieving idle VM analysis results."""
    from dfo.db.duck import DuckDBManager

    db = DuckDBManager()

    # Insert test VM in inventory
    db.execute_query(
        """
        INSERT INTO vm_inventory
        (vm_id, name, resource_group, location, size, power_state,
         os_type, priority, cpu_timeseries, discovered_at, subscription_id, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "vm-123", "idle-vm", "test-rg", "eastus", "Standard_B1s",
            "VM running", "Linux", "Regular", "[]",
            datetime.now(timezone.utc), "sub-123", "{}"
        )
    )

    # Insert analysis result
    db.execute_query(
        """
        INSERT INTO vm_idle_analysis
        (vm_id, cpu_avg, days_under_threshold, estimated_monthly_savings,
         severity, recommended_action, analyzed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("vm-123", 2.5, 14, 27.33, "Low", "Deallocate", datetime.now(timezone.utc))
    )

    results = get_idle_vms()

    assert len(results) == 1
    assert results[0]["vm_id"] == "vm-123"
    assert results[0]["name"] == "idle-vm"
    assert results[0]["cpu_avg"] == 2.5
    assert results[0]["severity"] == "Low"


def test_get_idle_vms_filter_by_severity(test_db):
    """Test retrieving idle VMs filtered by severity."""
    from dfo.db.duck import DuckDBManager

    db = DuckDBManager()

    # Insert test VMs
    for i, severity in enumerate(["Critical", "High", "Low"]):
        vm_id = f"vm-{i}"
        db.execute_query(
            """
            INSERT INTO vm_inventory
            (vm_id, name, resource_group, location, size, power_state,
             os_type, priority, cpu_timeseries, discovered_at, subscription_id, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                vm_id, f"vm-{i}", "test-rg", "eastus", "Standard_B1s",
                "VM running", "Linux", "Regular", "[]",
                datetime.now(timezone.utc), "sub-123", "{}"
            )
        )

        db.execute_query(
            """
            INSERT INTO vm_idle_analysis
            (vm_id, cpu_avg, days_under_threshold, estimated_monthly_savings,
             severity, recommended_action, analyzed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (vm_id, 2.5, 14, 100.0 * (i + 1), severity, "Deallocate",
             datetime.now(timezone.utc))
        )

    # Filter by Critical
    results = get_idle_vms(severity="Critical")

    assert len(results) == 1
    assert results[0]["severity"] == "Critical"


def test_get_idle_vms_with_limit(test_db):
    """Test retrieving idle VMs with limit."""
    from dfo.db.duck import DuckDBManager

    db = DuckDBManager()

    # Insert 5 test VMs
    for i in range(5):
        vm_id = f"vm-{i}"
        db.execute_query(
            """
            INSERT INTO vm_inventory
            (vm_id, name, resource_group, location, size, power_state,
             os_type, priority, cpu_timeseries, discovered_at, subscription_id, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                vm_id, f"vm-{i}", "test-rg", "eastus", "Standard_B1s",
                "VM running", "Linux", "Regular", "[]",
                datetime.now(timezone.utc), "sub-123", "{}"
            )
        )

        db.execute_query(
            """
            INSERT INTO vm_idle_analysis
            (vm_id, cpu_avg, days_under_threshold, estimated_monthly_savings,
             severity, recommended_action, analyzed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (vm_id, 2.5, 14, 50.0, "Medium", "Deallocate",
             datetime.now(timezone.utc))
        )

    # Get only top 3
    results = get_idle_vms(limit=3)

    assert len(results) == 3


def test_get_idle_vm_summary_with_results(test_db):
    """Test summary with idle VMs."""
    from dfo.db.duck import DuckDBManager

    db = DuckDBManager()

    # Insert test VMs with different severities and actions
    test_data = [
        ("vm-1", "Critical", "Delete", 600.0),
        ("vm-2", "High", "Deallocate", 300.0),
        ("vm-3", "Medium", "Downsize", 100.0),
        ("vm-4", "Low", "Deallocate", 25.0)
    ]

    for vm_id, severity, action, savings in test_data:
        db.execute_query(
            """
            INSERT INTO vm_inventory
            (vm_id, name, resource_group, location, size, power_state,
             os_type, priority, cpu_timeseries, discovered_at, subscription_id, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                vm_id, vm_id, "test-rg", "eastus", "Standard_B1s",
                "VM running", "Linux", "Regular", "[]",
                datetime.now(timezone.utc), "sub-123", "{}"
            )
        )

        db.execute_query(
            """
            INSERT INTO vm_idle_analysis
            (vm_id, cpu_avg, days_under_threshold, estimated_monthly_savings,
             severity, recommended_action, analyzed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (vm_id, 2.5, 14, savings, severity, action, datetime.now(timezone.utc))
        )

    summary = get_idle_vm_summary()

    assert summary["total_idle_vms"] == 4
    assert summary["total_potential_savings"] == 1025.0  # Sum of all savings

    # Check severity breakdown
    assert summary["by_severity"]["Critical"]["count"] == 1
    assert summary["by_severity"]["High"]["count"] == 1

    # Check action breakdown
    assert summary["by_action"]["Delete"]["count"] == 1
    assert summary["by_action"]["Deallocate"]["count"] == 2
    assert summary["by_action"]["Downsize"]["count"] == 1


def test_get_idle_vm_summary_empty(test_db):
    """Test summary with no idle VMs."""
    summary = get_idle_vm_summary()

    assert summary["total_idle_vms"] == 0
    assert summary["total_potential_savings"] == 0.0
    assert len(summary["by_severity"]) == 0
    assert len(summary["by_action"]) == 0


def test_analyze_vm_cpu_mixed_days():
    """Test CPU analysis with some days above threshold."""
    # Use midnight as base to avoid day boundary issues
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    cpu_timeseries = []

    # 10 days below threshold, 4 days above
    for day in range(14):
        avg_cpu = 2.0 if day < 10 else 8.0  # First 10 days idle, last 4 busy

        for hour in range(24):
            timestamp = base_time + timedelta(days=day, hours=hour)
            cpu_timeseries.append({
                "timestamp": timestamp.isoformat(),
                "average": avg_cpu
            })

    result = _analyze_vm_cpu(
        vm_id="vm-mixed",
        name="mixed-vm",
        cpu_timeseries=cpu_timeseries,
        threshold=5.0,
        min_days=14
    )

    # Overall average is (10*2.0 + 4*8.0) / 14 = 4.57%, so should be idle
    assert result is not None
    assert result["cpu_avg"] < 5.0
    assert result["days_under_threshold"] == 10
    assert result["total_days"] == 14
