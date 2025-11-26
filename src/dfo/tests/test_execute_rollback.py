"""Tests for action rollback logic."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from dfo.execute.rollback import (
    can_rollback_action,
    create_rollback_action,
    rollback_action,
    rollback_plan,
    RollbackError,
)
from dfo.execute.models import (
    ActionStatus,
    ActionType,
    PlanAction,
    PlanStatus,
)
from dfo.execute.azure_executor import ExecutionResult


# ============================================================================
# ROLLBACK ELIGIBILITY TESTS
# ============================================================================

class TestRollbackEligibility:
    """Tests for can_rollback_action() function."""

    def test_can_rollback_completed_action(self):
        """Test that completed action with rollback data can be rolled back."""
        action = PlanAction(
            action_id="action-1",
            plan_id="plan-1",
            resource_id="/test/vm",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.STOP,
            estimated_monthly_savings=100.0,
            status=ActionStatus.COMPLETED,
            rollback_possible=True,
            rollback_data={"action_type": "start", "previous_state": "running"},
        )

        can_rollback, reason = can_rollback_action(action)

        assert can_rollback is True
        assert reason is None

    def test_cannot_rollback_not_completed(self):
        """Test that non-completed action cannot be rolled back."""
        action = PlanAction(
            action_id="action-1",
            plan_id="plan-1",
            resource_id="/test/vm",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.STOP,
            estimated_monthly_savings=100.0,
            status=ActionStatus.RUNNING,
            rollback_possible=True,
            rollback_data={"action_type": "start"},
        )

        can_rollback, reason = can_rollback_action(action)

        assert can_rollback is False
        assert "not completed" in reason.lower()

    def test_cannot_rollback_already_rolled_back(self):
        """Test that already rolled back action cannot be rolled back again."""
        action = PlanAction(
            action_id="action-1",
            plan_id="plan-1",
            resource_id="/test/vm",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.STOP,
            estimated_monthly_savings=100.0,
            status=ActionStatus.COMPLETED,
            rollback_possible=True,
            rollback_data={"action_type": "start"},
            rolled_back_at=datetime.now(),
        )

        can_rollback, reason = can_rollback_action(action)

        assert can_rollback is False
        assert "already rolled back" in reason.lower()

    def test_cannot_rollback_delete_action(self):
        """Test that DELETE action cannot be rolled back (irreversible)."""
        action = PlanAction(
            action_id="action-1",
            plan_id="plan-1",
            resource_id="/test/vm",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="stopped-vms",
            action_type=ActionType.DELETE,
            estimated_monthly_savings=200.0,
            status=ActionStatus.COMPLETED,
            rollback_possible=False,
            rollback_data={},
        )

        can_rollback, reason = can_rollback_action(action)

        assert can_rollback is False
        # The function checks rollback_possible first, so we get "not rollbackable" message
        assert reason is not None

    def test_cannot_rollback_no_rollback_data(self):
        """Test that action without rollback data cannot be rolled back."""
        action = PlanAction(
            action_id="action-1",
            plan_id="plan-1",
            resource_id="/test/vm",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.STOP,
            estimated_monthly_savings=100.0,
            status=ActionStatus.COMPLETED,
            rollback_possible=True,
            rollback_data=None,
        )

        can_rollback, reason = can_rollback_action(action)

        assert can_rollback is False
        assert "no rollback data" in reason.lower()

    def test_cannot_rollback_missing_action_type(self):
        """Test that action without action_type in rollback data cannot be rolled back."""
        action = PlanAction(
            action_id="action-1",
            plan_id="plan-1",
            resource_id="/test/vm",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.STOP,
            estimated_monthly_savings=100.0,
            status=ActionStatus.COMPLETED,
            rollback_possible=True,
            rollback_data={"previous_state": "running"},  # Missing action_type
        )

        can_rollback, reason = can_rollback_action(action)

        assert can_rollback is False
        assert "action_type" in reason.lower()

    def test_cannot_rollback_marked_not_rollbackable(self):
        """Test that action marked as not rollbackable cannot be rolled back."""
        action = PlanAction(
            action_id="action-1",
            plan_id="plan-1",
            resource_id="/test/vm",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.STOP,
            estimated_monthly_savings=100.0,
            status=ActionStatus.COMPLETED,
            rollback_possible=False,  # Marked as not rollbackable
            rollback_data={"action_type": "start"},
        )

        can_rollback, reason = can_rollback_action(action)

        assert can_rollback is False
        assert "not rollbackable" in reason.lower()


# ============================================================================
# CREATE ROLLBACK ACTION TESTS
# ============================================================================

class TestCreateRollbackAction:
    """Tests for create_rollback_action() function."""

    def test_create_rollback_for_stop_action(self):
        """Test creating rollback action for STOP."""
        action = PlanAction(
            action_id="action-1",
            plan_id="plan-1",
            resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            resource_name="vm1",
            resource_type="vm",
            resource_group="rg1",
            location="eastus",
            subscription_id="sub1",
            analysis_type="idle-vms",
            action_type=ActionType.STOP,
            estimated_monthly_savings=100.0,
            status=ActionStatus.COMPLETED,
            rollback_possible=True,
            rollback_data={"action_type": "start", "previous_state": "running"},
        )

        rollback = create_rollback_action(action)

        assert rollback.action_id == "rollback-action-1"
        assert rollback.plan_id == "plan-1"
        assert rollback.resource_id == action.resource_id
        assert rollback.resource_name == "vm1"
        assert rollback.action_type == ActionType.START
        assert rollback.status == ActionStatus.PENDING
        assert rollback.rollback_possible is False  # Can't rollback a rollback
        assert rollback.estimated_monthly_savings == 0.0  # No savings from rollback
        assert "rollback" in rollback.analysis_type

    def test_create_rollback_for_deallocate_action(self):
        """Test creating rollback action for DEALLOCATE."""
        action = PlanAction(
            action_id="action-2",
            plan_id="plan-1",
            resource_id="/test/vm",
            resource_name="vm2",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.DEALLOCATE,
            estimated_monthly_savings=150.0,
            status=ActionStatus.COMPLETED,
            rollback_possible=True,
            rollback_data={"action_type": "start", "previous_state": "running"},
        )

        rollback = create_rollback_action(action)

        assert rollback.action_type == ActionType.START
        assert rollback.action_id == "rollback-action-2"

    def test_create_rollback_for_downsize_action(self):
        """Test creating rollback action for DOWNSIZE (restores original size)."""
        action = PlanAction(
            action_id="action-3",
            plan_id="plan-1",
            resource_id="/test/vm",
            resource_name="vm3",
            resource_type="vm",
            analysis_type="low-cpu",
            action_type=ActionType.DOWNSIZE,
            estimated_monthly_savings=200.0,
            status=ActionStatus.COMPLETED,
            rollback_possible=True,
            rollback_data={
                "action_type": "downsize",
                "original_size": "Standard_D4s_v3",
                "new_size": "Standard_B2s",
            },
        )

        rollback = create_rollback_action(action)

        assert rollback.action_type == ActionType.DOWNSIZE
        assert rollback.action_params["new_size"] == "Standard_D4s_v3"  # Restore original
        assert rollback.action_params["rollback_from_size"] == "Standard_B2s"

    def test_create_rollback_fails_for_ineligible_action(self):
        """Test that creating rollback for ineligible action raises error."""
        action = PlanAction(
            action_id="action-4",
            plan_id="plan-1",
            resource_id="/test/vm",
            resource_name="vm4",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.STOP,
            estimated_monthly_savings=100.0,
            status=ActionStatus.RUNNING,  # Not completed
            rollback_possible=True,
            rollback_data={"action_type": "start"},
        )

        with pytest.raises(RollbackError, match="not completed"):
            create_rollback_action(action)


# ============================================================================
# ROLLBACK ACTION EXECUTION TESTS
# ============================================================================

class TestRollbackActionExecution:
    """Tests for rollback_action() function."""

    @patch('dfo.execute.rollback.AzureVMExecutor')
    def test_rollback_action_success(self, mock_executor_class):
        """Test successful action rollback."""
        action = PlanAction(
            action_id="action-1",
            plan_id="plan-1",
            resource_id="/test/vm",
            resource_name="vm1",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.STOP,
            estimated_monthly_savings=100.0,
            status=ActionStatus.COMPLETED,
            rollback_possible=True,
            rollback_data={"action_type": "start", "previous_state": "running"},
        )

        # Mock Azure executor
        mock_executor = Mock()
        mock_executor.execute_action.return_value = ExecutionResult(
            success=True,
            message="VM started successfully",
            details={"resource_name": "vm1"},
        )
        mock_executor_class.return_value = mock_executor

        result = rollback_action(action, dry_run=False)

        assert result.success is True
        assert "started" in result.message.lower()
        assert result.details["rollback"] is True
        assert result.details["original_action_id"] == "action-1"
        assert result.details["original_action_type"] == ActionType.STOP
        mock_executor.execute_action.assert_called_once()

    def test_rollback_action_dry_run(self):
        """Test dry run rollback."""
        action = PlanAction(
            action_id="action-1",
            plan_id="plan-1",
            resource_id="/test/vm",
            resource_name="vm1",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.DEALLOCATE,
            estimated_monthly_savings=100.0,
            status=ActionStatus.COMPLETED,
            rollback_possible=True,
            rollback_data={"action_type": "start", "previous_state": "running"},
        )

        result = rollback_action(action, dry_run=True)

        assert result.success is True
        assert "dry run" in result.message.lower()
        assert result.details["dry_run"] is True
        assert result.details["rollback_action_type"] == ActionType.START
        assert result.details["resource_name"] == "vm1"

    def test_rollback_action_fails_for_ineligible(self):
        """Test that rollback fails for ineligible action."""
        action = PlanAction(
            action_id="action-1",
            plan_id="plan-1",
            resource_id="/test/vm",
            resource_name="vm1",
            resource_type="vm",
            analysis_type="stopped-vms",
            action_type=ActionType.DELETE,
            estimated_monthly_savings=100.0,
            status=ActionStatus.COMPLETED,
            rollback_possible=False,
        )

        with pytest.raises(RollbackError, match="Cannot rollback"):
            rollback_action(action, dry_run=False)


# ============================================================================
# PLAN ROLLBACK TESTS
# ============================================================================

class TestPlanRollback:
    """Tests for rollback_plan() function."""

    @patch('dfo.execute.rollback.rollback_action')
    @patch('dfo.execute.rollback.PlanManager')
    def test_rollback_plan_all_actions(self, mock_manager_class, mock_rollback_action):
        """Test rolling back all actions in a plan."""
        # Mock plan manager
        mock_manager = Mock()
        mock_plan = Mock(plan_id="plan-1", status=PlanStatus.COMPLETED)
        mock_manager.get_plan.return_value = mock_plan

        # Create proper PlanAction instances (not Mocks)
        actions = [
            PlanAction(
                action_id="action-1",
                plan_id="plan-1",
                resource_id="/test/vm1",
                resource_name="vm1",
                resource_type="vm",
                analysis_type="idle-vms",
                action_type=ActionType.STOP,
                estimated_monthly_savings=100.0,
                status=ActionStatus.COMPLETED,
                rollback_possible=True,
                rollback_data={"action_type": "start"},
            ),
            PlanAction(
                action_id="action-2",
                plan_id="plan-1",
                resource_id="/test/vm2",
                resource_name="vm2",
                resource_type="vm",
                analysis_type="idle-vms",
                action_type=ActionType.DEALLOCATE,
                estimated_monthly_savings=150.0,
                status=ActionStatus.COMPLETED,
                rollback_possible=True,
                rollback_data={"action_type": "start"},
            ),
            PlanAction(
                action_id="action-3",
                plan_id="plan-1",
                resource_id="/test/vm3",
                resource_name="vm3",
                resource_type="vm",
                analysis_type="stopped-vms",
                action_type=ActionType.DELETE,
                estimated_monthly_savings=200.0,
                status=ActionStatus.COMPLETED,
                rollback_possible=False,  # Not rollbackable
            ),
        ]
        mock_manager.get_actions.return_value = actions
        mock_manager_class.return_value = mock_manager

        # Mock rollback results
        mock_rollback_action.return_value = ExecutionResult(
            success=True,
            message="Rollback successful",
        )

        result = rollback_plan("plan-1", dry_run=False)

        assert result["plan_id"] == "plan-1"
        assert result["total_actions"] == 2  # Only rollbackable actions
        assert result["successful"] == 2
        assert result["failed"] == 0
        assert result["skipped"] == 1  # DELETE action skipped
        assert mock_rollback_action.call_count == 2  # Called for 2 rollbackable actions

    @patch('dfo.execute.rollback.rollback_action')
    @patch('dfo.execute.rollback.PlanManager')
    def test_rollback_plan_specific_actions(self, mock_manager_class, mock_rollback_action):
        """Test rolling back specific actions only."""
        mock_manager = Mock()
        mock_plan = Mock(plan_id="plan-1")
        mock_manager.get_plan.return_value = mock_plan

        actions = [
            PlanAction(
                action_id="action-1",
                plan_id="plan-1",
                resource_id="/test/vm1",
                resource_name="vm1",
                resource_type="vm",
                analysis_type="idle-vms",
                action_type=ActionType.STOP,
                estimated_monthly_savings=100.0,
                status=ActionStatus.COMPLETED,
                rollback_possible=True,
                rollback_data={"action_type": "start"},
            ),
            PlanAction(
                action_id="action-2",
                plan_id="plan-1",
                resource_id="/test/vm2",
                resource_name="vm2",
                resource_type="vm",
                analysis_type="idle-vms",
                action_type=ActionType.DEALLOCATE,
                estimated_monthly_savings=150.0,
                status=ActionStatus.COMPLETED,
                rollback_possible=True,
                rollback_data={"action_type": "start"},
            ),
        ]
        mock_manager.get_actions.return_value = actions
        mock_manager_class.return_value = mock_manager

        mock_rollback_action.return_value = ExecutionResult(success=True, message="OK")

        result = rollback_plan("plan-1", action_ids=["action-1"], dry_run=False)

        assert result["total_actions"] == 1  # Only action-1
        assert result["successful"] == 1
        assert mock_rollback_action.call_count == 1

    @patch('dfo.execute.rollback.PlanManager')
    def test_rollback_plan_dry_run(self, mock_manager_class):
        """Test dry run plan rollback."""
        mock_manager = Mock()
        mock_plan = Mock(plan_id="plan-1")
        mock_manager.get_plan.return_value = mock_plan

        actions = [
            PlanAction(
                action_id="action-1",
                plan_id="plan-1",
                resource_id="/test/vm1",
                resource_name="vm1",
                resource_type="vm",
                analysis_type="idle-vms",
                action_type=ActionType.STOP,
                estimated_monthly_savings=100.0,
                status=ActionStatus.COMPLETED,
                rollback_possible=True,
                rollback_data={"action_type": "start"},
            ),
        ]
        mock_manager.get_actions.return_value = actions
        mock_manager_class.return_value = mock_manager

        result = rollback_plan("plan-1", dry_run=True)

        assert result["dry_run"] is True
        assert result["total_actions"] == 1
        assert result["successful"] == 1  # Dry run succeeds
        # Dry run should still execute rollback_action with dry_run=True


# ============================================================================
# EDGE CASES
# ============================================================================

class TestRollbackEdgeCases:
    """Tests for rollback edge cases."""

    def test_rollback_action_types(self):
        """Test rollback eligibility for different action types."""
        # STOP -> START (rollbackable)
        stop_action = PlanAction(
            action_id="a1",
            plan_id="p1",
            resource_id="/test/vm",
            resource_name="vm",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.STOP,
            estimated_monthly_savings=100.0,
            status=ActionStatus.COMPLETED,
            rollback_possible=True,
            rollback_data={"action_type": "start"},
        )
        assert can_rollback_action(stop_action)[0] is True

        # DEALLOCATE -> START (rollbackable)
        deallocate_action = PlanAction(
            action_id="a2",
            plan_id="p1",
            resource_id="/test/vm",
            resource_name="vm",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.DEALLOCATE,
            estimated_monthly_savings=100.0,
            status=ActionStatus.COMPLETED,
            rollback_possible=True,
            rollback_data={"action_type": "start"},
        )
        assert can_rollback_action(deallocate_action)[0] is True

        # DELETE (NOT rollbackable)
        delete_action = PlanAction(
            action_id="a3",
            plan_id="p1",
            resource_id="/test/vm",
            resource_name="vm",
            resource_type="vm",
            analysis_type="stopped-vms",
            action_type=ActionType.DELETE,
            estimated_monthly_savings=100.0,
            status=ActionStatus.COMPLETED,
            rollback_possible=False,
        )
        assert can_rollback_action(delete_action)[0] is False

        # DOWNSIZE -> DOWNSIZE back (rollbackable)
        downsize_action = PlanAction(
            action_id="a4",
            plan_id="p1",
            resource_id="/test/vm",
            resource_name="vm",
            resource_type="vm",
            analysis_type="low-cpu",
            action_type=ActionType.DOWNSIZE,
            estimated_monthly_savings=100.0,
            status=ActionStatus.COMPLETED,
            rollback_possible=True,
            rollback_data={"action_type": "downsize", "original_size": "Standard_D4s_v3"},
        )
        assert can_rollback_action(downsize_action)[0] is True
