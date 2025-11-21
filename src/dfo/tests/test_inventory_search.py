"""Tests for inventory search functionality."""

from datetime import datetime, timezone
from dfo.inventory.queries import search_vms
from dfo.db.duck import DuckDBManager


def test_search_vms_by_name(test_db):
    """Test searching VMs by name."""
    db = DuckDBManager()

    # Insert test data
    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm1_id", "sub1", "prod-web-01", "rg1", "eastus", "Standard_B1s",
        "running", "Linux", "Regular", "{}", "[]", datetime.now(timezone.utc)
    ))

    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm2_id", "sub2", "prod-api-01", "rg2", "westus", "Standard_D2s_v3",
        "stopped", "Windows", "Regular", "{}", "[]", datetime.now(timezone.utc)
    ))

    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm3_id", "sub3", "dev-web-01", "rg3", "eastus", "Standard_B1s",
        "running", "Linux", "Regular", "{}", "[]", datetime.now(timezone.utc)
    ))

    # Search for "prod"
    results = search_vms("prod")
    assert len(results) == 2
    assert all("prod" in vm["name"] for vm in results)


def test_search_vms_by_resource_group(test_db):
    """Test searching VMs by resource group."""
    db = DuckDBManager()

    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm1_id", "sub1", "vm1", "production-rg", "eastus", "Standard_B1s",
        "running", "Linux", "Regular", "{}", "[]", datetime.now(timezone.utc)
    ))

    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm2_id", "sub2", "vm2", "development-rg", "westus", "Standard_D2s_v3",
        "stopped", "Windows", "Regular", "{}", "[]", datetime.now(timezone.utc)
    ))

    # Search for "production"
    results = search_vms("production")
    assert len(results) == 1
    assert results[0]["resource_group"] == "production-rg"


def test_search_vms_wildcard_pattern(test_db):
    """Test searching with wildcard patterns."""
    db = DuckDBManager()

    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm1_id", "sub1", "prod-web-01", "rg1", "eastus", "Standard_B1s",
        "running", "Linux", "Regular", "{}", "[]", datetime.now(timezone.utc)
    ))

    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm2_id", "sub2", "prod-api-01", "rg2", "westus", "Standard_D2s_v3",
        "stopped", "Windows", "Regular", "{}", "[]", datetime.now(timezone.utc)
    ))

    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm3_id", "sub3", "staging-web-01", "rg3", "eastus", "Standard_B1s",
        "running", "Linux", "Regular", "{}", "[]", datetime.now(timezone.utc)
    ))

    # Search with wildcard: "prod-*"
    results = search_vms("prod-*")
    assert len(results) == 2
    assert all(vm["name"].startswith("prod-") for vm in results)


def test_search_vms_case_insensitive(test_db):
    """Test case-insensitive search."""
    db = DuckDBManager()

    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm1_id", "sub1", "PROD-WEB-01", "rg1", "eastus", "Standard_B1s",
        "running", "Linux", "Regular", "{}", "[]", datetime.now(timezone.utc)
    ))

    # Search with lowercase should match uppercase
    results = search_vms("prod")
    assert len(results) == 1
    assert results[0]["name"] == "PROD-WEB-01"

    # Search with uppercase should match lowercase in database
    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm2_id", "sub2", "dev-api-01", "rg2", "westus", "Standard_D2s_v3",
        "stopped", "Windows", "Regular", "{}", "[]", datetime.now(timezone.utc)
    ))

    results = search_vms("DEV")
    assert len(results) == 1
    assert results[0]["name"] == "dev-api-01"


def test_search_vms_with_filters(test_db):
    """Test search with additional filters."""
    db = DuckDBManager()

    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm1_id", "sub1", "prod-web-01", "rg1", "eastus", "Standard_B1s",
        "running", "Linux", "Regular", "{}", "[]", datetime.now(timezone.utc)
    ))

    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm2_id", "sub2", "prod-api-01", "rg2", "westus", "Standard_D2s_v3",
        "stopped", "Windows", "Regular", "{}", "[]", datetime.now(timezone.utc)
    ))

    # Search with power_state filter
    results = search_vms("prod", power_state="running")
    assert len(results) == 1
    assert results[0]["name"] == "prod-web-01"

    # Search with location filter
    results = search_vms("prod", location="westus")
    assert len(results) == 1
    assert results[0]["name"] == "prod-api-01"


def test_search_vms_with_limit(test_db):
    """Test search with result limit."""
    db = DuckDBManager()

    for i in range(5):
        db.execute_query("""
            INSERT INTO vm_inventory (
                vm_id, subscription_id, name, resource_group, location, size,
                power_state, os_type, priority, tags, cpu_timeseries, discovered_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"vm{i}_id", "sub1", f"prod-vm-{i:02d}", "rg1", "eastus", "Standard_B1s",
            "running", "Linux", "Regular", "{}", "[]", datetime.now(timezone.utc)
        ))

    # Search with limit
    results = search_vms("prod", limit=3)
    assert len(results) == 3


def test_search_vms_no_results(test_db):
    """Test search with no matching results."""
    db = DuckDBManager()

    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm1_id", "sub1", "dev-web-01", "rg1", "eastus", "Standard_B1s",
        "running", "Linux", "Regular", "{}", "[]", datetime.now(timezone.utc)
    ))

    # Search for non-existent pattern
    results = search_vms("nonexistent")
    assert len(results) == 0


def test_search_vms_by_tags(test_db):
    """Test searching VMs by tags."""
    db = DuckDBManager()

    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm1_id", "sub1", "vm1", "rg1", "eastus", "Standard_B1s",
        "running", "Linux", "Regular", '{"env": "production", "owner": "team-a"}', "[]",
        datetime.now(timezone.utc)
    ))

    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm2_id", "sub2", "vm2", "rg2", "westus", "Standard_D2s_v3",
        "stopped", "Windows", "Regular", '{"env": "development"}', "[]",
        datetime.now(timezone.utc)
    ))

    # Search for tag value
    results = search_vms("production")
    assert len(results) == 1
    assert results[0]["name"] == "vm1"

    # Search for tag key
    results = search_vms("team-a")
    assert len(results) == 1
    assert results[0]["tags"]["owner"] == "team-a"
