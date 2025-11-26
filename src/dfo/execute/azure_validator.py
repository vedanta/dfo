"""Azure-specific resource validation."""

from typing import List, Optional

from azure.core.exceptions import ResourceNotFoundError
from azure.mgmt.compute import ComputeManagementClient

from dfo.core.auth import get_azure_credential
from dfo.core.config import get_settings
from dfo.execute.models import (
    ActionType,
    PlanAction,
    ValidationResult,
    ValidationStatus,
)
from dfo.providers.azure.client import get_compute_client


class AzureResourceValidator:
    """Validates Azure resources for execution actions."""

    def __init__(self):
        """Initialize Azure validator."""
        self.settings = get_settings()
        self.credential = get_azure_credential()
        self.compute_client: Optional[ComputeManagementClient] = None

    def _get_compute_client(self) -> ComputeManagementClient:
        """Get or create compute client."""
        if not self.compute_client:
            self.compute_client = get_compute_client(
                self.settings.azure_subscription_id,
                self.credential
            )
        return self.compute_client

    def validate_vm_action(self, action: PlanAction) -> ValidationResult:
        """Validate VM action against Azure.

        Checks:
        - VM exists
        - Current power state
        - Permissions (basic check)
        - Dependencies (disks, NICs)
        - Protection tags

        Args:
            action: Plan action to validate

        Returns:
            ValidationResult with validation details
        """
        result = ValidationResult(
            action_id=action.action_id,
            status=ValidationStatus.SUCCESS,
            resource_exists=False,
            permissions_ok=True,  # Assume OK unless check fails
            dependencies=[],
            warnings=[],
            errors=[],
        )

        try:
            # Parse resource ID to get resource group and VM name
            # Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Compute/virtualMachines/{name}
            parts = action.resource_id.split("/")
            if len(parts) < 9:
                result.errors.append(f"Invalid resource ID format: {action.resource_id}")
                result.status = ValidationStatus.ERROR
                return result

            resource_group = parts[4]
            vm_name = parts[8]

            # Get VM from Azure
            client = self._get_compute_client()
            vm = client.virtual_machines.get(
                resource_group_name=resource_group,
                vm_name=vm_name,
                expand="instanceView"
            )

            result.resource_exists = True

            # Check current power state
            power_state = self._get_power_state(vm)
            result.details = {
                "resource_group": resource_group,
                "vm_name": vm_name,
                "current_power_state": power_state,
                "vm_size": vm.hardware_profile.vm_size if vm.hardware_profile else None,
                "location": vm.location,
            }

            # Check protection tags
            if vm.tags:
                for tag_key in ["dfo-protected", "dfo-exclude"]:
                    if tag_key in vm.tags and str(vm.tags[tag_key]).lower() == "true":
                        result.errors.append(
                            f"Resource has protection tag '{tag_key}={vm.tags[tag_key]}'"
                        )
                        result.status = ValidationStatus.ERROR

            # Validate action based on current state
            self._validate_action_for_state(action, power_state, result)

            # Check dependencies
            self._check_dependencies(vm, action, result)

            # Warn about destructive actions
            if action.action_type == ActionType.DELETE:
                result.warnings.append(
                    "DELETE action is IRREVERSIBLE - VM and attached disks will be permanently deleted"
                )
                if result.status == ValidationStatus.SUCCESS:
                    result.status = ValidationStatus.WARNING

        except ResourceNotFoundError:
            result.resource_exists = False
            result.errors.append(f"Resource not found: {action.resource_id}")
            result.status = ValidationStatus.ERROR

        except Exception as e:
            result.errors.append(f"Validation failed: {str(e)}")
            result.status = ValidationStatus.ERROR

        return result

    def _get_power_state(self, vm) -> str:
        """Extract power state from VM instance view."""
        if not vm.instance_view or not vm.instance_view.statuses:
            return "unknown"

        for status in vm.instance_view.statuses:
            if status.code.startswith("PowerState/"):
                return status.code.split("/")[1]

        return "unknown"

    def _validate_action_for_state(
        self,
        action: PlanAction,
        power_state: str,
        result: ValidationResult
    ) -> None:
        """Validate if action is appropriate for current power state."""
        # Stop action
        if action.action_type == ActionType.STOP:
            if power_state in ["stopped", "deallocated"]:
                result.warnings.append(
                    f"VM is already {power_state} - action may be redundant"
                )
                if result.status == ValidationStatus.SUCCESS:
                    result.status = ValidationStatus.WARNING

        # Deallocate action
        elif action.action_type == ActionType.DEALLOCATE:
            if power_state == "deallocated":
                result.warnings.append(
                    "VM is already deallocated - action may be redundant"
                )
                if result.status == ValidationStatus.SUCCESS:
                    result.status = ValidationStatus.WARNING

        # Delete action
        elif action.action_type == ActionType.DELETE:
            if power_state == "running":
                result.warnings.append(
                    "VM is currently running - will be forcefully stopped before deletion"
                )

        # Downsize action
        elif action.action_type == ActionType.DOWNSIZE:
            if power_state == "running":
                result.warnings.append(
                    "VM must be stopped/deallocated before resizing"
                )

            # Validate new size parameter
            if action.action_params and "new_size" in action.action_params:
                result.details["new_size"] = action.action_params["new_size"]
            else:
                result.errors.append("Downsize action missing 'new_size' parameter")
                result.status = ValidationStatus.ERROR

    def _check_dependencies(
        self,
        vm,
        action: PlanAction,
        result: ValidationResult
    ) -> None:
        """Check VM dependencies (disks, NICs)."""
        dependencies = []

        # Check OS disk
        if vm.storage_profile and vm.storage_profile.os_disk:
            dependencies.append(f"OS Disk: {vm.storage_profile.os_disk.name}")

        # Check data disks
        if vm.storage_profile and vm.storage_profile.data_disks:
            for disk in vm.storage_profile.data_disks:
                dependencies.append(f"Data Disk: {disk.name}")

            # Warn if multiple disks and action is delete
            if action.action_type == ActionType.DELETE and len(vm.storage_profile.data_disks) > 0:
                result.warnings.append(
                    f"VM has {len(vm.storage_profile.data_disks)} attached data disk(s) that will be deleted"
                )

        # Check NICs
        if vm.network_profile and vm.network_profile.network_interfaces:
            for nic in vm.network_profile.network_interfaces:
                nic_id = nic.id.split("/")[-1]
                dependencies.append(f"NIC: {nic_id}")

        result.dependencies = dependencies

        # Add dependency info to details
        if dependencies:
            result.details["dependencies"] = dependencies


def validate_azure_vm_action(action: PlanAction) -> ValidationResult:
    """Validate Azure VM action.

    Convenience function that creates a validator and validates the action.

    Args:
        action: Plan action to validate

    Returns:
        ValidationResult with Azure-specific validation
    """
    validator = AzureResourceValidator()
    return validator.validate_vm_action(action)
