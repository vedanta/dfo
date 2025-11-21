"""Output formatters for inventory data.

This module provides functions to format inventory data (VMs, etc.) into
various output formats like JSON and CSV.
"""

import csv
import json
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Dict, List, Optional


def format_vms_as_json(
    vms: List[Dict[str, Any]],
    filters_applied: Optional[Dict[str, Any]] = None
) -> str:
    """
    Format VMs as JSON string.

    Args:
        vms: List of VM dictionaries
        filters_applied: Optional dict of filters that were applied

    Returns:
        JSON string with metadata and VM data
    """
    output = {
        "count": len(vms),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "filters_applied": filters_applied or {},
        "vms": []
    }

    for vm in vms:
        vm_data = {
            "vm_id": vm.get("vm_id"),
            "name": vm.get("name"),
            "resource_group": vm.get("resource_group"),
            "location": vm.get("location"),
            "size": vm.get("size"),
            "power_state": vm.get("power_state"),
            "tags": vm.get("tags", {}),
            "cpu_timeseries": vm.get("cpu_timeseries", []),
            "discovered_at": vm.get("discovered_at"),
            "subscription_id": vm.get("subscription_id")
        }
        output["vms"].append(vm_data)

    return json.dumps(output, indent=2, default=str)


def format_vms_as_csv(vms: List[Dict[str, Any]]) -> str:
    """
    Format VMs as CSV string.

    Args:
        vms: List of VM dictionaries

    Returns:
        CSV string with VM data
    """
    if not vms:
        return "name,resource_group,location,size,power_state,has_metrics,discovered_at\n"

    output = StringIO()
    fieldnames = [
        "name",
        "resource_group",
        "location",
        "size",
        "power_state",
        "has_metrics",
        "discovered_at"
    ]

    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for vm in vms:
        # Determine if VM has metrics
        cpu_data = vm.get("cpu_timeseries", [])
        has_metrics = "true" if cpu_data and len(cpu_data) > 0 else "false"

        row = {
            "name": vm.get("name", ""),
            "resource_group": vm.get("resource_group", ""),
            "location": vm.get("location", ""),
            "size": vm.get("size", ""),
            "power_state": vm.get("power_state", ""),
            "has_metrics": has_metrics,
            "discovered_at": vm.get("discovered_at", "")
        }
        writer.writerow(row)

    return output.getvalue()


def format_vm_detail_as_json(vm: Dict[str, Any]) -> str:
    """
    Format single VM detail as JSON string.

    Args:
        vm: VM dictionary

    Returns:
        JSON string with complete VM data
    """
    return json.dumps(vm, indent=2, default=str)
