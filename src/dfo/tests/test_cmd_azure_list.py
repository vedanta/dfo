"""Tests for azure list command."""

# Third-party
import pytest
from typer.testing import CliRunner

# Internal
from dfo.cli import app
from dfo.db.duck import reset_db, DuckDBManager
from dfo.core.config import reset_settings

runner = CliRunner()


@pytest.fixture
def setup_env(monkeypatch, tmp_path):
    """Setup test environment with test database."""
    # Create temp database
    test_db = tmp_path / "test.duckdb"
    monkeypatch.setenv("DFO_DUCKDB_FILE", str(test_db))
    monkeypatch.setenv("DFO_IDLE_CPU_THRESHOLD", "5.0")
    monkeypatch.setenv("DFO_IDLE_DAYS", "7")

    reset_settings()
    reset_db()

    # Initialize database
    db = DuckDBManager()
    db.initialize_schema()

    yield db

    reset_settings()
    reset_db()


@pytest.fixture
def sample_vms(setup_env):
    """Insert sample VM data."""
    import json
    from datetime import datetime

    records = [
        {
            "vm_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "subscription_id": "sub1",
            "name": "vm1",
            "resource_group": "rg1",
            "location": "eastus",
            "size": "Standard_B1s",
            "power_state": "running",
            "os_type": "Linux",
            "priority": "Regular",
            "tags": json.dumps({"env": "test"}),
            "cpu_timeseries": json.dumps([
                {"timestamp": "2025-01-01T00:00:00Z", "average": 10.5}
            ]),
            "discovered_at": datetime.utcnow()
        },
        {
            "vm_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm2",
            "subscription_id": "sub1",
            "name": "vm2",
            "resource_group": "rg2",
            "location": "westus",
            "size": "Standard_B2s",
            "power_state": "stopped",
            "os_type": "Windows",
            "priority": "Regular",
            "tags": json.dumps({}),
            "cpu_timeseries": json.dumps([]),
            "discovered_at": datetime.utcnow()
        },
        {
            "vm_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm3",
            "subscription_id": "sub1",
            "name": "vm3",
            "resource_group": "rg1",
            "location": "eastus",
            "size": "Standard_B1s",
            "power_state": "running",
            "os_type": "Linux",
            "priority": "Regular",
            "tags": json.dumps({}),
            "cpu_timeseries": json.dumps([
                {"timestamp": "2025-01-01T00:00:00Z", "average": 5.0}
            ]),
            "discovered_at": datetime.utcnow()
        }
    ]

    setup_env.insert_records("vm_inventory", records)
    return records


def test_list_vms_empty_database(setup_env):
    """Test list command with empty database."""
    result = runner.invoke(app, ["azure", "list", "vms"])

    assert result.exit_code == 0
    assert "No VMs found in inventory" in result.stdout


def test_list_vms_all(sample_vms):
    """Test listing all VMs."""
    result = runner.invoke(app, ["azure", "list", "vms"])

    assert result.exit_code == 0
    assert "VM Inventory (3 VMs)" in result.stdout
    assert "vm1" in result.stdout
    assert "vm2" in result.stdout
    assert "vm3" in result.stdout
    assert "Power State Distribution" in result.stdout
    assert "Location Distribution" in result.stdout


def test_list_vms_filter_by_resource_group(sample_vms):
    """Test filtering VMs by resource group."""
    result = runner.invoke(app, ["azure", "list", "vms", "--resource-group", "rg1"])

    assert result.exit_code == 0
    assert "VM Inventory (2 VMs)" in result.stdout
    assert "vm1" in result.stdout
    assert "vm3" in result.stdout
    assert "vm2" not in result.stdout


def test_list_vms_filter_by_location(sample_vms):
    """Test filtering VMs by location."""
    result = runner.invoke(app, ["azure", "list", "vms", "--location", "eastus"])

    assert result.exit_code == 0
    assert "VM Inventory (2 VMs)" in result.stdout
    assert "vm1" in result.stdout
    assert "vm3" in result.stdout
    assert "vm2" not in result.stdout


def test_list_vms_filter_by_power_state(sample_vms):
    """Test filtering VMs by power state."""
    result = runner.invoke(app, ["azure", "list", "vms", "--power-state", "running"])

    assert result.exit_code == 0
    assert "VM Inventory (2 VMs)" in result.stdout
    assert "vm1" in result.stdout
    assert "vm3" in result.stdout
    assert "vm2" not in result.stdout


def test_list_vms_filter_by_size(sample_vms):
    """Test filtering VMs by size."""
    result = runner.invoke(app, ["azure", "list", "vms", "--size", "Standard_B2s"])

    assert result.exit_code == 0
    assert "VM Inventory (1 VMs)" in result.stdout
    assert "vm2" in result.stdout
    assert "vm1" not in result.stdout


def test_list_vms_with_limit(sample_vms):
    """Test listing VMs with limit."""
    result = runner.invoke(app, ["azure", "list", "vms", "--limit", "2"])

    assert result.exit_code == 0
    assert "VM Inventory (2 VMs)" in result.stdout


def test_list_vms_combined_filters(sample_vms):
    """Test listing VMs with multiple filters."""
    result = runner.invoke(app, [
        "azure", "list", "vms",
        "--resource-group", "rg1",
        "--power-state", "running"
    ])

    assert result.exit_code == 0
    assert "VM Inventory (2 VMs)" in result.stdout
    assert "vm1" in result.stdout
    assert "vm3" in result.stdout


def test_list_vms_unsupported_resource_type(sample_vms):
    """Test list command with unsupported resource type."""
    result = runner.invoke(app, ["azure", "list", "databases"])

    assert result.exit_code == 1
    assert "Unsupported resource type" in result.stdout


def test_list_vms_help(setup_env):
    """Test list command help."""
    result = runner.invoke(app, ["azure", "list", "--help"])

    assert result.exit_code == 0
    assert "List discovered resources from local database" in result.stdout
    assert "--resource-group" in result.stdout
    assert "--location" in result.stdout
    assert "--power-state" in result.stdout
