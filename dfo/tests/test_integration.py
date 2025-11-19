"""Integration tests for Milestone 1.

These tests verify the full end-to-end flow of:
- Configuration loading
- Database initialization
- Model validation
- Data insertion and retrieval
"""
from datetime import datetime
from pathlib import Path

# Third-party
import pytest

# Internal
from dfo.core.config import get_settings, reset_settings
from dfo.db.duck import get_db, reset_db
from dfo.core.models import VMInventory, VMAnalysis, Severity, RecommendedAction


@pytest.fixture
def integration_env(tmp_path, monkeypatch):
    """Setup integration test environment."""
    db_file = tmp_path / "integration.duckdb"
    monkeypatch.setenv("DFO_DUCKDB_FILE", str(db_file))
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-sub")
    monkeypatch.setenv("DFO_IDLE_CPU_THRESHOLD", "10.0")

    reset_settings()
    reset_db()

    yield

    reset_db()
    reset_settings()


def test_full_setup_flow(integration_env):
    """Test full setup: config -> db init -> data insert."""
    # 1. Load configuration
    settings = get_settings()
    assert settings.azure_tenant_id == "test-tenant"
    assert settings.dfo_idle_cpu_threshold == 10.0

    # 2. Initialize database
    db = get_db()
    db.initialize_schema()

    # 3. Verify tables exist
    assert db.table_exists("vm_inventory")
    assert db.table_exists("vm_idle_analysis")
    assert db.table_exists("vm_actions")

    # 4. Insert test data using models
    inventory = VMInventory(
        vm_id="test-vm-1",
        name="integration-test-vm",
        resource_group="test-rg",
        location="eastus",
        size="Standard_D2s_v3",
        power_state="running",
        tags={"env": "test"},
        cpu_timeseries=[{"timestamp": "2024-01-01T00:00:00Z", "average": 5.0}]
    )

    db.insert_records("vm_inventory", [inventory.to_db_record()])

    # 5. Verify data inserted
    count = db.count_records("vm_inventory")
    assert count == 1

    results = db.fetch_all("SELECT name FROM vm_inventory")
    assert results[0][0] == "integration-test-vm"


def test_full_analysis_flow(integration_env):
    """Test full analysis flow: inventory -> analysis."""
    # Setup
    settings = get_settings()
    db = get_db()
    db.initialize_schema()

    # 1. Insert VM inventory
    inventory = VMInventory(
        vm_id="vm-idle-1",
        name="idle-vm",
        resource_group="test-rg",
        location="eastus",
        size="Standard_D2s_v3",
        power_state="running",
        tags={},
        cpu_timeseries=[
            {"timestamp": "2024-01-01T00:00:00Z", "average": 2.0},
            {"timestamp": "2024-01-02T00:00:00Z", "average": 3.0}
        ]
    )
    db.insert_records("vm_inventory", [inventory.to_db_record()])

    # 2. Create analysis result
    analysis = VMAnalysis(
        vm_id="vm-idle-1",
        cpu_avg=2.5,
        days_under_threshold=14,
        estimated_monthly_savings=150.0,
        severity=Severity.MEDIUM,
        recommended_action=RecommendedAction.STOP
    )
    db.insert_records("vm_idle_analysis", [analysis.to_db_record()])

    # 3. Verify analysis stored
    count = db.count_records("vm_idle_analysis")
    assert count == 1

    results = db.fetch_all(
        "SELECT vm_id, cpu_avg, severity FROM vm_idle_analysis"
    )
    assert results[0][0] == "vm-idle-1"
    assert results[0][1] == 2.5
    assert results[0][2] == "medium"


def test_multiple_records_workflow(integration_env):
    """Test workflow with multiple records."""
    db = get_db()
    db.initialize_schema()

    # Insert multiple VM inventories
    inventories = [
        VMInventory(
            vm_id=f"vm-{i}",
            name=f"test-vm-{i}",
            resource_group="test-rg",
            location="eastus",
            size="Standard_D2s_v3",
            power_state="running",
            tags={"index": str(i)},
            cpu_timeseries=[]
        )
        for i in range(5)
    ]

    records = [inv.to_db_record() for inv in inventories]
    db.insert_records("vm_inventory", records)

    # Verify all inserted
    count = db.count_records("vm_inventory")
    assert count == 5

    # Query specific VM
    results = db.fetch_all(
        "SELECT name FROM vm_inventory WHERE vm_id = ?",
        ("vm-2",)
    )
    assert results[0][0] == "test-vm-2"


def test_schema_refresh_workflow(integration_env):
    """Test that schema refresh works in workflow."""
    db = get_db()
    db.initialize_schema()

    # Insert data
    inventory = VMInventory(
        vm_id="test-vm",
        name="test",
        resource_group="rg",
        location="eastus",
        size="Standard_D2s_v3",
        power_state="running"
    )
    db.insert_records("vm_inventory", [inventory.to_db_record()])
    assert db.count_records("vm_inventory") == 1

    # Refresh schema (should clear data)
    db.initialize_schema(drop_existing=True)

    # Verify tables exist but are empty
    assert db.table_exists("vm_inventory")
    assert db.count_records("vm_inventory") == 0
