"""Rollback logic for executed actions."""

import logging
from datetime import datetime
from typing import List, Optional

from dfo.execute.azure_executor import AzureVMExecutor, ExecutionResult
from dfo.execute.models import ActionStatus, ActionType, PlanAction, PlanStatus
from dfo.execute.plan_manager import PlanManager

logger = logging.getLogger(__name__)


class RollbackError(Exception):
    """Raised when rollback operation fails."""

    pass


def can_rollback_action(action: PlanAction) -> tuple[bool, Optional[str]]:
    """Check if an action can be rolled back.

    Args:
        action: Plan action to check

    Returns:
        Tuple of (can_rollback, reason_if_not)
    """
    # Must be completed
    if action.status != ActionStatus.COMPLETED:
        return False, f"Action not completed (status: {action.status})"

    # Already rolled back
    if action.rolled_back_at:
        return False, "Action already rolled back"

    # Check rollback_possible flag
    if not action.rollback_possible:
        return False, "Action marked as not rollbackable"

    # DELETE is irreversible
    if action.action_type == ActionType.DELETE:
        return False, "DELETE actions cannot be rolled back (irreversible)"

    # Must have rollback data
    if not action.rollback_data:
        return False, "No rollback data available"

    # Check rollback data has required action_type
    if not action.rollback_data.get("action_type"):
        return False, "Rollback data missing action_type"

    return True, None


def create_rollback_action(action: PlanAction) -> PlanAction:
    """Create a rollback action from a completed action.

    Args:
        action: Completed action to rollback

    Returns:
        New PlanAction configured for rollback

    Raises:
        RollbackError: If action cannot be rolled back
    """
    can_rollback, reason = can_rollback_action(action)
    if not can_rollback:
        raise RollbackError(f"Cannot rollback action {action.action_id}: {reason}")

    # Get rollback action type from rollback_data
    rollback_action_type = action.rollback_data.get("action_type")

    # Create reverse action
    rollback_action = PlanAction(
        action_id=f"rollback-{action.action_id}",
        plan_id=action.plan_id,
        resource_id=action.resource_id,
        resource_name=action.resource_name,
        resource_type=action.resource_type,
        resource_group=action.resource_group,
        location=action.location,
        subscription_id=action.subscription_id,
        analysis_id=action.analysis_id,
        analysis_type=f"rollback-{action.analysis_type}",
        severity=action.severity,
        action_type=ActionType(rollback_action_type),
        action_params=_get_rollback_params(action),
        estimated_monthly_savings=0.0,  # No savings from rollback
        status=ActionStatus.PENDING,
        rollback_possible=False,  # Can't rollback a rollback
    )

    return rollback_action


def _get_rollback_params(action: PlanAction) -> dict:
    """Get action parameters for rollback.

    Args:
        action: Original action

    Returns:
        Parameters for rollback action
    """
    params = {}

    # For DOWNSIZE rollback, need to restore original size
    if action.action_type == ActionType.DOWNSIZE:
        original_size = action.rollback_data.get("original_size")
        if original_size:
            params["new_size"] = original_size
            params["rollback_from_size"] = action.rollback_data.get("new_size")

    return params


def rollback_action(action: PlanAction, dry_run: bool = False) -> ExecutionResult:
    """Rollback a single completed action.

    Args:
        action: Completed action to rollback
        dry_run: If True, simulate rollback

    Returns:
        ExecutionResult with rollback details

    Raises:
        RollbackError: If action cannot be rolled back
    """
    can_rollback, reason = can_rollback_action(action)
    if not can_rollback:
        raise RollbackError(f"Cannot rollback action: {reason}")

    # Create rollback action
    rollback_action_obj = create_rollback_action(action)

    if dry_run:
        logger.info(
            f"[DRY RUN] Would rollback {action.action_type} on {action.resource_name} "
            f"by executing {rollback_action_obj.action_type}"
        )
        return ExecutionResult(
            success=True,
            message=f"[DRY RUN] Would rollback {action.action_type} by executing {rollback_action_obj.action_type}",
            details={
                "dry_run": True,
                "original_action_id": action.action_id,
                "original_action_type": action.action_type,
                "rollback_action_type": rollback_action_obj.action_type,
                "resource_name": action.resource_name,
            },
        )

    # Execute rollback via Azure
    logger.info(
        f"Rolling back {action.action_type} on {action.resource_name} "
        f"by executing {rollback_action_obj.action_type}"
    )

    executor = AzureVMExecutor()
    result = executor.execute_action(rollback_action_obj)

    # Add rollback context to result
    result.details["rollback"] = True
    result.details["original_action_id"] = action.action_id
    result.details["original_action_type"] = action.action_type

    return result


def rollback_plan(
    plan_id: str,
    action_ids: Optional[List[str]] = None,
    dry_run: bool = False,
) -> dict:
    """Rollback completed actions in a plan.

    Only rolls back actions that:
    - Are in COMPLETED status
    - Have rollback_possible=True
    - Have not been rolled back already
    - Are not DELETE actions (irreversible)

    Args:
        plan_id: Plan ID
        action_ids: Optional list of specific action IDs to rollback
        dry_run: If True, simulate rollback

    Returns:
        Dictionary with rollback summary

    Raises:
        RollbackError: If plan cannot be rolled back
        ValueError: If plan not found
    """
    manager = PlanManager()
    plan = manager.get_plan(plan_id)

    # Get all completed actions
    all_actions = manager.get_actions(plan_id)
    completed_actions = [
        a for a in all_actions if a.status == ActionStatus.COMPLETED
    ]

    if not completed_actions:
        raise RollbackError(f"No completed actions to rollback in plan {plan_id}")

    # Filter by action_ids if provided
    if action_ids:
        actions_to_rollback = [
            a for a in completed_actions if a.action_id in action_ids
        ]
        if not actions_to_rollback:
            raise RollbackError(
                f"No matching completed actions found for IDs: {', '.join(action_ids)}"
            )
    else:
        actions_to_rollback = completed_actions

    # Filter out actions that can't be rolled back
    rollbackable_actions = []
    skipped_actions = []

    for action in actions_to_rollback:
        can_rollback, reason = can_rollback_action(action)
        if can_rollback:
            rollbackable_actions.append(action)
        else:
            skipped_actions.append((action, reason))
            logger.warning(
                f"Skipping rollback for {action.action_id}: {reason}"
            )

    if not rollbackable_actions:
        raise RollbackError("No actions can be rolled back")

    # Rollback each action
    successful = 0
    failed = 0
    results = []

    for action in rollbackable_actions:
        try:
            logger.info(
                f"Rolling back {action.action_type} on {action.resource_name} "
                f"({'DRY RUN' if dry_run else 'LIVE'})"
            )
            result = rollback_action(action, dry_run=dry_run)

            if result.success:
                # Update action with rollback info
                manager.update_action_status(
                    action.action_id,
                    ActionStatus.COMPLETED,  # Keep as completed
                    rolled_back_at=datetime.now(),
                    rollback_result=result.message,
                )
                successful += 1
                logger.info(f"✓ Rollback completed: {action.action_id}")
            else:
                failed += 1
                logger.error(
                    f"✗ Rollback failed: {action.action_id} - {result.message}"
                )

            results.append(
                {
                    "action_id": action.action_id,
                    "resource_name": action.resource_name,
                    "original_action_type": action.action_type,
                    "rollback_action_type": action.rollback_data.get("action_type"),
                    "success": result.success,
                    "message": result.message,
                }
            )

        except Exception as e:
            logger.exception(f"Unexpected error rolling back action {action.action_id}")
            failed += 1
            results.append(
                {
                    "action_id": action.action_id,
                    "resource_name": action.resource_name,
                    "original_action_type": action.action_type,
                    "success": False,
                    "message": f"Rollback error: {str(e)}",
                }
            )

    return {
        "plan_id": plan_id,
        "total_actions": len(rollbackable_actions),
        "successful": successful,
        "failed": failed,
        "skipped": len(skipped_actions),
        "skipped_reasons": [
            {"action_id": a.action_id, "reason": r} for a, r in skipped_actions
        ],
        "dry_run": dry_run,
        "results": results,
    }


def get_rollback_summary(plan_id: str) -> dict:
    """Get rollback summary for a plan.

    Shows which actions can be rolled back and which cannot.

    Args:
        plan_id: Plan ID

    Returns:
        Dictionary with rollback summary
    """
    manager = PlanManager()
    plan = manager.get_plan(plan_id)
    actions = manager.get_actions(plan_id)

    # Categorize actions
    completed_actions = [a for a in actions if a.status == ActionStatus.COMPLETED]
    already_rolled_back = [a for a in completed_actions if a.rolled_back_at]

    rollbackable = []
    not_rollbackable = []

    for action in completed_actions:
        if action in already_rolled_back:
            continue

        can_rollback, reason = can_rollback_action(action)
        if can_rollback:
            rollbackable.append(action)
        else:
            not_rollbackable.append((action, reason))

    return {
        "plan_id": plan_id,
        "plan_name": plan.plan_name,
        "total_completed": len(completed_actions),
        "already_rolled_back": len(already_rolled_back),
        "can_rollback": len(rollbackable),
        "cannot_rollback": len(not_rollbackable),
        "rollbackable_actions": [
            {
                "action_id": a.action_id,
                "resource_name": a.resource_name,
                "action_type": a.action_type,
                "rollback_action_type": a.rollback_data.get("action_type"),
            }
            for a in rollbackable
        ],
        "not_rollbackable_actions": [
            {
                "action_id": a.action_id,
                "resource_name": a.resource_name,
                "action_type": a.action_type,
                "reason": reason,
            }
            for a, reason in not_rollbackable
        ],
    }
