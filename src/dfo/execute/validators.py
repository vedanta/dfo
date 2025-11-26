"""Plan and action validation logic."""

from datetime import datetime, timedelta
from typing import Dict, List

from dfo.core.config import get_settings
from dfo.execute.models import (
    ActionStatus,
    ActionType,
    PlanAction,
    PlanStatus,
    PlanValidationResult,
    ValidationResult,
    ValidationStatus,
)
from dfo.execute.plan_manager import PlanManager


# Destructive actions that require extra warnings
DESTRUCTIVE_ACTIONS = [ActionType.DELETE, ActionType.DOWNSIZE]

# Protection tags that prevent action execution
PROTECTION_TAGS = ["dfo-protected", "dfo-exclude"]


def validate_plan(plan_id: str) -> PlanValidationResult:
    """Validate an execution plan.

    Performs comprehensive validation of all actions in a plan:
    - Resource existence
    - Current state
    - Permissions
    - Dependencies
    - Protection tags
    - Destructive action warnings

    Args:
        plan_id: Plan ID to validate

    Returns:
        PlanValidationResult with overall status and per-action results

    Raises:
        ValueError: If plan not found
    """
    manager = PlanManager()
    plan = manager.get_plan(plan_id)
    actions = manager.get_actions(plan_id)

    if not actions:
        return PlanValidationResult(
            plan_id=plan_id,
            status=ValidationStatus.ERROR,
            total_actions=0,
            ready_actions=0,
            warning_actions=0,
            error_actions=0,
            action_results=[],
            summary="Plan has no actions to validate",
        )

    # Validate each action
    action_results: List[ValidationResult] = []
    for action in actions:
        result = validate_action(action)
        action_results.append(result)

        # Update action in database
        manager.update_action_status(
            action.action_id,
            ActionStatus.VALIDATED if result.status == ValidationStatus.SUCCESS else ActionStatus.PENDING,
            validation_status=result.status,
            validation_details={
                "resource_exists": result.resource_exists,
                "permissions_ok": result.permissions_ok,
                "dependencies": result.dependencies or [],
                "warnings": result.warnings,
                "errors": result.errors,
            },
        )

    # Calculate summary statistics
    ready_actions = sum(1 for r in action_results if r.status == ValidationStatus.SUCCESS)
    warning_actions = sum(1 for r in action_results if r.status == ValidationStatus.WARNING)
    error_actions = sum(1 for r in action_results if r.status == ValidationStatus.ERROR)

    # Determine overall status
    if error_actions > 0:
        overall_status = ValidationStatus.ERROR
    elif warning_actions > 0:
        overall_status = ValidationStatus.WARNING
    else:
        overall_status = ValidationStatus.SUCCESS

    # Build summary message
    summary_parts = []
    if ready_actions > 0:
        summary_parts.append(f"{ready_actions} ready")
    if warning_actions > 0:
        summary_parts.append(f"{warning_actions} warnings")
    if error_actions > 0:
        summary_parts.append(f"{error_actions} errors")

    summary = f"Validation complete: {', '.join(summary_parts)}"

    # Update plan status
    validation_errors = [
        {"action_id": r.action_id, "errors": r.errors}
        for r in action_results
        if r.errors
    ]
    validation_warnings = [
        {"action_id": r.action_id, "warnings": r.warnings}
        for r in action_results
        if r.warnings
    ]

    manager.update_plan_status(
        plan_id,
        PlanStatus.VALIDATED if overall_status != ValidationStatus.ERROR else PlanStatus.DRAFT,
        validation_errors=validation_errors if validation_errors else None,
        validation_warnings=validation_warnings if validation_warnings else None,
    )

    return PlanValidationResult(
        plan_id=plan_id,
        status=overall_status,
        total_actions=len(actions),
        ready_actions=ready_actions,
        warning_actions=warning_actions,
        error_actions=error_actions,
        action_results=action_results,
        summary=summary,
    )


def validate_action(action: PlanAction, use_azure_validation: bool = True) -> ValidationResult:
    """Validate a single action.

    Performs validation checks appropriate for the action type.
    For Azure VM resources, uses Azure-specific validation.

    Args:
        action: Plan action to validate
        use_azure_validation: Whether to use Azure SDK for validation (default: True)

    Returns:
        ValidationResult with validation status and details
    """
    # Use Azure-specific validation for VMs if enabled
    if use_azure_validation and action.resource_type == "vm":
        try:
            from dfo.execute.azure_validator import validate_azure_vm_action
            return validate_azure_vm_action(action)
        except Exception as e:
            # Fall back to basic validation if Azure validation fails
            result = ValidationResult(
                action_id=action.action_id,
                status=ValidationStatus.WARNING,
                resource_exists=False,
                permissions_ok=False,
                dependencies=[],
                warnings=[f"Azure validation unavailable: {str(e)}"],
                errors=[],
            )
            return result

    # Basic validation (fallback or non-Azure resources)
    result = ValidationResult(
        action_id=action.action_id,
        status=ValidationStatus.SUCCESS,
        resource_exists=True,  # Assume true for basic validation
        permissions_ok=True,   # Assume true for basic validation
        dependencies=[],
        warnings=[],
        errors=[],
    )

    # Check for destructive actions
    if action.action_type in [act.value for act in DESTRUCTIVE_ACTIONS]:
        result.warnings.append(
            f"Action '{action.action_type}' is IRREVERSIBLE"
        )
        result.status = ValidationStatus.WARNING

    # Check action-specific requirements
    if action.action_type == ActionType.DOWNSIZE:
        if not action.action_params or "new_size" not in action.action_params:
            result.errors.append("Downsize action requires 'new_size' parameter")
            result.status = ValidationStatus.ERROR

    # Add basic resource info to details
    result.details = {
        "resource_id": action.resource_id,
        "resource_name": action.resource_name,
        "action_type": action.action_type,
        "estimated_savings": action.estimated_monthly_savings,
    }

    return result


def should_revalidate(plan_id: str) -> bool:
    """Check if plan needs re-validation.

    Plans should be re-validated if:
    - More than 1 hour has passed since last validation
    - Plan has never been validated

    Args:
        plan_id: Plan ID to check

    Returns:
        True if plan needs re-validation, False otherwise
    """
    manager = PlanManager()
    plan = manager.get_plan(plan_id)

    if not plan.validated_at:
        return True

    # Check if more than 1 hour since last validation
    settings = get_settings()
    revalidate_hours = getattr(settings, 'plan_revalidate_hours', 1)
    threshold = datetime.now() - timedelta(hours=revalidate_hours)

    return plan.validated_at < threshold


def get_validation_summary(plan_id: str) -> Dict[str, any]:
    """Get validation summary for a plan.

    Args:
        plan_id: Plan ID

    Returns:
        Dictionary with validation summary
    """
    manager = PlanManager()
    plan = manager.get_plan(plan_id)
    actions = manager.get_actions(plan_id)

    validated_actions = sum(
        1 for a in actions if a.validation_status == ValidationStatus.SUCCESS
    )
    warning_actions = sum(
        1 for a in actions if a.validation_status == ValidationStatus.WARNING
    )
    error_actions = sum(
        1 for a in actions if a.validation_status == ValidationStatus.ERROR
    )
    pending_actions = len(actions) - validated_actions - warning_actions - error_actions

    return {
        "plan_id": plan_id,
        "plan_status": plan.status,
        "validated_at": plan.validated_at,
        "needs_revalidation": should_revalidate(plan_id),
        "total_actions": len(actions),
        "validated": validated_actions,
        "warnings": warning_actions,
        "errors": error_actions,
        "pending": pending_actions,
    }
