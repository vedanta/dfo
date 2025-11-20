"""Tests for DuckDB layer."""
from pathlib import Path

# Third-party
import pytest

# Internal
from dfo.db.duck import DuckDBManager, get_db, reset_db
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


def test_db_initialization(test_db):
    """Test database is initialized with schema."""
    assert test_db.table_exists("vm_inventory")
    assert test_db.table_exists("vm_idle_analysis")
    assert test_db.table_exists("vm_actions")


def test_db_file_creation(tmp_path, monkeypatch):
    """Test that database file is created."""
    db_file = tmp_path / "new_test.duckdb"
    monkeypatch.setenv("DFO_DUCKDB_FILE", str(db_file))
    monkeypatch.setenv("AZURE_TENANT_ID", "test")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test")

    reset_settings()
    reset_db()

    db = get_db()
    assert Path(db_file).exists()

    db.close()
    reset_db()
    reset_settings()


def test_insert_and_fetch(test_db):
    """Test inserting and fetching records."""
    records = [
        {
            "vm_id": "vm1",
            "subscription_id": "test-sub",
            "name": "test-vm-1",
            "resource_group": "rg1",
            "location": "eastus",
            "size": "Standard_D2s_v3",
            "power_state": "running",
            "tags": "{}",
            "cpu_timeseries": "[]",
            "discovered_at": "2024-01-01 00:00:00"
        },
        {
            "vm_id": "vm2",
            "subscription_id": "test-sub",
            "name": "test-vm-2",
            "resource_group": "rg1",
            "location": "westus",
            "size": "Standard_B2s",
            "power_state": "stopped",
            "tags": "{}",
            "cpu_timeseries": "[]",
            "discovered_at": "2024-01-01 00:00:00"
        }
    ]

    test_db.insert_records("vm_inventory", records)
    count = test_db.count_records("vm_inventory")
    assert count == 2

    results = test_db.fetch_all("SELECT * FROM vm_inventory ORDER BY name")
    assert len(results) == 2
    assert results[0][2] == "test-vm-1"  # name column (shifted by 1 due to subscription_id)


def test_clear_table(test_db):
    """Test clearing a table."""
    records = [
        {
            "vm_id": "vm1",
            "subscription_id": "test-sub",
            "name": "test-vm",
            "resource_group": "rg1",
            "location": "eastus",
            "size": "Standard_D2s_v3",
            "power_state": "running",
            "tags": "{}",
            "cpu_timeseries": "[]",
            "discovered_at": "2024-01-01 00:00:00"
        }
    ]

    test_db.insert_records("vm_inventory", records)
    assert test_db.count_records("vm_inventory") == 1

    test_db.clear_table("vm_inventory")
    assert test_db.count_records("vm_inventory") == 0


def test_schema_refresh(test_db):
    """Test schema refresh with drop_existing."""
    # Insert some data
    records = [{
        "vm_id": "vm1",
        "subscription_id": "test-sub",
        "name": "test-vm",
        "resource_group": "rg1",
        "location": "eastus",
        "size": "Standard_D2s_v3",
        "power_state": "running",
        "tags": "{}",
        "cpu_timeseries": "[]",
        "discovered_at": "2024-01-01 00:00:00"
    }]
    test_db.insert_records("vm_inventory", records)
    assert test_db.count_records("vm_inventory") == 1

    # Refresh schema (drop and recreate)
    test_db.initialize_schema(drop_existing=True)

    # Tables should exist but be empty
    assert test_db.table_exists("vm_inventory")
    assert test_db.count_records("vm_inventory") == 0


def test_singleton_pattern(test_db):
    """Test that DuckDBManager is a singleton."""
    db1 = get_db()
    db2 = get_db()
    assert db1 is db2


def test_empty_insert(test_db):
    """Test inserting empty list does nothing."""
    test_db.insert_records("vm_inventory", [])
    assert test_db.count_records("vm_inventory") == 0


def test_table_exists_false(test_db):
    """Test table_exists returns False for non-existent table."""
    assert not test_db.table_exists("nonexistent_table")


def test_fetch_with_params(test_db):
    """Test fetch_all with parameters."""
    records = [
        {
            "vm_id": "vm1",
            "name": "test-vm-1",
            "resource_group": "rg1",
            "location": "eastus",
            "size": "Standard_D2s_v3",
            "power_state": "running",
            "tags": "{}",
            "cpu_timeseries": "[]",
            "discovered_at": "2024-01-01 00:00:00"
        },
        {
            "vm_id": "vm2",
            "name": "test-vm-2",
            "resource_group": "rg2",
            "location": "westus",
            "size": "Standard_B2s",
            "power_state": "stopped",
            "tags": "{}",
            "cpu_timeseries": "[]",
            "discovered_at": "2024-01-01 00:00:00"
        }
    ]

    test_db.insert_records("vm_inventory", records)

    # Query with parameter
    result = test_db.fetch_all(
        "SELECT name FROM vm_inventory WHERE resource_group = ?",
        ("rg1",)
    )
    assert len(result) == 1
    assert result[0][0] == "test-vm-1"
