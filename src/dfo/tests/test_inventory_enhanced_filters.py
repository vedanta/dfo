"""Tests for enhanced inventory filtering (tags and dates)."""

from datetime import datetime, timezone, timedelta
from dfo.inventory.queries import get_vms_filtered
from dfo.db.duck import DuckDBManager


def test_filter_by_tag_key_value(test_db):
    """Test filtering VMs by tag key=value."""
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
        "stopped", "Windows", "Regular", '{"env": "development", "owner": "team-b"}', "[]",
        datetime.now(timezone.utc)
    ))

    # Filter by env=production
    results = get_vms_filtered(tag="env=production")
    assert len(results) == 1
    assert results[0]["name"] == "vm1"
    assert results[0]["tags"]["env"] == "production"

    # Filter by owner=team-b
    results = get_vms_filtered(tag="owner=team-b")
    assert len(results) == 1
    assert results[0]["name"] == "vm2"


def test_filter_by_tag_key_exists(test_db):
    """Test filtering VMs by tag key exists."""
    db = DuckDBManager()

    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm1_id", "sub1", "vm1", "rg1", "eastus", "Standard_B1s",
        "running", "Linux", "Regular", '{"env": "production", "cost-center": "eng"}', "[]",
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

    # Filter by tag_key=cost-center (only vm1 has this)
    results = get_vms_filtered(tag_key="cost-center")
    assert len(results) == 1
    assert results[0]["name"] == "vm1"

    # Filter by tag_key=env (both have this)
    results = get_vms_filtered(tag_key="env")
    assert len(results) == 2


def test_filter_by_tag_without_equals(test_db):
    """Test filtering by tag without = sign (treated as key exists)."""
    db = DuckDBManager()

    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm1_id", "sub1", "vm1", "rg1", "eastus", "Standard_B1s",
        "running", "Linux", "Regular", '{"owner": "team-a"}', "[]",
        datetime.now(timezone.utc)
    ))

    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm2_id", "sub2", "vm2", "rg2", "westus", "Standard_D2s_v3",
        "stopped", "Windows", "Regular", '{"env": "dev"}', "[]",
        datetime.now(timezone.utc)
    ))

    # Filter by tag="owner" (no =, so check key exists)
    results = get_vms_filtered(tag="owner")
    assert len(results) == 1
    assert results[0]["name"] == "vm1"


def test_filter_by_discovered_after(test_db):
    """Test filtering VMs by discovered_after date."""
    db = DuckDBManager()

    # VM discovered yesterday
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm1_id", "sub1", "vm1", "rg1", "eastus", "Standard_B1s",
        "running", "Linux", "Regular", "{}", "[]", yesterday
    ))

    # VM discovered today
    today = datetime.now(timezone.utc)
    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm2_id", "sub2", "vm2", "rg2", "westus", "Standard_D2s_v3",
        "stopped", "Windows", "Regular", "{}", "[]", today
    ))

    # Filter: discovered after yesterday (should get vm2)
    yesterday_str = yesterday.strftime("%Y-%m-%d")
    results = get_vms_filtered(discovered_after=yesterday_str)
    assert len(results) >= 1  # At least vm2
    assert any(vm["name"] == "vm2" for vm in results)


def test_filter_by_discovered_before(test_db):
    """Test filtering VMs by discovered_before date."""
    db = DuckDBManager()

    # VM discovered 3 days ago
    three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm1_id", "sub1", "vm1", "rg1", "eastus", "Standard_B1s",
        "running", "Linux", "Regular", "{}", "[]", three_days_ago
    ))

    # VM discovered today
    today = datetime.now(timezone.utc)
    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm2_id", "sub2", "vm2", "rg2", "westus", "Standard_D2s_v3",
        "stopped", "Windows", "Regular", "{}", "[]", today
    ))

    # Filter: discovered before 2 days ago (should get vm1)
    two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
    two_days_ago_str = two_days_ago.strftime("%Y-%m-%d")
    results = get_vms_filtered(discovered_before=two_days_ago_str)
    assert len(results) == 1
    assert results[0]["name"] == "vm1"


def test_filter_by_date_range(test_db):
    """Test filtering VMs by date range (after + before)."""
    db = DuckDBManager()

    # VM discovered 5 days ago
    five_days_ago = datetime.now(timezone.utc) - timedelta(days=5)
    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm1_id", "sub1", "vm1", "rg1", "eastus", "Standard_B1s",
        "running", "Linux", "Regular", "{}", "[]", five_days_ago
    ))

    # VM discovered 3 days ago
    three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm2_id", "sub2", "vm2", "rg2", "westus", "Standard_D2s_v3",
        "stopped", "Windows", "Regular", "{}", "[]", three_days_ago
    ))

    # VM discovered today
    today = datetime.now(timezone.utc)
    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm3_id", "sub3", "vm3", "rg3", "centralus", "Standard_B2s",
        "running", "Linux", "Regular", "{}", "[]", today
    ))

    # Filter: discovered between 4 days ago and 2 days ago (should get vm2)
    four_days_ago = datetime.now(timezone.utc) - timedelta(days=4)
    two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)

    results = get_vms_filtered(
        discovered_after=four_days_ago.strftime("%Y-%m-%d"),
        discovered_before=two_days_ago.strftime("%Y-%m-%d")
    )
    assert len(results) == 1
    assert results[0]["name"] == "vm2"


def test_filter_combined_tag_and_location(test_db):
    """Test combining tag filter with other filters."""
    db = DuckDBManager()

    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm1_id", "sub1", "vm1", "rg1", "eastus", "Standard_B1s",
        "running", "Linux", "Regular", '{"env": "production"}', "[]",
        datetime.now(timezone.utc)
    ))

    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm2_id", "sub2", "vm2", "rg2", "westus", "Standard_D2s_v3",
        "stopped", "Windows", "Regular", '{"env": "production"}', "[]",
        datetime.now(timezone.utc)
    ))

    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm3_id", "sub3", "vm3", "rg3", "eastus", "Standard_B2s",
        "running", "Linux", "Regular", '{"env": "development"}', "[]",
        datetime.now(timezone.utc)
    ))

    # Filter: env=production AND location=eastus (should get vm1)
    results = get_vms_filtered(tag="env=production", location="eastus")
    assert len(results) == 1
    assert results[0]["name"] == "vm1"


def test_filter_no_matching_tags(test_db):
    """Test filtering with tag that doesn't exist."""
    db = DuckDBManager()

    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm1_id", "sub1", "vm1", "rg1", "eastus", "Standard_B1s",
        "running", "Linux", "Regular", '{"env": "production"}', "[]",
        datetime.now(timezone.utc)
    ))

    # Filter by non-existent tag
    results = get_vms_filtered(tag="owner=nobody")
    assert len(results) == 0

    # Filter by non-existent tag key
    results = get_vms_filtered(tag_key="nonexistent")
    assert len(results) == 0


def test_filter_vms_without_tags(test_db):
    """Test filtering VMs that have empty tags."""
    db = DuckDBManager()

    # VM with tags
    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm1_id", "sub1", "vm1", "rg1", "eastus", "Standard_B1s",
        "running", "Linux", "Regular", '{"env": "production"}', "[]",
        datetime.now(timezone.utc)
    ))

    # VM without tags
    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm2_id", "sub2", "vm2", "rg2", "westus", "Standard_D2s_v3",
        "stopped", "Windows", "Regular", '{}', "[]",
        datetime.now(timezone.utc)
    ))

    # Filter by tag - should only get vm1
    results = get_vms_filtered(tag="env=production")
    assert len(results) == 1
    assert results[0]["name"] == "vm1"


def test_filter_combined_all_filters(test_db):
    """Test combining all filter types together."""
    db = DuckDBManager()

    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm1_id", "sub1", "vm1", "prod-rg", "eastus", "Standard_B1s",
        "running", "Linux", "Regular", '{"env": "production", "owner": "team-a"}', "[]",
        yesterday
    ))

    today = datetime.now(timezone.utc)
    db.execute_query("""
        INSERT INTO vm_inventory (
            vm_id, subscription_id, name, resource_group, location, size,
            power_state, os_type, priority, tags, cpu_timeseries, discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "vm2_id", "sub2", "vm2", "prod-rg", "eastus", "Standard_B1s",
        "running", "Linux", "Regular", '{"env": "production", "owner": "team-b"}', "[]",
        today
    ))

    # Combine: resource_group, location, power_state, size, tag, date
    yesterday_str = yesterday.strftime("%Y-%m-%d")
    results = get_vms_filtered(
        resource_group="prod-rg",
        location="eastus",
        power_state="running",
        size="Standard_B1s",
        tag="env=production",
        discovered_before=yesterday_str
    )
    # At least vm1 should be in results, vm2 might be included depending on date comparison
    assert len(results) >= 1
    assert any(vm["name"] == "vm1" for vm in results)
