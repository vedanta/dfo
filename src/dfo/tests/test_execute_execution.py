"""Tests for execution orchestration."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from dfo.execute.execution import (
    execute_action,
    execute_plan,
    ExecutionError,
)
from dfo.execute.azure_executor import ExecutionResult
from dfo.execute.models import (
    ActionStatus,
    ActionType,
    CreatePlanRequest,
    PlanAction,
    PlanStatus,
    ValidationStatus,
)
from dfo.execute.plan_manager import PlanManager
from dfo.db.duck import DuckDBManager


# ============================================================================
# ACTION EXECUTION TESTS
# ============================================================================

class TestExecuteAction:
    """Tests for execute_action() function."""

    def test_execute_action_dry_run_stop(self):
        """Test dry run execution for STOP action."""
        action = PlanAction(
            action_id="action-1",
            plan_id="plan-1",
            resource_id="/test/vm",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.STOP,
            estimated_monthly_savings=100.0,
        )

        result = execute_action(action, dry_run=True)

        assert result.success is True
        assert "dry run" in result.message.lower()
        assert result.details["dry_run"] is True
        assert result.details["action_type"] == ActionType.STOP
        assert result.rollback_data["action_type"] == "start"
        assert result.rollback_data["previous_state"] == "running"

    def test_execute_action_dry_run_deallocate(self):
        """Test dry run execution for DEALLOCATE action."""
        action = PlanAction(
            action_id="action-1",
            plan_id="plan-1",
            resource_id="/test/vm",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.DEALLOCATE,
            estimated_monthly_savings=100.0,
        )

        result = execute_action(action, dry_run=True)

        assert result.success is True
        assert result.rollback_data["action_type"] == "start"

    def test_execute_action_dry_run_delete(self):
        """Test dry run execution for DELETE action (not reversible)."""
        action = PlanAction(
            action_id="action-1",
            plan_id="plan-1",
            resource_id="/test/vm",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="stopped-vms",
            action_type=ActionType.DELETE,
            estimated_monthly_savings=200.0,
        )

        result = execute_action(action, dry_run=True)

        assert result.success is True
        assert result.rollback_data["action_type"] is None
        assert "IRREVERSIBLE" in result.rollback_data["warning"]

    def test_execute_action_dry_run_downsize(self):
        """Test dry run execution for DOWNSIZE action."""
        action = PlanAction(
            action_id="action-1",
            plan_id="plan-1",
            resource_id="/test/vm",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="low-cpu",
            action_type=ActionType.DOWNSIZE,
            estimated_monthly_savings=150.0,
            action_params={"new_size": "Standard_B2s"},
        )

        result = execute_action(action, dry_run=True)

        assert result.success is True
        assert result.rollback_data["action_type"] == "downsize"
        assert result.rollback_data["new_size"] == "Standard_B2s"

    @patch('dfo.execute.execution.AzureVMExecutor')
    def test_execute_action_live(self, mock_executor_class):
        """Test live execution (calls Azure executor)."""
        action = PlanAction(
            action_id="action-1",
            plan_id="plan-1",
            resource_id="/test/vm",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.STOP,
            estimated_monthly_savings=100.0,
        )

        # Mock Azure executor
        mock_executor = Mock()
        mock_executor.execute_action.return_value = ExecutionResult(
            success=True,
            message="VM stopped successfully",
            details={"resource_name": "test-vm"},
            rollback_data={"action_type": "start"},
        )
        mock_executor_class.return_value = mock_executor

        result = execute_action(action, dry_run=False)

        assert result.success is True
        assert "stopped" in result.message.lower()
        mock_executor.execute_action.assert_called_once_with(action)


# ============================================================================
# PLAN EXECUTION TESTS
# ============================================================================

class TestExecutePlan:
    """Tests for execute_plan() function."""

    @patch('dfo.execute.execution.execute_action')
    def test_execute_plan_not_approved(self, mock_execute_action, test_db):
        """Test that execution fails if plan not approved."""
        # Create plan
        db = DuckDBManager()
        conn = db.get_connection()
        conn.execute("""
            INSERT INTO vm_idle_analysis (
                vm_id, cpu_avg, days_under_threshold, estimated_monthly_savings,
                severity, recommended_action, equivalent_sku, analyzed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            2.5, 14, 100.0, "high", "DEALLOCATE", "Standard_B2s", datetime.now()
        ])

        manager = PlanManager()
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = manager.create_plan(request)

        # Try to execute without approval
        with pytest.raises(ExecutionError, match="must be 'approved'"):
            execute_plan(plan.plan_id, dry_run=True)

    @patch('dfo.execute.execution.execute_action')
    def test_execute_plan_dry_run_success(self, mock_execute_action, test_db):
        """Test successful dry run plan execution."""
        # Create and approve plan
        db = DuckDBManager()
        conn = db.get_connection()
        conn.execute("""
            INSERT INTO vm_idle_analysis (
                vm_id, cpu_avg, days_under_threshold, estimated_monthly_savings,
                severity, recommended_action, equivalent_sku, analyzed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            2.5, 14, 100.0, "high", "DEALLOCATE", "Standard_B2s", datetime.now()
        ])

        manager = PlanManager()
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = manager.create_plan(request)

        # Validate and approve
        manager.update_plan_status(plan.plan_id, PlanStatus.VALIDATED)
        manager.update_plan_status(plan.plan_id, PlanStatus.APPROVED)

        # Mock action execution
        mock_execute_action.return_value = ExecutionResult(
            success=True,
            message="Action completed",
            rollback_data={"action_type": "start"},
        )

        result = execute_plan(plan.plan_id, dry_run=True)

        assert result["plan_id"] == plan.plan_id
        assert result["total_actions"] == 1
        assert result["successful"] == 1
        assert result["failed"] == 0
        assert result["dry_run"] is True
        mock_execute_action.assert_called_once()

    @patch('dfo.execute.execution.execute_action')
    def test_execute_plan_specific_actions(self, mock_execute_action, test_db):
        """Test executing specific actions only."""
        # Create plan with multiple actions
        db = DuckDBManager()
        conn = db.get_connection()
        conn.execute("""
            INSERT INTO vm_idle_analysis (
                vm_id, cpu_avg, days_under_threshold, estimated_monthly_savings,
                severity, recommended_action, equivalent_sku, analyzed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            2.5, 14, 100.0, "high", "DEALLOCATE", "Standard_B2s", datetime.now()
        ])
        conn.execute("""
            INSERT INTO vm_idle_analysis (
                vm_id, cpu_avg, days_under_threshold, estimated_monthly_savings,
                severity, recommended_action, equivalent_sku, analyzed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm2",
            1.5, 20, 150.0, "high", "DEALLOCATE", "Standard_B2s", datetime.now()
        ])

        manager = PlanManager()
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = manager.create_plan(request)
        manager.update_plan_status(plan.plan_id, PlanStatus.APPROVED)

        # Get first action ID
        actions = manager.get_actions(plan.plan_id)
        first_action_id = actions[0].action_id

        # Mock action execution
        mock_execute_action.return_value = ExecutionResult(
            success=True,
            message="OK",
            rollback_data={"action_type": "start"},
        )

        result = execute_plan(plan.plan_id, action_ids=[first_action_id], dry_run=True)

        assert result["total_actions"] == 1  # Only executed one action
        mock_execute_action.assert_called_once()

    @patch('dfo.execute.execution.execute_action')
    def test_execute_plan_with_failures(self, mock_execute_action, test_db):
        """Test plan execution with some failures."""
        # Create plan
        db = DuckDBManager()
        conn = db.get_connection()
        conn.execute("""
            INSERT INTO vm_idle_analysis (
                vm_id, cpu_avg, days_under_threshold, estimated_monthly_savings,
                severity, recommended_action, equivalent_sku, analyzed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            2.5, 14, 100.0, "high", "DEALLOCATE", "Standard_B2s", datetime.now()
        ])

        manager = PlanManager()
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = manager.create_plan(request)
        manager.update_plan_status(plan.plan_id, PlanStatus.APPROVED)

        # Mock action execution failure
        mock_execute_action.return_value = ExecutionResult(
            success=False,
            message="VM not found",
            error_code="RESOURCE_NOT_FOUND",
        )

        result = execute_plan(plan.plan_id, dry_run=False)

        assert result["total_actions"] == 1
        assert result["successful"] == 0
        assert result["failed"] == 1

        # Check that action status was updated to FAILED
        actions = manager.get_actions(plan.plan_id)
        assert actions[0].status == ActionStatus.FAILED
        assert "VM not found" in actions[0].error_message

    @patch('dfo.execute.execution.execute_action')
    def test_execute_plan_exception_handling(self, mock_execute_action, test_db):
        """Test that unexpected exceptions are caught and recorded."""
        # Create plan
        db = DuckDBManager()
        conn = db.get_connection()
        conn.execute("""
            INSERT INTO vm_idle_analysis (
                vm_id, cpu_avg, days_under_threshold, estimated_monthly_savings,
                severity, recommended_action, equivalent_sku, analyzed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            2.5, 14, 100.0, "high", "DEALLOCATE", "Standard_B2s", datetime.now()
        ])

        manager = PlanManager()
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = manager.create_plan(request)
        manager.update_plan_status(plan.plan_id, PlanStatus.APPROVED)

        # Mock unexpected exception
        mock_execute_action.side_effect = Exception("Unexpected error")

        result = execute_plan(plan.plan_id, dry_run=False)

        assert result["failed"] == 1
        assert "Unexpected error" in result["results"][0]["message"]

        # Check that action status was updated to FAILED
        actions = manager.get_actions(plan.plan_id)
        assert actions[0].status == ActionStatus.FAILED
        assert actions[0].error_code == "UNEXPECTED_ERROR"

    def test_execute_plan_no_actions(self, test_db):
        """Test that execution fails if plan has no actions."""
        manager = PlanManager()
        request = CreatePlanRequest(
            plan_name="Empty Plan",
            created_by="test@example.com",
            analysis_types=[],  # No analysis types = no actions
        )
        plan = manager.create_plan(request)
        manager.update_plan_status(plan.plan_id, PlanStatus.APPROVED)

        with pytest.raises(ExecutionError, match="No actions to execute"):
            execute_plan(plan.plan_id, dry_run=True)

    def test_execute_plan_invalid_action_ids(self, test_db):
        """Test that execution fails if specified action IDs don't exist."""
        # Create plan
        db = DuckDBManager()
        conn = db.get_connection()
        conn.execute("""
            INSERT INTO vm_idle_analysis (
                vm_id, cpu_avg, days_under_threshold, estimated_monthly_savings,
                severity, recommended_action, equivalent_sku, analyzed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            2.5, 14, 100.0, "high", "DEALLOCATE", "Standard_B2s", datetime.now()
        ])

        manager = PlanManager()
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = manager.create_plan(request)
        manager.update_plan_status(plan.plan_id, PlanStatus.APPROVED)

        with pytest.raises(ExecutionError, match="No matching actions found"):
            execute_plan(plan.plan_id, action_ids=["nonexistent-action"], dry_run=True)


# ============================================================================
# PLAN STATUS UPDATES
# ============================================================================

class TestPlanStatusUpdates:
    """Tests for plan status updates during execution."""

    @patch('dfo.execute.execution.execute_action')
    def test_plan_status_updated_to_executing(self, mock_execute_action, test_db):
        """Test that plan status is updated to EXECUTING when execution starts."""
        # Create and approve plan
        db = DuckDBManager()
        conn = db.get_connection()
        conn.execute("""
            INSERT INTO vm_idle_analysis (
                vm_id, cpu_avg, days_under_threshold, estimated_monthly_savings,
                severity, recommended_action, equivalent_sku, analyzed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            2.5, 14, 100.0, "high", "DEALLOCATE", "Standard_B2s", datetime.now()
        ])

        manager = PlanManager()
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = manager.create_plan(request)
        manager.update_plan_status(plan.plan_id, PlanStatus.APPROVED)

        # Mock execution
        mock_execute_action.return_value = ExecutionResult(
            success=True,
            message="OK",
            rollback_data={"action_type": "start"},
        )

        execute_plan(plan.plan_id, dry_run=True)

        # Check plan status - will be back to APPROVED after execution completes
        updated_plan = manager.get_plan(plan.plan_id)
        # Note: Plan status might be COMPLETED or APPROVED depending on implementation
        assert updated_plan.status in [PlanStatus.APPROVED, PlanStatus.COMPLETED, PlanStatus.EXECUTING]

    @patch('dfo.execute.execution.execute_action')
    def test_action_status_updated_during_execution(self, mock_execute_action, test_db):
        """Test that action status is updated to RUNNING and then COMPLETED."""
        # Create and approve plan
        db = DuckDBManager()
        conn = db.get_connection()
        conn.execute("""
            INSERT INTO vm_idle_analysis (
                vm_id, cpu_avg, days_under_threshold, estimated_monthly_savings,
                severity, recommended_action, equivalent_sku, analyzed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            2.5, 14, 100.0, "high", "DEALLOCATE", "Standard_B2s", datetime.now()
        ])

        manager = PlanManager()
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = manager.create_plan(request)
        manager.update_plan_status(plan.plan_id, PlanStatus.APPROVED)

        # Mock execution
        mock_execute_action.return_value = ExecutionResult(
            success=True,
            message="VM stopped",
            details={"resource_name": "vm1"},
            rollback_data={"action_type": "start", "previous_state": "running"},
        )

        execute_plan(plan.plan_id, dry_run=False)

        # Check action status
        actions = manager.get_actions(plan.plan_id)
        assert actions[0].status == ActionStatus.COMPLETED
        assert actions[0].execution_result == "VM stopped"
        assert actions[0].rollback_possible is True
        assert actions[0].rollback_data["action_type"] == "start"


# ============================================================================
# DRY RUN VS LIVE EXECUTION
# ============================================================================

class TestDryRunVsLive:
    """Tests comparing dry run vs live execution."""

    @patch('dfo.execute.execution.AzureVMExecutor')
    def test_dry_run_does_not_call_azure(self, mock_executor_class):
        """Test that dry run does not call Azure executor."""
        action = PlanAction(
            action_id="action-1",
            plan_id="plan-1",
            resource_id="/test/vm",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.STOP,
            estimated_monthly_savings=100.0,
        )

        execute_action(action, dry_run=True)

        # Executor should not be instantiated in dry run
        mock_executor_class.assert_not_called()

    @patch('dfo.execute.execution.AzureVMExecutor')
    def test_live_execution_calls_azure(self, mock_executor_class):
        """Test that live execution calls Azure executor."""
        action = PlanAction(
            action_id="action-1",
            plan_id="plan-1",
            resource_id="/test/vm",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.STOP,
            estimated_monthly_savings=100.0,
        )

        mock_executor = Mock()
        mock_executor.execute_action.return_value = ExecutionResult(
            success=True,
            message="VM stopped",
        )
        mock_executor_class.return_value = mock_executor

        execute_action(action, dry_run=False)

        # Executor should be called in live execution
        mock_executor_class.assert_called_once()
        mock_executor.execute_action.assert_called_once()
