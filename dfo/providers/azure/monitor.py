"""Azure Monitor provider operations.

This module contains Azure SDK wrappers for Monitor/metrics operations.

Per CODE_STYLE.md:
- This is a provider module - Azure SDK calls only
- No database operations
- No business logic
"""
from typing import List, Dict, Any

# Third-party
from azure.mgmt.monitor import MonitorManagementClient


def get_cpu_metrics(
    client: MonitorManagementClient,
    resource_id: str,
    days: int = 14
) -> List[Dict[str, Any]]:
    """Get CPU metrics for a VM.

    Args:
        client: MonitorManagementClient instance.
        resource_id: Full Azure resource ID of the VM.
        days: Number of days of metrics to retrieve.

    Returns:
        List of metric data points with timestamps and values.

    Note:
        This is a stub implementation for Milestone 2.
        Full implementation in Milestone 3.
    """
    # Stub: return empty list
    # Milestone 3 will implement actual metric retrieval
    return []
