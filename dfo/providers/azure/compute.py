"""Azure Compute provider operations.

This module contains Azure SDK wrappers for compute operations.

Per CODE_STYLE.md:
- This is a provider module - Azure SDK calls only
- No database operations
- No business logic (that belongs in discover/analyze layers)
"""
from typing import List, Dict, Any

# Third-party
from azure.mgmt.compute import ComputeManagementClient


def list_vms(client: ComputeManagementClient) -> List[Dict[str, Any]]:
    """List all VMs in the subscription.

    Args:
        client: ComputeManagementClient instance.

    Returns:
        List of VM dictionaries with basic metadata.

    Note:
        This is a stub implementation for Milestone 2.
        Full implementation in Milestone 3.
    """
    # Stub: return empty list
    # Milestone 3 will implement actual VM listing
    return []


def stop_vm(
    client: ComputeManagementClient,
    resource_group: str,
    vm_name: str
) -> Dict[str, Any]:
    """Stop a VM (keeps it allocated).

    Args:
        client: ComputeManagementClient instance.
        resource_group: Resource group name.
        vm_name: VM name.

    Returns:
        Operation result dictionary.

    Note:
        This is a stub implementation for Milestone 2.
        Full implementation in Milestone 6.
    """
    # Stub: return success
    return {"status": "stub", "message": "Not implemented yet"}


def deallocate_vm(
    client: ComputeManagementClient,
    resource_group: str,
    vm_name: str
) -> Dict[str, Any]:
    """Deallocate a VM (releases compute resources).

    Args:
        client: ComputeManagementClient instance.
        resource_group: Resource group name.
        vm_name: VM name.

    Returns:
        Operation result dictionary.

    Note:
        This is a stub implementation for Milestone 2.
        Full implementation in Milestone 6.
    """
    # Stub: return success
    return {"status": "stub", "message": "Not implemented yet"}
