"""VM discovery orchestration using rules engine.

This module orchestrates VM discovery workflow:
1. List all VMs via compute provider
2. Retrieve CPU metrics via monitor provider (using rule-defined period)
3. Transform to VMInventory models
4. Batch insert to database

Per CODE_STYLE.md:
- This is a discovery module - orchestration only
- Uses provider layer for Azure SDK calls
- Uses db layer for persistence
- Business logic only, no direct Azure SDK calls
"""
from typing import List, Optional
from datetime import datetime

# Internal
from dfo.core.config import get_settings
from dfo.core.auth import get_cached_credential
from dfo.core.models import VMInventory
from dfo.providers.azure.client import get_compute_client, get_monitor_client
from dfo.providers.azure.compute import list_vms
from dfo.providers.azure.monitor import get_cpu_metrics
from dfo.db.duck import get_db
from dfo.rules import get_rule_engine


def discover_vms(
    subscription_id: Optional[str] = None,
    refresh: bool = True
) -> List[VMInventory]:
    """Discover Azure VMs using rules-driven metric collection.

    Args:
        subscription_id: Azure subscription ID (uses config default if None).
        refresh: If True, clear existing inventory before inserting new data.

    Returns:
        List of discovered VMInventory objects.

    Raises:
        Exception: If discovery or database operations fail.
    """
    # Get configuration
    settings = get_settings()
    sub_id = subscription_id or settings.azure_subscription_id

    # Load rules engine to determine collection period
    rule_engine = get_rule_engine()
    idle_rule = rule_engine.get_rule_by_type("Idle VM Detection")

    # Determine collection period from rule (with config override)
    # Rule default: 7d, but user can override with DFO_IDLE_DAYS
    collection_days = idle_rule.period_days if idle_rule else settings.dfo_idle_days

    # Get Azure clients
    credential = get_cached_credential()
    compute_client = get_compute_client(sub_id, credential)
    monitor_client = get_monitor_client(sub_id, credential)

    # Get database manager
    db = get_db()

    # Clear existing inventory if refresh mode
    if refresh:
        db.clear_table("vm_inventory")

    # Discover VMs
    vms_data = list_vms(compute_client)

    # Build inventory with metrics
    inventory = []
    for vm_data in vms_data:
        try:
            # Get CPU metrics using rule-defined period
            cpu_metrics = get_cpu_metrics(
                monitor_client,
                vm_data["vm_id"],
                days=collection_days  # Uses rule period (7d) or user override
            )

            # Create VMInventory model
            vm_inventory = VMInventory(
                vm_id=vm_data["vm_id"],
                name=vm_data["name"],
                resource_group=vm_data["resource_group"],
                location=vm_data["location"],
                size=vm_data["size"],
                power_state=vm_data["power_state"],
                tags=vm_data["tags"],
                cpu_timeseries=cpu_metrics,
                discovered_at=datetime.utcnow()
            )

            inventory.append(vm_inventory)

        except Exception as e:
            # Log error but continue with other VMs
            # This ensures partial failures don't stop entire discovery
            print(f"Warning: Failed to get metrics for {vm_data['name']}: {e}")

            # Still add VM without metrics
            vm_inventory = VMInventory(
                vm_id=vm_data["vm_id"],
                name=vm_data["name"],
                resource_group=vm_data["resource_group"],
                location=vm_data["location"],
                size=vm_data["size"],
                power_state=vm_data["power_state"],
                tags=vm_data["tags"],
                cpu_timeseries=[],  # Empty metrics
                discovered_at=datetime.utcnow()
            )
            inventory.append(vm_inventory)

    # Insert into database
    if inventory:
        records = [vm.to_db_record() for vm in inventory]
        db.insert_records("vm_inventory", records)

    return inventory
