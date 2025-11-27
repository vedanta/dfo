"""Direct execution module for single-resource actions.

This module provides direct execution of optimization actions on individual resources
without the multi-step plan-based workflow. Direct execution is disabled by default
and must be explicitly enabled via DFO_ENABLE_DIRECT_EXECUTION environment variable.

Usage:
    from dfo.execute.direct import DirectExecutionManager, DirectExecutionRequest

    manager = DirectExecutionManager()

    request = DirectExecutionRequest(
        resource_type="vm",
        resource_name="vm-prod-001",
        action="stop",
        resource_group="production-rg",
        reason="Cost optimization",
        force=False,
        yes=False
    )

    result = manager.execute(request)

Safety Features:
    - Feature flag check (disabled by default)
    - Resource validation (existence, state)
    - Action validation (valid for resource type/state)
    - Azure validation (locks, tags, policies)
    - Preview display with confirmation prompt
    - Comprehensive action logging

Supported Actions:
    - stop: Stop VM (preserves compute allocation)
    - deallocate: Deallocate VM (releases compute, keeps disks)
    - delete: Delete VM (permanent removal)
    - downsize: Resize VM to smaller SKU
    - restart: Restart VM
"""
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm

from dfo.core.config import get_settings
from dfo.execute.action_logger import ActionLogger
from dfo.providers.azure.client import get_compute_client
from dfo.db.duck import get_db


class ActionType(str, Enum):
    """Supported action types."""
    STOP = "stop"
    DEALLOCATE = "deallocate"
    DELETE = "delete"
    DOWNSIZE = "downsize"
    RESTART = "restart"


class ResourceType(str, Enum):
    """Supported resource types."""
    VM = "vm"


class ExecutionError(Exception):
    """Base exception for execution errors."""
    pass


class FeatureDisabledError(ExecutionError):
    """Raised when direct execution feature is disabled."""
    pass


class ResourceNotFoundError(ExecutionError):
    """Raised when resource is not found."""
    pass


class ValidationError(ExecutionError):
    """Raised when validation fails."""
    pass


@dataclass
class DirectExecutionRequest:
    """Request for direct execution of an action.

    Attributes:
        resource_type: Type of resource (currently only 'vm' supported)
        resource_name: Name of the resource
        action: Action to perform (stop, deallocate, delete, downsize, restart)
        resource_group: Resource group name (required for Azure resources)
        force: Skip safety confirmations (dangerous!)
        yes: Auto-confirm execution (bypasses interactive prompt)
        target_sku: Target SKU for downsize action (required for downsize)
        reason: User-provided reason for the action
        no_validation: Skip validation checks (very dangerous!)
        dry_run: Simulate execution without making changes

    Example:
        >>> request = DirectExecutionRequest(
        ...     resource_type="vm",
        ...     resource_name="vm-prod-001",
        ...     action="stop",
        ...     resource_group="production-rg",
        ...     reason="Cost optimization during off-hours"
        ... )
    """
    resource_type: str
    resource_name: str
    action: str
    resource_group: str
    force: bool = False
    yes: bool = False
    target_sku: Optional[str] = None
    reason: Optional[str] = None
    no_validation: bool = False
    dry_run: bool = True

    def __post_init__(self):
        """Validate request after initialization."""
        # Validate resource type
        try:
            ResourceType(self.resource_type)
        except ValueError:
            raise ValidationError(
                f"Invalid resource type: {self.resource_type}. "
                f"Supported types: {[t.value for t in ResourceType]}"
            )

        # Validate action type
        try:
            ActionType(self.action)
        except ValueError:
            raise ValidationError(
                f"Invalid action: {self.action}. "
                f"Supported actions: {[a.value for a in ActionType]}"
            )

        # Validate downsize requires target_sku
        if self.action == ActionType.DOWNSIZE and not self.target_sku:
            raise ValidationError("Downsize action requires target_sku parameter")

        # Validate resource_group is provided
        if not self.resource_group:
            raise ValidationError("resource_group is required for Azure resources")


@dataclass
class ExecutionResult:
    """Result of direct execution.

    Attributes:
        success: Whether execution succeeded
        action_id: Action log ID
        message: Result message
        duration_seconds: Execution duration
        pre_state: Resource state before action
        post_state: Resource state after action (None if dry-run)
        errors: List of errors if execution failed
    """
    success: bool
    action_id: str
    message: str
    duration_seconds: float
    pre_state: Optional[Dict[str, Any]] = None
    post_state: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None


class DirectExecutionManager:
    """Manages direct execution of optimization actions.

    This class orchestrates the complete execution workflow:
    1. Feature flag check
    2. Resource validation
    3. Action validation
    4. Azure validation (locks, tags, policies)
    5. Preview display
    6. User confirmation
    7. Action execution
    8. Result logging and display

    Example:
        >>> manager = DirectExecutionManager()
        >>> request = DirectExecutionRequest(
        ...     resource_type="vm",
        ...     resource_name="vm-prod-001",
        ...     action="stop",
        ...     resource_group="production-rg"
        ... )
        >>> result = manager.execute(request)
    """

    def __init__(self):
        """Initialize DirectExecutionManager."""
        self.settings = get_settings()
        self.console = Console()
        self.logger = ActionLogger()
        self.db_manager = get_db()
        self.db = self.db_manager.get_connection()

    def execute(self, request: DirectExecutionRequest) -> ExecutionResult:
        """Execute direct action on resource.

        Args:
            request: DirectExecutionRequest with action details

        Returns:
            ExecutionResult with execution details

        Raises:
            FeatureDisabledError: If direct execution is disabled
            ResourceNotFoundError: If resource not found
            ValidationError: If validation fails
            ExecutionError: If execution fails

        Example:
            >>> manager = DirectExecutionManager()
            >>> request = DirectExecutionRequest(
            ...     resource_type="vm",
            ...     resource_name="vm-prod-001",
            ...     action="stop",
            ...     resource_group="production-rg"
            ... )
            >>> result = manager.execute(request)
            >>> print(f"Success: {result.success}")
            >>> print(f"Action ID: {result.action_id}")
        """
        start_time = datetime.utcnow()

        # Step 1: Check feature flag
        self._check_feature_enabled()

        # Step 2: Validate resource exists and get current state
        resource_data = self._validate_resource(request)

        # Step 3: Validate action is appropriate for resource
        if not request.no_validation:
            self._validate_action(request, resource_data)

        # Step 4: Azure-side validation (locks, tags, etc.)
        if not request.no_validation:
            self._azure_validation(request, resource_data)

        # Step 5: Display preview
        self._display_preview(request, resource_data)

        # Step 6: Get confirmation (unless force/yes flags set)
        if not request.dry_run and not request.yes and not request.force:
            if not self._confirm_execution(request):
                self.console.print("[yellow]Execution cancelled by user[/yellow]")
                return ExecutionResult(
                    success=False,
                    action_id="",
                    message="Cancelled by user",
                    duration_seconds=0,
                    errors=["Cancelled by user"]
                )

        # Step 7: Create action log entry
        action_id = self.logger.create_log_entry(
            action_type=request.action,
            vm_name=request.resource_name,
            resource_group=request.resource_group,
            executed=not request.dry_run,
            source="direct_execution",
            vm_id=resource_data.get("id"),
            reason=request.reason,
            pre_state=resource_data
        )

        # Step 8: Execute action
        try:
            self.logger.update_log_entry(
                action_id=action_id,
                status="executing"
            )

            result_message, post_state = self._execute_action(request, resource_data)

            # Calculate duration
            duration = (datetime.utcnow() - start_time).total_seconds()

            # Update log with success
            self.logger.update_log_entry(
                action_id=action_id,
                status="completed",
                result_message=result_message,
                duration_seconds=duration,
                post_state=post_state
            )

            # Step 9: Display result
            self._display_result(request, result_message, action_id)

            return ExecutionResult(
                success=True,
                action_id=action_id,
                message=result_message,
                duration_seconds=duration,
                pre_state=resource_data,
                post_state=post_state
            )

        except Exception as e:
            # Calculate duration
            duration = (datetime.utcnow() - start_time).total_seconds()

            # Update log with failure
            error_message = str(e)
            self.logger.update_log_entry(
                action_id=action_id,
                status="failed",
                result_message=error_message,
                duration_seconds=duration
            )

            # Display error
            self.console.print(f"[red]✗ Execution failed: {error_message}[/red]")

            return ExecutionResult(
                success=False,
                action_id=action_id,
                message=error_message,
                duration_seconds=duration,
                pre_state=resource_data,
                errors=[error_message]
            )

    def _check_feature_enabled(self):
        """Check if direct execution feature is enabled.

        Raises:
            FeatureDisabledError: If feature is disabled
        """
        if not self.settings.dfo_enable_direct_execution:
            raise FeatureDisabledError(
                "Direct execution is disabled. Set DFO_ENABLE_DIRECT_EXECUTION=true to enable.\n"
                "⚠ WARNING: Direct execution bypasses plan-based safety gates. "
                "Only enable in development/testing or with proper access controls."
            )

    def _validate_resource(self, request: DirectExecutionRequest) -> Dict[str, Any]:
        """Validate resource exists and get current state.

        Args:
            request: DirectExecutionRequest

        Returns:
            Dict with resource data (id, name, location, size, power_state, etc.)

        Raises:
            ResourceNotFoundError: If resource not found
        """
        if request.resource_type == ResourceType.VM:
            compute_client = get_compute_client()

            try:
                vm = compute_client.virtual_machines.get(
                    resource_group_name=request.resource_group,
                    vm_name=request.resource_name,
                    expand="instanceView"
                )

                # Extract power state from instance view
                power_state = "unknown"
                if vm.instance_view and vm.instance_view.statuses:
                    for status in vm.instance_view.statuses:
                        if status.code and status.code.startswith("PowerState/"):
                            power_state = status.code.replace("PowerState/", "")
                            break

                return {
                    "id": vm.id,
                    "name": vm.name,
                    "location": vm.location,
                    "size": vm.hardware_profile.vm_size,
                    "power_state": power_state,
                    "os_type": vm.storage_profile.os_disk.os_type if vm.storage_profile and vm.storage_profile.os_disk else "unknown",
                    "tags": dict(vm.tags) if vm.tags else {},
                    "resource_group": request.resource_group
                }

            except Exception as e:
                # Check if it's an Azure ResourceNotFoundError
                if e.__class__.__name__ == "ResourceNotFoundError" or "NotFound" in str(type(e)):
                    raise ResourceNotFoundError(
                        f"VM '{request.resource_name}' not found in resource group '{request.resource_group}'"
                    )
                raise ExecutionError(f"Failed to get VM: {e}")

        raise ValidationError(f"Unsupported resource type: {request.resource_type}")

    def _validate_action(self, request: DirectExecutionRequest, resource_data: Dict[str, Any]):
        """Validate action is appropriate for resource state.

        Args:
            request: DirectExecutionRequest
            resource_data: Current resource data

        Raises:
            ValidationError: If action is invalid for current state
        """
        power_state = resource_data.get("power_state", "unknown")
        action = request.action

        # Define valid state transitions
        if action == ActionType.STOP:
            if power_state in ["stopped", "deallocated"]:
                raise ValidationError(
                    f"Cannot stop VM - already in state: {power_state}"
                )

        elif action == ActionType.DEALLOCATE:
            if power_state == "deallocated":
                raise ValidationError(
                    f"Cannot deallocate VM - already deallocated"
                )

        elif action == ActionType.RESTART:
            if power_state in ["stopped", "deallocated"]:
                raise ValidationError(
                    f"Cannot restart VM - current state is {power_state}. Use 'start' action instead."
                )

        elif action == ActionType.DELETE:
            # Delete can be performed in any state, but warn about running VMs
            if power_state == "running":
                self.console.print(
                    "[yellow]⚠ Warning: VM is currently running. "
                    "Consider stopping it first.[/yellow]"
                )

        elif action == ActionType.DOWNSIZE:
            if power_state == "running":
                raise ValidationError(
                    "Cannot downsize running VM. Stop or deallocate it first."
                )

            # Validate target SKU is different from current
            current_sku = resource_data.get("size")
            if request.target_sku == current_sku:
                raise ValidationError(
                    f"Target SKU '{request.target_sku}' is same as current SKU"
                )

    def _azure_validation(self, request: DirectExecutionRequest, resource_data: Dict[str, Any]):
        """Perform Azure-side validation (locks, tags, policies).

        Args:
            request: DirectExecutionRequest
            resource_data: Current resource data

        Note:
            Currently performs basic tag-based checks. Future enhancement:
            - Check for resource locks
            - Check for Azure Policy restrictions
            - Check for dependencies (NICs, disks, etc.)
        """
        tags = resource_data.get("tags", {})

        # Check for protection tags
        if tags.get("dfo-protected") == "true":
            raise ValidationError(
                f"Resource has 'dfo-protected=true' tag. Remove tag to allow execution."
            )

        if tags.get("environment") == "production" and request.action == ActionType.DELETE:
            self.console.print(
                "[yellow]⚠ Warning: Deleting production resource! "
                "Ensure you have proper authorization.[/yellow]"
            )

    def _display_preview(self, request: DirectExecutionRequest, resource_data: Dict[str, Any]):
        """Display preview of action to be performed.

        Args:
            request: DirectExecutionRequest
            resource_data: Current resource data
        """
        table = Table(title="Execution Preview", show_header=False, box=None)
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Resource Type", request.resource_type.upper())
        table.add_row("Resource Name", request.resource_name)
        table.add_row("Resource Group", request.resource_group)
        table.add_row("Current State", resource_data.get("power_state", "unknown"))
        table.add_row("Current Size", resource_data.get("size", "unknown"))
        table.add_row("Action", request.action.upper())

        if request.action == ActionType.DOWNSIZE:
            table.add_row("Target Size", request.target_sku or "N/A")

        table.add_row("Mode", "[yellow]DRY RUN[/yellow]" if request.dry_run else "[red]LIVE EXECUTION[/red]")

        if request.reason:
            table.add_row("Reason", request.reason)

        self.console.print()
        self.console.print(table)
        self.console.print()

    def _confirm_execution(self, request: DirectExecutionRequest) -> bool:
        """Prompt user for confirmation.

        Args:
            request: DirectExecutionRequest

        Returns:
            bool: True if user confirms, False otherwise
        """
        if request.action == ActionType.DELETE:
            prompt = f"⚠ PERMANENTLY DELETE VM '{request.resource_name}'? This cannot be undone!"
        else:
            prompt = f"Execute {request.action} on '{request.resource_name}'?"

        return Confirm.ask(prompt, default=False)

    def _execute_action(
        self,
        request: DirectExecutionRequest,
        resource_data: Dict[str, Any]
    ) -> tuple[str, Optional[Dict[str, Any]]]:
        """Execute the action on the resource.

        Args:
            request: DirectExecutionRequest
            resource_data: Current resource data

        Returns:
            Tuple of (result_message, post_state)

        Raises:
            ExecutionError: If execution fails
        """
        if request.dry_run:
            return (
                f"[DRY RUN] Would execute {request.action} on {request.resource_name}",
                None
            )

        # Live execution
        compute_client = get_compute_client()

        try:
            if request.action == ActionType.STOP:
                self.console.print(f"Stopping VM '{request.resource_name}'...")
                poller = compute_client.virtual_machines.begin_power_off(
                    resource_group_name=request.resource_group,
                    vm_name=request.resource_name
                )
                poller.wait()
                post_state = self._get_post_state(request)
                return (f"VM '{request.resource_name}' stopped successfully", post_state)

            elif request.action == ActionType.DEALLOCATE:
                self.console.print(f"Deallocating VM '{request.resource_name}'...")
                poller = compute_client.virtual_machines.begin_deallocate(
                    resource_group_name=request.resource_group,
                    vm_name=request.resource_name
                )
                poller.wait()
                post_state = self._get_post_state(request)
                return (f"VM '{request.resource_name}' deallocated successfully", post_state)

            elif request.action == ActionType.RESTART:
                self.console.print(f"Restarting VM '{request.resource_name}'...")
                poller = compute_client.virtual_machines.begin_restart(
                    resource_group_name=request.resource_group,
                    vm_name=request.resource_name
                )
                poller.wait()
                post_state = self._get_post_state(request)
                return (f"VM '{request.resource_name}' restarted successfully", post_state)

            elif request.action == ActionType.DELETE:
                self.console.print(f"Deleting VM '{request.resource_name}'...")
                poller = compute_client.virtual_machines.begin_delete(
                    resource_group_name=request.resource_group,
                    vm_name=request.resource_name
                )
                poller.wait()
                return (f"VM '{request.resource_name}' deleted successfully", {"deleted": True})

            elif request.action == ActionType.DOWNSIZE:
                self.console.print(
                    f"Resizing VM '{request.resource_name}' to {request.target_sku}..."
                )

                # Get current VM
                vm = compute_client.virtual_machines.get(
                    resource_group_name=request.resource_group,
                    vm_name=request.resource_name
                )

                # Update VM size
                vm.hardware_profile.vm_size = request.target_sku

                # Begin update
                poller = compute_client.virtual_machines.begin_create_or_update(
                    resource_group_name=request.resource_group,
                    vm_name=request.resource_name,
                    parameters=vm
                )
                poller.wait()

                post_state = self._get_post_state(request)
                return (
                    f"VM '{request.resource_name}' resized to {request.target_sku} successfully",
                    post_state
                )

            else:
                raise ExecutionError(f"Unsupported action: {request.action}")

        except Exception as e:
            raise ExecutionError(f"Action execution failed: {e}")

    def _get_post_state(self, request: DirectExecutionRequest) -> Dict[str, Any]:
        """Get resource state after execution.

        Args:
            request: DirectExecutionRequest

        Returns:
            Dict with post-execution resource state
        """
        try:
            return self._validate_resource(request)
        except Exception as e:
            return {"error": f"Failed to get post-execution state: {e}"}

    def _display_result(self, request: DirectExecutionRequest, message: str, action_id: str):
        """Display execution result.

        Args:
            request: DirectExecutionRequest
            message: Result message
            action_id: Action log ID
        """
        self.console.print()

        if request.dry_run:
            panel = Panel(
                f"[yellow]{message}[/yellow]\n\n"
                f"Action ID: {action_id}\n"
                f"To execute for real, add --no-dry-run flag",
                title="✓ Dry Run Complete",
                border_style="yellow"
            )
        else:
            panel = Panel(
                f"[green]{message}[/green]\n\n"
                f"Action ID: {action_id}\n"
                f"View logs: ./dfo azure logs show {action_id}",
                title="✓ Execution Complete",
                border_style="green"
            )

        self.console.print(panel)
        self.console.print()
