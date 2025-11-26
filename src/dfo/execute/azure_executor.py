"""Azure VM action executor."""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from azure.core.exceptions import ResourceNotFoundError, HttpResponseError
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.compute.models import VirtualMachine

from dfo.core.auth import get_azure_credential
from dfo.core.config import get_settings
from dfo.execute.models import ActionType, PlanAction
from dfo.providers.azure.client import get_compute_client

logger = logging.getLogger(__name__)


class ExecutionResult:
    """Result of executing an action."""

    def __init__(
        self,
        success: bool,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        rollback_data: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ):
        """Initialize execution result.

        Args:
            success: Whether execution succeeded
            message: Result message
            details: Additional execution details
            rollback_data: Data needed for rollback
            error_code: Error code if failed
        """
        self.success = success
        self.message = message
        self.details = details or {}
        self.rollback_data = rollback_data or {}
        self.error_code = error_code


class AzureVMExecutor:
    """Executes actions on Azure VMs."""

    def __init__(self):
        """Initialize Azure VM executor."""
        self.settings = get_settings()
        self.credential = get_azure_credential()
        self.compute_client: Optional[ComputeManagementClient] = None

    def _get_compute_client(self) -> ComputeManagementClient:
        """Get or create compute client."""
        if not self.compute_client:
            self.compute_client = get_compute_client(
                self.settings.azure_subscription_id, self.credential
            )
        return self.compute_client

    def _parse_resource_id(self, resource_id: str) -> tuple[str, str]:
        """Parse Azure resource ID to get resource group and VM name.

        Args:
            resource_id: Azure resource ID

        Returns:
            Tuple of (resource_group, vm_name)

        Raises:
            ValueError: If resource ID format is invalid
        """
        # Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Compute/virtualMachines/{name}
        parts = resource_id.split("/")
        if len(parts) < 9:
            raise ValueError(f"Invalid resource ID format: {resource_id}")

        resource_group = parts[4]
        vm_name = parts[8]
        return resource_group, vm_name

    def _get_vm(self, resource_group: str, vm_name: str) -> VirtualMachine:
        """Get VM from Azure.

        Args:
            resource_group: Resource group name
            vm_name: VM name

        Returns:
            VirtualMachine object

        Raises:
            ResourceNotFoundError: If VM not found
        """
        client = self._get_compute_client()
        return client.virtual_machines.get(
            resource_group_name=resource_group,
            vm_name=vm_name,
            expand="instanceView",
        )

    def _get_power_state(self, vm: VirtualMachine) -> str:
        """Get VM power state.

        Args:
            vm: VirtualMachine object

        Returns:
            Power state string (running, stopped, deallocated, etc.)
        """
        if not vm.instance_view or not vm.instance_view.statuses:
            return "unknown"

        for status in vm.instance_view.statuses:
            if status.code.startswith("PowerState/"):
                return status.code.split("/")[1]

        return "unknown"

    def execute_action(self, action: PlanAction) -> ExecutionResult:
        """Execute an action on a VM.

        Args:
            action: Plan action to execute

        Returns:
            ExecutionResult with execution details
        """
        try:
            # Route to appropriate executor based on action type
            if action.action_type == ActionType.STOP:
                return self.stop_vm(action)
            elif action.action_type == ActionType.DEALLOCATE:
                return self.deallocate_vm(action)
            elif action.action_type == ActionType.DELETE:
                return self.delete_vm(action)
            elif action.action_type == ActionType.DOWNSIZE:
                return self.downsize_vm(action)
            elif action.action_type == ActionType.START:
                return self.start_vm(action)
            else:
                return ExecutionResult(
                    success=False,
                    message=f"Unknown action type: {action.action_type}",
                    error_code="UNKNOWN_ACTION_TYPE",
                )

        except Exception as e:
            logger.exception(f"Error executing action {action.action_id}")
            return ExecutionResult(
                success=False,
                message=f"Execution failed: {str(e)}",
                error_code="EXECUTION_ERROR",
            )

    def stop_vm(self, action: PlanAction) -> ExecutionResult:
        """Stop a VM (graceful shutdown, but keeps compute allocation).

        Args:
            action: Plan action

        Returns:
            ExecutionResult
        """
        try:
            resource_group, vm_name = self._parse_resource_id(action.resource_id)
            client = self._get_compute_client()

            # Get current state for rollback
            vm = self._get_vm(resource_group, vm_name)
            current_state = self._get_power_state(vm)

            # Stop the VM
            logger.info(f"Stopping VM: {vm_name} in {resource_group}")
            poller = client.virtual_machines.begin_power_off(
                resource_group_name=resource_group, vm_name=vm_name
            )
            poller.wait()

            return ExecutionResult(
                success=True,
                message=f"VM stopped successfully: {vm_name}",
                details={
                    "resource_group": resource_group,
                    "vm_name": vm_name,
                    "previous_state": current_state,
                    "new_state": "stopped",
                },
                rollback_data={
                    "action_type": "start" if current_state == "running" else None,
                    "previous_state": current_state,
                },
            )

        except ResourceNotFoundError:
            return ExecutionResult(
                success=False,
                message=f"VM not found: {action.resource_name}",
                error_code="RESOURCE_NOT_FOUND",
            )
        except HttpResponseError as e:
            return ExecutionResult(
                success=False,
                message=f"Azure API error: {e.message}",
                error_code=e.error.code if e.error else "HTTP_ERROR",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Stop failed: {str(e)}",
                error_code="STOP_ERROR",
            )

    def deallocate_vm(self, action: PlanAction) -> ExecutionResult:
        """Deallocate a VM (stop and release compute resources).

        This releases the compute allocation and stops billing for compute.

        Args:
            action: Plan action

        Returns:
            ExecutionResult
        """
        try:
            resource_group, vm_name = self._parse_resource_id(action.resource_id)
            client = self._get_compute_client()

            # Get current state for rollback
            vm = self._get_vm(resource_group, vm_name)
            current_state = self._get_power_state(vm)

            # Deallocate the VM
            logger.info(f"Deallocating VM: {vm_name} in {resource_group}")
            poller = client.virtual_machines.begin_deallocate(
                resource_group_name=resource_group, vm_name=vm_name
            )
            poller.wait()

            return ExecutionResult(
                success=True,
                message=f"VM deallocated successfully: {vm_name}",
                details={
                    "resource_group": resource_group,
                    "vm_name": vm_name,
                    "previous_state": current_state,
                    "new_state": "deallocated",
                },
                rollback_data={
                    "action_type": "start" if current_state == "running" else None,
                    "previous_state": current_state,
                },
            )

        except ResourceNotFoundError:
            return ExecutionResult(
                success=False,
                message=f"VM not found: {action.resource_name}",
                error_code="RESOURCE_NOT_FOUND",
            )
        except HttpResponseError as e:
            return ExecutionResult(
                success=False,
                message=f"Azure API error: {e.message}",
                error_code=e.error.code if e.error else "HTTP_ERROR",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Deallocate failed: {str(e)}",
                error_code="DEALLOCATE_ERROR",
            )

    def delete_vm(self, action: PlanAction) -> ExecutionResult:
        """Delete a VM and optionally its associated resources.

        WARNING: This is irreversible. The VM and attached resources will be
        permanently deleted.

        Args:
            action: Plan action

        Returns:
            ExecutionResult
        """
        try:
            resource_group, vm_name = self._parse_resource_id(action.resource_id)
            client = self._get_compute_client()

            # Get VM details before deletion for rollback info
            vm = self._get_vm(resource_group, vm_name)
            current_state = self._get_power_state(vm)

            # Collect resource info for rollback (though delete is not reversible)
            rollback_info = {
                "resource_group": resource_group,
                "vm_name": vm_name,
                "vm_size": vm.hardware_profile.vm_size if vm.hardware_profile else None,
                "location": vm.location,
                "previous_state": current_state,
                "warning": "DELETE is IRREVERSIBLE - VM cannot be recovered",
            }

            # Delete the VM
            logger.warning(
                f"DELETING VM (IRREVERSIBLE): {vm_name} in {resource_group}"
            )
            poller = client.virtual_machines.begin_delete(
                resource_group_name=resource_group, vm_name=vm_name
            )
            poller.wait()

            return ExecutionResult(
                success=True,
                message=f"VM deleted successfully (IRREVERSIBLE): {vm_name}",
                details={
                    "resource_group": resource_group,
                    "vm_name": vm_name,
                    "previous_state": current_state,
                    "new_state": "deleted",
                    "warning": "This action is IRREVERSIBLE",
                },
                rollback_data=rollback_info,
            )

        except ResourceNotFoundError:
            # VM already deleted or never existed
            return ExecutionResult(
                success=True,
                message=f"VM not found (may already be deleted): {action.resource_name}",
                details={"resource_name": action.resource_name, "status": "not_found"},
            )
        except HttpResponseError as e:
            return ExecutionResult(
                success=False,
                message=f"Azure API error: {e.message}",
                error_code=e.error.code if e.error else "HTTP_ERROR",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Delete failed: {str(e)}",
                error_code="DELETE_ERROR",
            )

    def downsize_vm(self, action: PlanAction) -> ExecutionResult:
        """Resize a VM to a smaller size.

        VM must be stopped/deallocated before resizing.

        Args:
            action: Plan action (must have 'new_size' in action_params)

        Returns:
            ExecutionResult
        """
        try:
            resource_group, vm_name = self._parse_resource_id(action.resource_id)
            client = self._get_compute_client()

            # Validate new_size parameter
            if not action.action_params or "new_size" not in action.action_params:
                return ExecutionResult(
                    success=False,
                    message="Downsize action requires 'new_size' parameter",
                    error_code="MISSING_PARAMETER",
                )

            new_size = action.action_params["new_size"]

            # Get current VM
            vm = self._get_vm(resource_group, vm_name)
            current_size = vm.hardware_profile.vm_size if vm.hardware_profile else None
            current_state = self._get_power_state(vm)

            # Check if VM is stopped/deallocated
            if current_state not in ["stopped", "deallocated"]:
                return ExecutionResult(
                    success=False,
                    message=f"VM must be stopped/deallocated before resizing (current state: {current_state})",
                    error_code="INVALID_STATE",
                )

            # Update VM size
            logger.info(
                f"Resizing VM: {vm_name} from {current_size} to {new_size}"
            )
            vm.hardware_profile.vm_size = new_size
            poller = client.virtual_machines.begin_create_or_update(
                resource_group_name=resource_group, vm_name=vm_name, parameters=vm
            )
            poller.wait()

            return ExecutionResult(
                success=True,
                message=f"VM resized successfully: {vm_name} ({current_size} → {new_size})",
                details={
                    "resource_group": resource_group,
                    "vm_name": vm_name,
                    "previous_size": current_size,
                    "new_size": new_size,
                },
                rollback_data={
                    "action_type": "downsize",  # Rollback would resize back
                    "original_size": current_size,
                    "new_size": new_size,
                },
            )

        except ResourceNotFoundError:
            return ExecutionResult(
                success=False,
                message=f"VM not found: {action.resource_name}",
                error_code="RESOURCE_NOT_FOUND",
            )
        except HttpResponseError as e:
            return ExecutionResult(
                success=False,
                message=f"Azure API error: {e.message}",
                error_code=e.error.code if e.error else "HTTP_ERROR",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Downsize failed: {str(e)}",
                error_code="DOWNSIZE_ERROR",
            )

    def start_vm(self, action: PlanAction) -> ExecutionResult:
        """Start a stopped/deallocated VM (typically used for rollback).

        Args:
            action: Plan action

        Returns:
            ExecutionResult
        """
        try:
            resource_group, vm_name = self._parse_resource_id(action.resource_id)
            client = self._get_compute_client()

            # Get current state
            vm = self._get_vm(resource_group, vm_name)
            current_state = self._get_power_state(vm)

            # Start the VM
            logger.info(f"Starting VM: {vm_name} in {resource_group}")
            poller = client.virtual_machines.begin_start(
                resource_group_name=resource_group, vm_name=vm_name
            )
            poller.wait()

            return ExecutionResult(
                success=True,
                message=f"VM started successfully: {vm_name}",
                details={
                    "resource_group": resource_group,
                    "vm_name": vm_name,
                    "previous_state": current_state,
                    "new_state": "running",
                },
                rollback_data={
                    "action_type": "stop",  # Rollback would stop it again
                    "previous_state": current_state,
                },
            )

        except ResourceNotFoundError:
            return ExecutionResult(
                success=False,
                message=f"VM not found: {action.resource_name}",
                error_code="RESOURCE_NOT_FOUND",
            )
        except HttpResponseError as e:
            return ExecutionResult(
                success=False,
                message=f"Azure API error: {e.message}",
                error_code=e.error.code if e.error else "HTTP_ERROR",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Start failed: {str(e)}",
                error_code="START_ERROR",
            )
