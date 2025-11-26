"""Plan approval logic."""

from datetime import datetime, timedelta
from typing import Optional

from dfo.core.config import get_settings
from dfo.execute.models import ActionType, PlanStatus, ValidationStatus
from dfo.execute.plan_manager import PlanManager
from dfo.execute.validators import should_revalidate


class ApprovalError(Exception):
    """Raised when plan approval fails validation checks."""

    pass


def approve_plan(
    plan_id: str, approved_by: str = "system", notes: Optional[str] = None
) -> None:
    """Approve an execution plan.

    Prerequisites:
    - Plan status must be VALIDATED
    - Validation must be fresh (<1 hour by default)
    - No actions with ERROR validation status
    - All actions must be in VALIDATED or PENDING status

    Args:
        plan_id: Plan ID to approve
        approved_by: User or system identifier approving the plan
        notes: Optional approval notes for audit trail

    Raises:
        ApprovalError: If plan cannot be approved due to validation checks
        ValueError: If plan not found
    """
    manager = PlanManager()
    plan = manager.get_plan(plan_id)
    actions = manager.get_actions(plan_id)

    # Check 1: Plan must be in VALIDATED status
    if plan.status != PlanStatus.VALIDATED:
        if plan.status == PlanStatus.DRAFT:
            raise ApprovalError(
                f"Cannot approve plan: status is '{plan.status}'\n"
                f"Run validation first: dfo azure plan validate {plan_id}"
            )
        elif plan.status == PlanStatus.APPROVED:
            raise ApprovalError(
                f"Plan is already approved at {plan.approved_at} by {plan.approved_by}"
            )
        elif plan.status in [PlanStatus.EXECUTING, PlanStatus.COMPLETED]:
            raise ApprovalError(
                f"Cannot approve plan: status is '{plan.status}'"
            )
        else:
            raise ApprovalError(
                f"Cannot approve plan: invalid status '{plan.status}'"
            )

    # Check 2: Validation must be fresh
    if should_revalidate(plan_id):
        if plan.validated_at:
            age_hours = (datetime.now() - plan.validated_at).total_seconds() / 3600
            raise ApprovalError(
                f"Cannot approve plan: validation is stale ({age_hours:.1f} hours old)\n"
                f"Re-validate plan: dfo azure plan validate {plan_id}"
            )
        else:
            raise ApprovalError(
                f"Cannot approve plan: plan has never been validated\n"
                f"Validate plan: dfo azure plan validate {plan_id}"
            )

    # Check 3: No actions with validation errors
    error_actions = [
        a for a in actions if a.validation_status == ValidationStatus.ERROR
    ]
    if error_actions:
        error_details = []
        for action in error_actions:
            errors = []
            if action.validation_details and "errors" in action.validation_details:
                errors = action.validation_details["errors"]
            error_msg = f"  - {action.action_id}: {', '.join(errors) if errors else 'Unknown error'}"
            error_details.append(error_msg)

        raise ApprovalError(
            f"Cannot approve plan: {len(error_actions)} action(s) have validation errors\n\n"
            f"Errors:\n" + "\n".join(error_details) + "\n\n"
            f"Fix errors or remove failed actions, then re-validate"
        )

    # Check 4: Plan must have at least one action
    if not actions:
        raise ApprovalError("Cannot approve plan: plan has no actions")

    # Update plan status to APPROVED
    metadata = {}
    if notes:
        metadata["approval_notes"] = notes

    # approved_at is set automatically by update_plan_status when status changes to APPROVED
    manager.update_plan_status(
        plan_id,
        PlanStatus.APPROVED,
        approved_by=approved_by,
        metadata=metadata if metadata else None,
    )


def get_approval_summary(plan_id: str) -> dict:
    """Get approval summary for a plan.

    Returns information needed for approval decision:
    - Action counts by type
    - Validation status
    - Destructive action warnings
    - Estimated savings

    Args:
        plan_id: Plan ID

    Returns:
        Dictionary with approval summary
    """
    manager = PlanManager()
    plan = manager.get_plan(plan_id)
    actions = manager.get_actions(plan_id)

    # Count actions by type
    action_counts = {}
    for action in actions:
        action_type = action.action_type
        action_counts[action_type] = action_counts.get(action_type, 0) + 1

    # Count destructive actions
    destructive_actions = [
        a for a in actions if a.action_type in [ActionType.DELETE, ActionType.DOWNSIZE]
    ]

    # Count validation statuses
    ready_actions = sum(
        1 for a in actions if a.validation_status == ValidationStatus.SUCCESS
    )
    warning_actions = sum(
        1 for a in actions if a.validation_status == ValidationStatus.WARNING
    )
    error_actions = sum(
        1 for a in actions if a.validation_status == ValidationStatus.ERROR
    )

    # Calculate validation age
    validation_age_hours = None
    if plan.validated_at:
        validation_age_hours = (
            datetime.now() - plan.validated_at
        ).total_seconds() / 3600

    return {
        "plan_id": plan_id,
        "plan_name": plan.plan_name,
        "plan_status": plan.status,
        "total_actions": len(actions),
        "action_counts": action_counts,
        "ready_actions": ready_actions,
        "warning_actions": warning_actions,
        "error_actions": error_actions,
        "destructive_actions": len(destructive_actions),
        "estimated_savings": plan.total_estimated_savings,
        "validated_at": plan.validated_at,
        "validation_age_hours": validation_age_hours,
        "can_approve": plan.status == PlanStatus.VALIDATED
        and error_actions == 0
        and not should_revalidate(plan_id),
    }
