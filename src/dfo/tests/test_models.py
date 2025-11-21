"""Tests for core data models."""
from datetime import datetime

# Third-party
import pytest

# Internal
from dfo.core.models import (
    VM, VMInventory, VMAnalysis, VMAction,
    PowerState, Severity, RecommendedAction
)


def test_vm_model():
    """Test VM model validation."""
    vm = VM(
        vm_id="/subscriptions/test/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1",
        name="test-vm",
        resource_group="test-rg",
        location="eastus",
        size="Standard_D2s_v3",
        power_state=PowerState.RUNNING
    )
    assert vm.name == "test-vm"
    assert vm.power_state == PowerState.RUNNING
    assert vm.tags == {}


def test_vm_with_tags():
    """Test VM model with tags."""
    vm = VM(
        vm_id="test-id",
        name="test-vm",
        resource_group="test-rg",
        location="eastus",
        size="Standard_D2s_v3",
        power_state=PowerState.RUNNING,
        tags={"env": "dev", "owner": "team-a"}
    )
    assert vm.tags["env"] == "dev"
    assert vm.tags["owner"] == "team-a"


def test_vm_inventory_to_db_record():
    """Test VMInventory serialization to DB record."""
    inventory = VMInventory(
        vm_id="test-id",
        subscription_id="test-subscription",
        name="test-vm",
        resource_group="test-rg",
        location="eastus",
        size="Standard_D2s_v3",
        power_state="running",
        os_type="Linux",
        priority="Regular",
        tags={"env": "dev"},
        cpu_timeseries=[{"timestamp": "2024-01-01T00:00:00Z", "average": 5.0}]
    )

    record = inventory.to_db_record()
    assert record["vm_id"] == "test-id"
    assert record["subscription_id"] == "test-subscription"
    assert record["name"] == "test-vm"
    assert record["os_type"] == "Linux"
    assert record["priority"] == "Regular"
    assert "tags" in record
    assert "cpu_timeseries" in record
    # JSON strings for DuckDB
    assert isinstance(record["tags"], str)
    assert isinstance(record["cpu_timeseries"], str)
    assert '"env": "dev"' in record["tags"]


def test_vm_analysis_severity_enum():
    """Test severity enum values."""
    analysis = VMAnalysis(
        vm_id="test-id",
        cpu_avg=2.5,
        days_under_threshold=14,
        estimated_monthly_savings=600.0,
        severity=Severity.CRITICAL,
        recommended_action=RecommendedAction.DEALLOCATE
    )
    assert analysis.severity == Severity.CRITICAL
    assert analysis.severity.value == "critical"
    assert analysis.recommended_action == RecommendedAction.DEALLOCATE


def test_vm_analysis_to_db_record():
    """Test VMAnalysis serialization."""
    analysis = VMAnalysis(
        vm_id="test-id",
        cpu_avg=3.2,
        days_under_threshold=10,
        estimated_monthly_savings=150.0,
        severity=Severity.MEDIUM,
        recommended_action=RecommendedAction.STOP
    )

    record = analysis.to_db_record()
    assert record["vm_id"] == "test-id"
    assert record["cpu_avg"] == 3.2
    assert record["severity"] == "medium"
    assert record["recommended_action"] == "stop"


def test_vm_action_model():
    """Test VMAction model."""
    action = VMAction(
        vm_id="test-id",
        action="stop",
        status="success",
        dry_run=True,
        notes="Test dry run"
    )

    assert action.dry_run is True
    assert action.notes == "Test dry run"

    record = action.to_db_record()
    assert record["action"] == "stop"
    assert record["status"] == "success"
    assert record["dry_run"] is True


def test_power_state_enum():
    """Test PowerState enum values."""
    assert PowerState.RUNNING.value == "running"
    assert PowerState.STOPPED.value == "stopped"
    assert PowerState.DEALLOCATED.value == "deallocated"
    assert PowerState.UNKNOWN.value == "unknown"


def test_severity_enum_order():
    """Test Severity enum values."""
    assert Severity.CRITICAL.value == "critical"
    assert Severity.HIGH.value == "high"
    assert Severity.MEDIUM.value == "medium"
    assert Severity.LOW.value == "low"


def test_recommended_action_enum():
    """Test RecommendedAction enum values."""
    assert RecommendedAction.STOP.value == "stop"
    assert RecommendedAction.DEALLOCATE.value == "deallocate"
    assert RecommendedAction.RESIZE.value == "resize"
    assert RecommendedAction.NONE.value == "none"


def test_vm_inventory_default_discovered_at():
    """Test that discovered_at has a default value."""
    inventory = VMInventory(
        vm_id="test-id",
        subscription_id="test-subscription",
        name="test-vm",
        resource_group="test-rg",
        location="eastus",
        size="Standard_D2s_v3",
        power_state="running"
    )
    assert isinstance(inventory.discovered_at, datetime)
    assert inventory.priority == "Regular"  # Default value
    assert inventory.os_type is None  # Optional field


def test_vm_analysis_default_analyzed_at():
    """Test that analyzed_at has a default value."""
    analysis = VMAnalysis(
        vm_id="test-id",
        cpu_avg=2.5,
        days_under_threshold=14,
        estimated_monthly_savings=100.0,
        severity=Severity.MEDIUM,
        recommended_action=RecommendedAction.STOP
    )
    assert isinstance(analysis.analyzed_at, datetime)
