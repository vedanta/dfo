"""Tests for inventory sorting functionality."""

from datetime import datetime, timezone, timedelta
from dfo.inventory.queries import get_vms_filtered
from dfo.db.duck import DuckDBManager


def test_sort_by_name_ascending(test_db):
    """Test sorting VMs by name in ascending order."""
    db = DuckDBManager()

    # Insert VMs in random order
    for name in ["charlie", "alpha", "bravo"]:
        db.execute_query("""
            INSERT INTO vm_inventory (
                vm_id, subscription_id, name, resource_group, location, size,
                power_state, os_type, priority, tags, cpu_timeseries, discovered_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"{name}_id", "sub1", name, "rg1", "eastus", "Standard_B1s",
            "running", "Linux", "Regular", "{}", "[]", datetime.now(timezone.utc)
        ))

    # Sort by name ascending (default)
    results = get_vms_filtered(sort="name", order="asc")
    assert len(results) == 3
    assert results[0]["name"] == "alpha"
    assert results[1]["name"] == "bravo"
    assert results[2]["name"] == "charlie"


def test_sort_by_name_descending(test_db):
    """Test sorting VMs by name in descending order."""
    db = DuckDBManager()

    for name in ["charlie", "alpha", "bravo"]:
        db.execute_query("""
            INSERT INTO vm_inventory (
                vm_id, subscription_id, name, resource_group, location, size,
                power_state, os_type, priority, tags, cpu_timeseries, discovered_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"{name}_id", "sub1", name, "rg1", "eastus", "Standard_B1s",
            "running", "Linux", "Regular", "{}", "[]", datetime.now(timezone.utc)
        ))

    # Sort by name descending
    results = get_vms_filtered(sort="name", order="desc")
    assert len(results) == 3
    assert results[0]["name"] == "charlie"
    assert results[1]["name"] == "bravo"
    assert results[2]["name"] == "alpha"


def test_sort_by_location(test_db):
    """Test sorting VMs by location."""
    db = DuckDBManager()

    locations = ["westus", "eastus", "centralus"]
    for i, location in enumerate(locations):
        db.execute_query("""
            INSERT INTO vm_inventory (
                vm_id, subscription_id, name, resource_group, location, size,
                power_state, os_type, priority, tags, cpu_timeseries, discovered_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"vm{i}_id", "sub1", f"vm{i}", "rg1", location, "Standard_B1s",
            "running", "Linux", "Regular", "{}", "[]", datetime.now(timezone.utc)
        ))

    # Sort by location
    results = get_vms_filtered(sort="location", order="asc")
    assert len(results) == 3
    assert results[0]["location"] == "centralus"
    assert results[1]["location"] == "eastus"
    assert results[2]["location"] == "westus"


def test_sort_by_power_state(test_db):
    """Test sorting VMs by power state."""
    db = DuckDBManager()

    power_states = [("vm1", "stopped"), ("vm2", "deallocated"), ("vm3", "running")]
    for name, power_state in power_states:
        db.execute_query("""
            INSERT INTO vm_inventory (
                vm_id, subscription_id, name, resource_group, location, size,
                power_state, os_type, priority, tags, cpu_timeseries, discovered_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"{name}_id", "sub1", name, "rg1", "eastus", "Standard_B1s",
            power_state, "Linux", "Regular", "{}", "[]", datetime.now(timezone.utc)
        ))

    # Sort by power_state
    results = get_vms_filtered(sort="power_state", order="asc")
    assert len(results) == 3
    assert results[0]["power_state"] == "deallocated"
    assert results[1]["power_state"] == "running"
    assert results[2]["power_state"] == "stopped"


def test_sort_by_size(test_db):
    """Test sorting VMs by size."""
    db = DuckDBManager()

    sizes = [("vm1", "Standard_D4s_v3"), ("vm2", "Standard_B1s"), ("vm3", "Standard_D2s_v3")]
    for name, size in sizes:
        db.execute_query("""
            INSERT INTO vm_inventory (
                vm_id, subscription_id, name, resource_group, location, size,
                power_state, os_type, priority, tags, cpu_timeseries, discovered_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"{name}_id", "sub1", name, "rg1", "eastus", size,
            "running", "Linux", "Regular", "{}", "[]", datetime.now(timezone.utc)
        ))

    # Sort by size
    results = get_vms_filtered(sort="size", order="asc")
    assert len(results) == 3
    assert results[0]["size"] == "Standard_B1s"
    assert results[1]["size"] == "Standard_D2s_v3"
    assert results[2]["size"] == "Standard_D4s_v3"


def test_sort_by_discovered_at(test_db):
    """Test sorting VMs by discovered_at date."""
    db = DuckDBManager()

    # Insert VMs with different discovery dates
    three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
    two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
    one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)

    vms = [("vm1", three_days_ago), ("vm2", one_day_ago), ("vm3", two_days_ago)]
    for name, discovered_at in vms:
        db.execute_query("""
            INSERT INTO vm_inventory (
                vm_id, subscription_id, name, resource_group, location, size,
                power_state, os_type, priority, tags, cpu_timeseries, discovered_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"{name}_id", "sub1", name, "rg1", "eastus", "Standard_B1s",
            "running", "Linux", "Regular", "{}", "[]", discovered_at
        ))

    # Sort by discovered_at ascending (oldest first)
    results = get_vms_filtered(sort="discovered_at", order="asc")
    assert len(results) == 3
    assert results[0]["name"] == "vm1"  # 3 days ago
    assert results[1]["name"] == "vm3"  # 2 days ago
    assert results[2]["name"] == "vm2"  # 1 day ago

    # Sort by discovered_at descending (newest first)
    results = get_vms_filtered(sort="discovered_at", order="desc")
    assert len(results) == 3
    assert results[0]["name"] == "vm2"  # 1 day ago
    assert results[1]["name"] == "vm3"  # 2 days ago
    assert results[2]["name"] == "vm1"  # 3 days ago


def test_sort_by_resource_group(test_db):
    """Test sorting VMs by resource group."""
    db = DuckDBManager()

    resource_groups = [("vm1", "prod-rg"), ("vm2", "dev-rg"), ("vm3", "test-rg")]
    for name, rg in resource_groups:
        db.execute_query("""
            INSERT INTO vm_inventory (
                vm_id, subscription_id, name, resource_group, location, size,
                power_state, os_type, priority, tags, cpu_timeseries, discovered_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"{name}_id", "sub1", name, rg, "eastus", "Standard_B1s",
            "running", "Linux", "Regular", "{}", "[]", datetime.now(timezone.utc)
        ))

    # Sort by resource_group
    results = get_vms_filtered(sort="resource_group", order="asc")
    assert len(results) == 3
    assert results[0]["resource_group"] == "dev-rg"
    assert results[1]["resource_group"] == "prod-rg"
    assert results[2]["resource_group"] == "test-rg"


def test_sort_with_filters(test_db):
    """Test sorting combined with filters."""
    db = DuckDBManager()

    # Insert VMs with different attributes
    vms = [
        ("vm1", "prod-rg", "eastus", "running"),
        ("vm2", "prod-rg", "westus", "running"),
        ("vm3", "dev-rg", "eastus", "stopped"),
    ]
    for name, rg, location, power_state in vms:
        db.execute_query("""
            INSERT INTO vm_inventory (
                vm_id, subscription_id, name, resource_group, location, size,
                power_state, os_type, priority, tags, cpu_timeseries, discovered_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"{name}_id", "sub1", name, rg, location, "Standard_B1s",
            power_state, "Linux", "Regular", "{}", "[]", datetime.now(timezone.utc)
        ))

    # Filter by resource_group=prod-rg and sort by location
    results = get_vms_filtered(
        resource_group="prod-rg",
        sort="location",
        order="asc"
    )
    assert len(results) == 2
    assert results[0]["location"] == "eastus"
    assert results[1]["location"] == "westus"


def test_sort_invalid_field_uses_default(test_db):
    """Test that invalid sort field falls back to default (name)."""
    db = DuckDBManager()

    for name in ["charlie", "alpha", "bravo"]:
        db.execute_query("""
            INSERT INTO vm_inventory (
                vm_id, subscription_id, name, resource_group, location, size,
                power_state, os_type, priority, tags, cpu_timeseries, discovered_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"{name}_id", "sub1", name, "rg1", "eastus", "Standard_B1s",
            "running", "Linux", "Regular", "{}", "[]", datetime.now(timezone.utc)
        ))

    # Invalid sort field should fall back to name
    results = get_vms_filtered(sort="invalid_field", order="asc")
    assert len(results) == 3
    assert results[0]["name"] == "alpha"  # Sorted by name (default)
    assert results[1]["name"] == "bravo"
    assert results[2]["name"] == "charlie"


def test_default_sort_is_name_ascending(test_db):
    """Test that default sort is by name ascending."""
    db = DuckDBManager()

    for name in ["zebra", "apple", "mango"]:
        db.execute_query("""
            INSERT INTO vm_inventory (
                vm_id, subscription_id, name, resource_group, location, size,
                power_state, os_type, priority, tags, cpu_timeseries, discovered_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"{name}_id", "sub1", name, "rg1", "eastus", "Standard_B1s",
            "running", "Linux", "Regular", "{}", "[]", datetime.now(timezone.utc)
        ))

    # No sort specified, should default to name ascending
    results = get_vms_filtered()
    assert len(results) == 3
    assert results[0]["name"] == "apple"
    assert results[1]["name"] == "mango"
    assert results[2]["name"] == "zebra"
