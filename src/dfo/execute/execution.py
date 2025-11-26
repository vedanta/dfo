"""Execution orchestration for plans and actions."""

import logging
from datetime import datetime
from typing import List, Optional

from dfo.execute.azure_executor import AzureVMExecutor, ExecutionResult
from dfo.execute.models import ActionStatus, ActionType, PlanAction, PlanStatus
from dfo.execute.plan_manager import PlanManager

logger = logging.getLogger(__name__)


class ExecutionError(Exception):
    """Raised when plan execution fails."""

    pass


def execute_action(action: PlanAction, dry_run: bool = False) -> ExecutionResult:
    """Execute a single action.

    Args:
        action: Plan action to execute
        dry_run: If True, simulate execution without making changes

    Returns:
        ExecutionResult with execution details
    """
    if dry_run:
        # Simulate execution
        logger.info(f"[DRY RUN] Would execute {action.action_type} on {action.resource_name}")
        return ExecutionResult(
            success=True,
            message=f"[DRY RUN] Would execute {action.action_type} on {action.resource_name}",
            details={
                "dry_run": True,
                "action_type": action.action_type,
                "resource_name": action.resource_name,
            },
        )

    # Execute on Azure
    executor = AzureVMExecutor()
    return executor.execute_action(action)


def execute_plan(
    plan_id: str,
    action_ids: Optional[List[str]] = None,
    dry_run: bool = False,
) -> dict:
    """Execute an execution plan.

    Executes all actions in a plan (or specific actions if action_ids provided).
    Updates plan and action statuses throughout execution.

    Args:
        plan_id: Plan ID to execute
        action_ids: Optional list of specific action IDs to execute
        dry_run: If True, simulate execution without making changes

    Returns:
        Dictionary with execution summary

    Raises:
        ExecutionError: If plan cannot be executed
        ValueError: If plan not found
    """
    manager = PlanManager()
    plan = manager.get_plan(plan_id)

    # Validate plan status
    if plan.status != PlanStatus.APPROVED:
        raise ExecutionError(
            f"Cannot execute plan: status is '{plan.status}' (must be 'approved')\n"
            f"Approve plan first: dfo azure plan approve {plan_id}"
        )

    # Get actions to execute
    all_actions = manager.get_actions(plan_id)
    if action_ids:
        actions = [a for a in all_actions if a.action_id in action_ids]
        if not actions:
            raise ExecutionError(
                f"No matching actions found for IDs: {', '.join(action_ids)}"
            )
    else:
        actions = all_actions

    if not actions:
        raise ExecutionError("No actions to execute")

    # Update plan status to EXECUTING
    manager.update_plan_status(plan_id, PlanStatus.EXECUTING)

    # Execute each action
    successful = 0
    failed = 0
    skipped = 0
    results = []

    for action in actions:
        try:
            # Update action status to RUNNING
            manager.update_action_status(action.action_id, ActionStatus.RUNNING)

            # Execute the action
            logger.info(
                f"Executing {action.action_type} on {action.resource_name} "
                f"({'DRY RUN' if dry_run else 'LIVE'})"
            )
            result = execute_action(action, dry_run=dry_run)

            # Update action based on result
            if result.success:
                manager.update_action_status(
                    action.action_id,
                    ActionStatus.COMPLETED,
                    execution_result=result.message,
                    execution_details=result.details,
                    rollback_possible=bool(result.rollback_data.get("action_type")),
                    rollback_data=result.rollback_data,
                )
                successful += 1
                logger.info(f"✓ Action completed: {action.action_id}")
            else:
                manager.update_action_status(
                    action.action_id,
                    ActionStatus.FAILED,
                    execution_result=result.message,
                    execution_details=result.details,
                    error_message=result.message,
                    error_code=result.error_code,
                )
                failed += 1
                logger.error(f"✗ Action failed: {action.action_id} - {result.message}")

            results.append(
                {
                    "action_id": action.action_id,
                    "resource_name": action.resource_name,
                    "action_type": action.action_type,
                    "success": result.success,
                    "message": result.message,
                }
            )

        except Exception as e:
            # Unexpected error during execution
            logger.exception(f"Unexpected error executing action {action.action_id}")
            manager.update_action_status(
                action.action_id,
                ActionStatus.FAILED,
                execution_result=f"Execution error: {str(e)}",
                error_message=str(e),
                error_code="UNEXPECTED_ERROR",
            )
            failed += 1
            results.append(
                {
                    "action_id": action.action_id,
                    "resource_name": action.resource_name,
                    "action_type": action.action_type,
                    "success": False,
                    "message": f"Execution error: {str(e)}",
                }
            )

    # Update plan metrics
    manager.update_plan_metrics(plan_id)

    # Update plan status based on results
    if failed == 0:
        final_status = PlanStatus.COMPLETED
    else:
        final_status = PlanStatus.FAILED

    manager.update_plan_status(plan_id, final_status)

    return {
        "plan_id": plan_id,
        "total_actions": len(actions),
        "successful": successful,
        "failed": failed,
        "skipped": skipped,
        "dry_run": dry_run,
        "final_status": final_status,
        "results": results,
    }


def execute_actions_by_type(
    plan_id: str, action_type: ActionType, dry_run: bool = False
) -> dict:
    """Execute only actions of a specific type in a plan.

    Args:
        plan_id: Plan ID
        action_type: Type of actions to execute
        dry_run: If True, simulate execution

    Returns:
        Dictionary with execution summary
    """
    manager = PlanManager()
    all_actions = manager.get_actions(plan_id)

    # Filter by action type
    matching_actions = [a for a in all_actions if a.action_type == action_type]
    action_ids = [a.action_id for a in matching_actions]

    if not action_ids:
        raise ExecutionError(
            f"No actions of type '{action_type}' found in plan {plan_id}"
        )

    return execute_plan(plan_id, action_ids=action_ids, dry_run=dry_run)


def retry_failed_actions(plan_id: str, dry_run: bool = False) -> dict:
    """Retry all failed actions in a plan.

    Args:
        plan_id: Plan ID
        dry_run: If True, simulate execution

    Returns:
        Dictionary with execution summary
    """
    manager = PlanManager()
    all_actions = manager.get_actions(plan_id)

    # Filter failed actions
    failed_actions = [a for a in all_actions if a.status == ActionStatus.FAILED]
    action_ids = [a.action_id for a in failed_actions]

    if not action_ids:
        raise ExecutionError(f"No failed actions found in plan {plan_id}")

    return execute_plan(plan_id, action_ids=action_ids, dry_run=dry_run)
