"""Tests for azure show command."""

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
def sample_vm(setup_env):
    """Insert sample VM data."""
    import json
    from datetime import datetime

    record = {
        "vm_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/test-vm",
        "subscription_id": "sub1",
        "name": "test-vm",
        "resource_group": "test-rg",
        "location": "eastus",
        "size": "Standard_B1s",
        "power_state": "running",
        "os_type": "Linux",
        "priority": "Regular",
        "tags": json.dumps({"env": "test", "owner": "team1"}),
        "cpu_timeseries": json.dumps([
            {"timestamp": "2025-01-01T00:00:00Z", "average": 10.5, "minimum": 5.0, "maximum": 15.0},
            {"timestamp": "2025-01-01T01:00:00Z", "average": 12.0, "minimum": 8.0, "maximum": 18.0},
            {"timestamp": "2025-01-01T02:00:00Z", "average": 8.5, "minimum": 4.0, "maximum": 12.0}
        ]),
        "discovered_at": datetime.utcnow()
    }

    setup_env.insert_records("vm_inventory", [record])
    return record


def test_show_vm_basic(sample_vm):
    """Test showing basic VM details."""
    result = runner.invoke(app, ["azure", "show", "vm", "test-vm"])

    assert result.exit_code == 0
    assert "test-vm" in result.stdout
    assert "Basic Information" in result.stdout
    assert "test-rg" in result.stdout
    assert "eastus" in result.stdout
    assert "Standard_B1s" in result.stdout
    assert "running" in result.stdout


def test_show_vm_with_tags(sample_vm):
    """Test showing VM with tags."""
    result = runner.invoke(app, ["azure", "show", "vm", "test-vm"])

    assert result.exit_code == 0
    assert "Tags" in result.stdout
    assert "env: test" in result.stdout
    assert "owner: team1" in result.stdout


def test_show_vm_with_metrics(sample_vm):
    """Test showing VM with CPU metrics."""
    result = runner.invoke(app, ["azure", "show", "vm", "test-vm"])

    assert result.exit_code == 0
    assert "CPU Metrics" in result.stdout
    assert "Data Points: 3" in result.stdout
    assert "Average CPU:" in result.stdout
    assert "Min CPU:" in result.stdout
    assert "Max CPU:" in result.stdout


def test_show_vm_with_detailed_metrics(sample_vm):
    """Test showing VM with detailed metrics flag."""
    result = runner.invoke(app, ["azure", "show", "vm", "test-vm", "--metrics"])

    assert result.exit_code == 0
    assert "Detailed Metrics" in result.stdout
    assert "CPU Timeseries Data" in result.stdout


def test_show_vm_not_found(setup_env):
    """Test showing non-existent VM."""
    result = runner.invoke(app, ["azure", "show", "vm", "nonexistent-vm"])

    assert result.exit_code == 1
    assert "not found in inventory" in result.stdout


def test_show_vm_without_metrics(setup_env):
    """Test showing VM without metrics."""
    import json
    from datetime import datetime

    record = {
        "vm_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/no-metrics-vm",
        "subscription_id": "sub1",
        "name": "no-metrics-vm",
        "resource_group": "test-rg",
        "location": "eastus",
        "size": "Standard_B1s",
        "power_state": "stopped",
        "os_type": "Linux",
        "priority": "Regular",
        "tags": json.dumps({}),
        "cpu_timeseries": json.dumps([]),
        "discovered_at": datetime.utcnow()
    }

    setup_env.insert_records("vm_inventory", [record])

    result = runner.invoke(app, ["azure", "show", "vm", "no-metrics-vm"])

    assert result.exit_code == 0
    assert "No metrics collected" in result.stdout


def test_show_vm_unsupported_resource_type(sample_vm):
    """Test show command with unsupported resource type."""
    result = runner.invoke(app, ["azure", "show", "database", "test-vm"])

    assert result.exit_code == 1
    assert "Unsupported resource type" in result.stdout


def test_show_vm_help(setup_env):
    """Test show command help."""
    result = runner.invoke(app, ["azure", "show", "--help"])

    assert result.exit_code == 0
    assert "Show detailed information about a specific resource" in result.stdout
    assert "--metrics" in result.stdout
