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
        List of VM dictionaries with metadata:
        - vm_id: Full Azure resource ID
        - name: VM name
        - resource_group: Resource group name
        - location: Azure region
        - size: VM size (e.g., "Standard_D2s_v3")
        - power_state: Current power state (running/stopped/deallocated/unknown)
        - tags: Resource tags dict

    Raises:
        Exception: If Azure API call fails.
    """
    vms = []

    # List all VMs across subscription
    for vm in client.virtual_machines.list_all():
        # Extract resource group from resource ID
        # Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Compute/virtualMachines/{name}
        resource_group = vm.id.split('/')[4]

        # Get instance view for power state
        try:
            instance_view = client.virtual_machines.instance_view(
                resource_group_name=resource_group,
                vm_name=vm.name
            )

            # Extract power state from statuses
            power_state = "unknown"
            if instance_view.statuses:
                for status in instance_view.statuses:
                    if status.code and status.code.startswith('PowerState/'):
                        power_state = status.code.split('/')[-1].lower()
                        break
        except Exception:
            # If instance view fails, continue with unknown power state
            power_state = "unknown"

        vms.append({
            "vm_id": vm.id,
            "name": vm.name,
            "resource_group": resource_group,
            "location": vm.location,
            "size": vm.hardware_profile.vm_size,
            "power_state": power_state,
            "tags": vm.tags or {}
        })

    return vms


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
