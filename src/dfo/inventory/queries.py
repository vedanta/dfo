"""Inventory query helpers.

This module provides high-level query functions for retrieving
discovered resources from the database.
"""
from typing import List, Dict, Any, Optional
import json

# Internal
from dfo.db.duck import DuckDBManager


def get_all_vms() -> List[Dict[str, Any]]:
    """Get all VMs from inventory.

    Returns:
        List of VM records with deserialized JSON fields.
    """
    db = DuckDBManager()
    rows = db.query("SELECT * FROM vm_inventory ORDER BY name")
    return _deserialize_vm_records(rows)


def get_vm_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Get specific VM by name.

    Args:
        name: VM name to search for.

    Returns:
        VM record if found, None otherwise.
    """
    db = DuckDBManager()
    rows = db.query(
        "SELECT * FROM vm_inventory WHERE name = ?",
        [name]
    )

    if not rows:
        return None

    deserialized = _deserialize_vm_records(rows)
    return deserialized[0] if deserialized else None


def get_vms_filtered(
    resource_group: Optional[str] = None,
    location: Optional[str] = None,
    power_state: Optional[str] = None,
    size: Optional[str] = None,
    tag: Optional[str] = None,
    tag_key: Optional[str] = None,
    discovered_after: Optional[str] = None,
    discovered_before: Optional[str] = None,
    sort: Optional[str] = None,
    order: Optional[str] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Get filtered VMs from inventory.

    Args:
        resource_group: Filter by resource group.
        location: Filter by location.
        power_state: Filter by power state.
        size: Filter by VM size.
        tag: Filter by tag (key=value format).
        tag_key: Filter by tag key exists.
        discovered_after: Filter by discovery date (YYYY-MM-DD format).
        discovered_before: Filter by discovery date (YYYY-MM-DD format).
        sort: Sort by field (name, resource_group, location, size, power_state, discovered_at).
        order: Sort order (asc or desc). Default: asc.
        limit: Maximum number of results.

    Returns:
        List of matching VM records.
    """
    db = DuckDBManager()

    # Build query dynamically
    conditions = []
    params = []

    if resource_group:
        conditions.append("resource_group = ?")
        params.append(resource_group)

    if location:
        conditions.append("location = ?")
        params.append(location)

    if power_state:
        conditions.append("power_state = ?")
        params.append(power_state)

    if size:
        conditions.append("size = ?")
        params.append(size)

    # Tag filtering (key=value)
    if tag:
        if "=" in tag:
            tag_key_part, tag_value = tag.split("=", 1)
            # DuckDB JSON extraction: json_extract(tags, '$.key') = 'value'
            conditions.append(f"json_extract_string(tags, '$.{tag_key_part}') = ?")
            params.append(tag_value)
        else:
            # If no =, treat as tag key exists check
            conditions.append(f"json_extract_string(tags, '$.{tag}') IS NOT NULL")

    # Tag key filtering (key exists)
    if tag_key:
        conditions.append(f"json_extract_string(tags, '$.{tag_key}') IS NOT NULL")

    # Date filtering
    if discovered_after:
        conditions.append("DATE(discovered_at) >= ?")
        params.append(discovered_after)

    if discovered_before:
        conditions.append("DATE(discovered_at) <= ?")
        params.append(discovered_before)

    query = "SELECT * FROM vm_inventory"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    # Sorting
    valid_sort_fields = ["name", "resource_group", "location", "size", "power_state", "discovered_at"]
    sort_field = "name"  # default
    sort_order = "ASC"  # default

    if sort:
        if sort in valid_sort_fields:
            sort_field = sort
        else:
            # Invalid sort field, use default
            sort_field = "name"

    if order:
        if order.lower() in ["asc", "desc"]:
            sort_order = order.upper()

    query += f" ORDER BY {sort_field} {sort_order}"

    if limit:
        query += f" LIMIT {limit}"

    rows = db.query(query, params if params else None)
    return _deserialize_vm_records(rows)


def get_vm_count_by_power_state() -> Dict[str, int]:
    """Get VM counts grouped by power state.

    Returns:
        Dict mapping power state to count.
    """
    db = DuckDBManager()
    rows = db.query(
        "SELECT power_state, COUNT(*) as count "
        "FROM vm_inventory "
        "GROUP BY power_state "
        "ORDER BY count DESC"
    )

    return {row[0]: row[1] for row in rows}


def get_vm_count_by_location() -> Dict[str, int]:
    """Get VM counts grouped by location.

    Returns:
        Dict mapping location to count.
    """
    db = DuckDBManager()
    rows = db.query(
        "SELECT location, COUNT(*) as count "
        "FROM vm_inventory "
        "GROUP BY location "
        "ORDER BY count DESC"
    )

    return {row[0]: row[1] for row in rows}


def search_vms(
    query: str,
    resource_group: Optional[str] = None,
    location: Optional[str] = None,
    power_state: Optional[str] = None,
    size: Optional[str] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Search VMs by name, resource group, or tags.

    Performs case-insensitive search across VM fields. Supports
    wildcard patterns with * character.

    Args:
        query: Search query string (supports * wildcard).
        resource_group: Optional filter by resource group.
        location: Optional filter by location.
        power_state: Optional filter by power state.
        size: Optional filter by VM size.
        limit: Maximum number of results.

    Returns:
        List of matching VM records.
    """
    db = DuckDBManager()

    # Convert wildcard pattern (* to %)
    search_pattern = query.replace('*', '%').lower()

    # Build search conditions (case-insensitive LIKE)
    search_conditions = [
        "LOWER(name) LIKE ?",
        "LOWER(resource_group) LIKE ?",
        "LOWER(tags) LIKE ?"
    ]

    # Build additional filter conditions
    filter_conditions = []
    params = []

    # Add search pattern for each field
    for _ in search_conditions:
        params.append(f"%{search_pattern}%")

    if resource_group:
        filter_conditions.append("resource_group = ?")
        params.append(resource_group)

    if location:
        filter_conditions.append("location = ?")
        params.append(location)

    if power_state:
        filter_conditions.append("power_state = ?")
        params.append(power_state)

    if size:
        filter_conditions.append("size = ?")
        params.append(size)

    # Build final query
    sql = "SELECT * FROM vm_inventory WHERE "
    sql += "(" + " OR ".join(search_conditions) + ")"

    if filter_conditions:
        sql += " AND " + " AND ".join(filter_conditions)

    sql += " ORDER BY name"

    if limit:
        sql += f" LIMIT {limit}"

    rows = db.query(sql, params)
    return _deserialize_vm_records(rows)


def _deserialize_vm_records(rows: List[tuple]) -> List[Dict[str, Any]]:
    """Deserialize JSON fields in VM records.

    Args:
        rows: Raw database rows.

    Returns:
        List of VM records with deserialized JSON fields.
    """
    if not rows:
        return []

    # Column names from schema: vm_id, subscription_id, name, resource_group,
    # location, size, power_state, tags, cpu_timeseries, discovered_at
    columns = [
        "vm_id", "subscription_id", "name", "resource_group",
        "location", "size", "power_state", "tags",
        "cpu_timeseries", "discovered_at"
    ]

    records = []
    for row in rows:
        record = dict(zip(columns, row))

        # Deserialize JSON fields
        if record.get("tags"):
            try:
                record["tags"] = json.loads(record["tags"])
            except (json.JSONDecodeError, TypeError):
                record["tags"] = {}

        if record.get("cpu_timeseries"):
            try:
                record["cpu_timeseries"] = json.loads(record["cpu_timeseries"])
            except (json.JSONDecodeError, TypeError):
                record["cpu_timeseries"] = []

        records.append(record)

    return records
