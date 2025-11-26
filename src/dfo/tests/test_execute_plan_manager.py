"""Tests for execution plan manager (CRUD, actions, history)."""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from dfo.execute.plan_manager import (
    PlanManager,
    generate_plan_id,
    generate_action_id,
    generate_history_id,
)
from dfo.execute.models import (
    ActionStatus,
    ActionType,
    CreatePlanRequest,
    PlanStatus,
    Severity,
)
from dfo.db.duck import DuckDBManager


@pytest.fixture
def plan_manager(test_db):
    """Create PlanManager instance with test database."""
    return PlanManager()


@pytest.fixture
def sample_idle_vm_analysis(test_db):
    """Insert sample idle VM analysis for plan creation."""
    db = DuckDBManager()

    db.conn.execute("""
        INSERT INTO vm_idle_analysis (
            vm_id, vm_name, resource_group, location, vm_size,
            power_state, severity, cpu_average, days_under_threshold,
            recommended_action, equivalent_sku, estimated_monthly_savings,
            annual_savings, analyzed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/test-vm1",
        "test-vm1",
        "rg1",
        "eastus",
        "Standard_D2s_v3",
        "running",
        "high",
        2.5,
        14,
        "DEALLOCATE",
        "Standard_B2s",
        100.0,
        1200.0,
        datetime.now().isoformat()
    ])

    db.conn.execute("""
        INSERT INTO vm_idle_analysis (
            vm_id, vm_name, resource_group, location, vm_size,
            power_state, severity, cpu_average, days_under_threshold,
            recommended_action, equivalent_sku, estimated_monthly_savings,
            annual_savings, analyzed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/test-vm2",
        "test-vm2",
        "rg1",
        "westus",
        "Standard_E4s_v3",
        "running",
        "medium",
        3.0,
        10,
        "DEALLOCATE",
        "Standard_E2s_v3",
        200.0,
        2400.0,
        datetime.now().isoformat()
    ])

    yield db


# ============================================================================
# ID GENERATION TESTS
# ============================================================================

class TestIDGeneration:
    """Tests for ID generation functions."""

    def test_generate_plan_id_format(self):
        """Test plan ID format."""
        plan_id = generate_plan_id()
        assert plan_id.startswith("plan-")
        assert len(plan_id) <= 20  # Should be truncated to 20 chars

    def test_generate_plan_id_unique(self):
        """Test that plan IDs are unique."""
        ids = {generate_plan_id() for _ in range(100)}
        assert len(ids) == 100  # All should be unique

    def test_generate_action_id_format(self):
        """Test action ID format."""
        action_id = generate_action_id()
        assert action_id.startswith("action-")
        assert len(action_id) <= 24

    def test_generate_action_id_unique(self):
        """Test that action IDs are unique."""
        ids = {generate_action_id() for _ in range(100)}
        assert len(ids) == 100

    def test_generate_history_id_format(self):
        """Test history ID format."""
        history_id = generate_history_id()
        assert history_id.startswith("hist-")
        assert len(history_id) <= 22

    def test_generate_history_id_unique(self):
        """Test that history IDs are unique."""
        ids = {generate_history_id() for _ in range(100)}
        assert len(ids) == 100


# ============================================================================
# PLAN CRUD TESTS
# ============================================================================

class TestPlanCRUD:
    """Tests for plan CRUD operations."""

    def test_create_plan_basic(self, plan_manager, sample_idle_vm_analysis):
        """Test creating a basic plan."""
        request = CreatePlanRequest(
            plan_name="Test Plan",
            description="A test execution plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
            severity_filter="high",
            limit=None,
            tags={"environment": "test"},
        )

        plan = plan_manager.create_plan(request)

        assert plan.plan_id.startswith("plan-")
        assert plan.plan_name == "Test Plan"
        assert plan.description == "A test execution plan"
        assert plan.created_by == "test@example.com"
        assert plan.status == PlanStatus.DRAFT
        assert plan.analysis_types == ["idle-vms"]
        assert plan.severity_filter == "high"
        assert plan.total_actions == 1  # Only high severity VM
        assert plan.total_estimated_savings == 100.0
        assert plan.tags == {"environment": "test"}
        assert plan.expires_at is not None

    def test_create_plan_with_limit(self, plan_manager, sample_idle_vm_analysis):
        """Test creating plan with action limit."""
        request = CreatePlanRequest(
            plan_name="Limited Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
            limit=1,
        )

        plan = plan_manager.create_plan(request)
        actions = plan_manager.get_actions(plan.plan_id)

        assert plan.total_actions == 1
        assert len(actions) == 1

    def test_create_plan_multiple_analysis_types(self, plan_manager, sample_idle_vm_analysis):
        """Test creating plan with multiple analysis types."""
        request = CreatePlanRequest(
            plan_name="Multi-Analysis Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )

        plan = plan_manager.create_plan(request)
        assert plan.total_actions == 2  # Both VMs

    def test_get_plan_success(self, plan_manager, sample_idle_vm_analysis):
        """Test retrieving an existing plan."""
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        created_plan = plan_manager.create_plan(request)

        retrieved_plan = plan_manager.get_plan(created_plan.plan_id)

        assert retrieved_plan.plan_id == created_plan.plan_id
        assert retrieved_plan.plan_name == created_plan.plan_name
        assert retrieved_plan.status == created_plan.status

    def test_get_plan_not_found(self, plan_manager):
        """Test getting non-existent plan raises error."""
        with pytest.raises(ValueError, match="Plan not found"):
            plan_manager.get_plan("plan-nonexistent")

    def test_list_plans_empty(self, plan_manager):
        """Test listing plans when none exist."""
        plans = plan_manager.list_plans()
        assert len(plans) == 0

    def test_list_plans_all(self, plan_manager, sample_idle_vm_analysis):
        """Test listing all plans."""
        # Create multiple plans
        for i in range(3):
            request = CreatePlanRequest(
                plan_name=f"Plan {i}",
                created_by="test@example.com",
                analysis_types=["idle-vms"],
            )
            plan_manager.create_plan(request)

        plans = plan_manager.list_plans()
        assert len(plans) == 3

    def test_list_plans_filter_by_status(self, plan_manager, sample_idle_vm_analysis):
        """Test filtering plans by status."""
        request1 = CreatePlanRequest(
            plan_name="Draft Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan1 = plan_manager.create_plan(request1)

        request2 = CreatePlanRequest(
            plan_name="Validated Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan2 = plan_manager.create_plan(request2)
        plan_manager.update_plan_status(plan2.plan_id, PlanStatus.VALIDATED)

        draft_plans = plan_manager.list_plans(status=PlanStatus.DRAFT)
        validated_plans = plan_manager.list_plans(status=PlanStatus.VALIDATED)

        assert len(draft_plans) == 1
        assert draft_plans[0].plan_id == plan1.plan_id
        assert len(validated_plans) == 1
        assert validated_plans[0].plan_id == plan2.plan_id

    def test_list_plans_with_limit(self, plan_manager, sample_idle_vm_analysis):
        """Test listing plans with limit."""
        for i in range(5):
            request = CreatePlanRequest(
                plan_name=f"Plan {i}",
                created_by="test@example.com",
                analysis_types=["idle-vms"],
            )
            plan_manager.create_plan(request)

        plans = plan_manager.list_plans(limit=3)
        assert len(plans) == 3

    def test_list_plans_sort_by_savings(self, plan_manager, sample_idle_vm_analysis):
        """Test sorting plans by estimated savings."""
        # Create plans with different savings
        request1 = CreatePlanRequest(
            plan_name="High Savings",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
            severity_filter=None,  # All VMs
        )
        plan1 = plan_manager.create_plan(request1)

        request2 = CreatePlanRequest(
            plan_name="Low Savings",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
            severity_filter="high",  # Only high severity
        )
        plan2 = plan_manager.create_plan(request2)

        plans = plan_manager.list_plans(sort_by="total_estimated_savings")

        # Should be sorted descending by savings
        assert plans[0].total_estimated_savings >= plans[1].total_estimated_savings

    def test_update_plan_status_to_validated(self, plan_manager, sample_idle_vm_analysis):
        """Test updating plan status to VALIDATED."""
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = plan_manager.create_plan(request)

        updated_plan = plan_manager.update_plan_status(
            plan.plan_id, PlanStatus.VALIDATED
        )

        assert updated_plan.status == PlanStatus.VALIDATED
        assert updated_plan.validated_at is not None

    def test_update_plan_status_to_approved(self, plan_manager, sample_idle_vm_analysis):
        """Test updating plan status to APPROVED."""
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = plan_manager.create_plan(request)

        # First validate
        plan_manager.update_plan_status(plan.plan_id, PlanStatus.VALIDATED)

        # Then approve
        updated_plan = plan_manager.update_plan_status(
            plan.plan_id,
            PlanStatus.APPROVED,
            approved_by="approver@example.com",
        )

        assert updated_plan.status == PlanStatus.APPROVED
        assert updated_plan.approved_at is not None
        assert updated_plan.approved_by == "approver@example.com"

    def test_update_plan_status_with_validation_errors(self, plan_manager, sample_idle_vm_analysis):
        """Test updating plan with validation errors."""
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = plan_manager.create_plan(request)

        errors = [{"action_id": "action-1", "error": "Resource not found"}]
        updated_plan = plan_manager.update_plan_status(
            plan.plan_id, PlanStatus.DRAFT, validation_errors=errors
        )

        assert updated_plan.validation_errors == errors

    def test_delete_plan_draft_status(self, plan_manager, sample_idle_vm_analysis):
        """Test deleting a plan in DRAFT status."""
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = plan_manager.create_plan(request)

        plan_manager.delete_plan(plan.plan_id)

        with pytest.raises(ValueError, match="Plan not found"):
            plan_manager.get_plan(plan.plan_id)

    def test_delete_plan_validated_status(self, plan_manager, sample_idle_vm_analysis):
        """Test deleting a plan in VALIDATED status."""
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = plan_manager.create_plan(request)
        plan_manager.update_plan_status(plan.plan_id, PlanStatus.VALIDATED)

        plan_manager.delete_plan(plan.plan_id)

        with pytest.raises(ValueError, match="Plan not found"):
            plan_manager.get_plan(plan.plan_id)

    def test_delete_plan_approved_status_fails(self, plan_manager, sample_idle_vm_analysis):
        """Test deleting an approved plan fails."""
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = plan_manager.create_plan(request)
        plan_manager.update_plan_status(plan.plan_id, PlanStatus.VALIDATED)
        plan_manager.update_plan_status(plan.plan_id, PlanStatus.APPROVED)

        with pytest.raises(ValueError, match="Cannot delete plan"):
            plan_manager.delete_plan(plan.plan_id)

    def test_delete_plan_completed_status_fails(self, plan_manager, sample_idle_vm_analysis):
        """Test deleting a completed plan fails."""
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = plan_manager.create_plan(request)
        plan_manager.update_plan_status(plan.plan_id, PlanStatus.COMPLETED)

        with pytest.raises(ValueError, match="Cannot delete plan"):
            plan_manager.delete_plan(plan.plan_id)


# ============================================================================
# ACTION OPERATIONS TESTS
# ============================================================================

class TestActionOperations:
    """Tests for action operations."""

    def test_get_actions_for_plan(self, plan_manager, sample_idle_vm_analysis):
        """Test getting all actions for a plan."""
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = plan_manager.create_plan(request)

        actions = plan_manager.get_actions(plan.plan_id)

        assert len(actions) == 2
        for action in actions:
            assert action.plan_id == plan.plan_id
            assert action.status == ActionStatus.PENDING
            assert action.action_type == ActionType.DEALLOCATE

    def test_get_actions_empty_plan(self, plan_manager, test_db):
        """Test getting actions for a plan with no actions."""
        # Create plan without analysis data
        db = DuckDBManager()
        plan_id = generate_plan_id()
        db.conn.execute("""
            INSERT INTO execution_plans (
                plan_id, plan_name, created_by, status, analysis_types
            ) VALUES (?, ?, ?, ?, ?)
        """, [plan_id, "Empty Plan", "test@example.com", "draft", "[]"])

        actions = plan_manager.get_actions(plan_id)
        assert len(actions) == 0

    def test_get_action_by_id(self, plan_manager, sample_idle_vm_analysis):
        """Test getting a single action by ID."""
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = plan_manager.create_plan(request)
        actions = plan_manager.get_actions(plan.plan_id)

        action_id = actions[0].action_id
        retrieved_action = plan_manager.get_action(action_id)

        assert retrieved_action.action_id == action_id
        assert retrieved_action.plan_id == plan.plan_id

    def test_get_action_not_found(self, plan_manager):
        """Test getting non-existent action raises error."""
        with pytest.raises(ValueError, match="Action not found"):
            plan_manager.get_action("action-nonexistent")

    def test_update_action_status_to_completed(self, plan_manager, sample_idle_vm_analysis):
        """Test updating action status to COMPLETED."""
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = plan_manager.create_plan(request)
        actions = plan_manager.get_actions(plan.plan_id)
        action_id = actions[0].action_id

        # Set to running first
        plan_manager.update_action_status(action_id, ActionStatus.RUNNING)

        # Then to completed
        updated_action = plan_manager.update_action_status(
            action_id,
            ActionStatus.COMPLETED,
            execution_result="Successfully deallocated VM",
            realized_monthly_savings=100.0,
        )

        assert updated_action.status == ActionStatus.COMPLETED
        assert updated_action.execution_completed_at is not None
        assert updated_action.realized_monthly_savings == 100.0

    def test_update_action_status_with_rollback_data(self, plan_manager, sample_idle_vm_analysis):
        """Test updating action with rollback data."""
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = plan_manager.create_plan(request)
        actions = plan_manager.get_actions(plan.plan_id)
        action_id = actions[0].action_id

        rollback_data = {
            "action_type": "start",
            "previous_state": "running",
        }

        updated_action = plan_manager.update_action_status(
            action_id,
            ActionStatus.COMPLETED,
            rollback_possible=True,
            rollback_data=rollback_data,
        )

        assert updated_action.rollback_possible is True
        assert updated_action.rollback_data == rollback_data

    def test_add_action_to_draft_plan(self, plan_manager, sample_idle_vm_analysis):
        """Test adding action to a draft plan."""
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = plan_manager.create_plan(request)

        new_action = plan_manager.add_action(
            plan_id=plan.plan_id,
            resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/new-vm",
            resource_name="new-vm",
            analysis_type="idle-vms",
            action_type=ActionType.STOP,
            estimated_monthly_savings=50.0,
            severity="low",
        )

        assert new_action.plan_id == plan.plan_id
        assert new_action.resource_name == "new-vm"
        assert new_action.action_type == ActionType.STOP
        assert new_action.estimated_monthly_savings == 50.0

        # Verify plan metrics updated
        updated_plan = plan_manager.get_plan(plan.plan_id)
        assert updated_plan.total_actions == 3  # Original 2 + new 1

    def test_add_action_to_non_draft_plan_fails(self, plan_manager, sample_idle_vm_analysis):
        """Test adding action to non-draft plan fails."""
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = plan_manager.create_plan(request)
        plan_manager.update_plan_status(plan.plan_id, PlanStatus.VALIDATED)

        with pytest.raises(ValueError, match="Cannot add actions"):
            plan_manager.add_action(
                plan_id=plan.plan_id,
                resource_id="/test/vm",
                resource_name="test-vm",
                analysis_type="idle-vms",
                action_type=ActionType.STOP,
                estimated_monthly_savings=50.0,
            )

    def test_remove_action_from_draft_plan(self, plan_manager, sample_idle_vm_analysis):
        """Test removing action from draft plan."""
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = plan_manager.create_plan(request)
        actions = plan_manager.get_actions(plan.plan_id)
        action_id = actions[0].action_id

        plan_manager.remove_action(action_id)

        # Verify action is removed
        with pytest.raises(ValueError, match="Action not found"):
            plan_manager.get_action(action_id)

        # Verify plan metrics updated
        updated_plan = plan_manager.get_plan(plan.plan_id)
        assert updated_plan.total_actions == 1

    def test_remove_action_from_non_draft_plan_fails(self, plan_manager, sample_idle_vm_analysis):
        """Test removing action from non-draft plan fails."""
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = plan_manager.create_plan(request)
        actions = plan_manager.get_actions(plan.plan_id)
        action_id = actions[0].action_id

        plan_manager.update_plan_status(plan.plan_id, PlanStatus.VALIDATED)

        with pytest.raises(ValueError, match="Cannot remove actions"):
            plan_manager.remove_action(action_id)


# ============================================================================
# HISTORY OPERATIONS TESTS
# ============================================================================

class TestHistoryOperations:
    """Tests for action history operations."""

    def test_get_action_history(self, plan_manager, sample_idle_vm_analysis):
        """Test getting history for a specific action."""
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = plan_manager.create_plan(request)
        actions = plan_manager.get_actions(plan.plan_id)
        action_id = actions[0].action_id

        # Update action status to generate history
        plan_manager.update_action_status(action_id, ActionStatus.RUNNING)
        plan_manager.update_action_status(action_id, ActionStatus.COMPLETED)

        history = plan_manager.get_action_history(action_id)

        assert len(history) >= 2  # At least 2 status changes
        for entry in history:
            assert entry.action_id == action_id

    def test_get_plan_history(self, plan_manager, sample_idle_vm_analysis):
        """Test getting history for entire plan."""
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = plan_manager.create_plan(request)
        actions = plan_manager.get_actions(plan.plan_id)

        # Update multiple actions to generate history
        for action in actions:
            plan_manager.update_action_status(action.action_id, ActionStatus.RUNNING)
            plan_manager.update_action_status(action.action_id, ActionStatus.COMPLETED)

        history = plan_manager.get_plan_history(plan.plan_id)

        assert len(history) >= 4  # At least 2 changes per action
        for entry in history:
            assert entry.plan_id == plan.plan_id


# ============================================================================
# EDGE CASES AND ERROR HANDLING
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_plan_expires_at_set_correctly(self, plan_manager, sample_idle_vm_analysis):
        """Test that plan expiration is set correctly."""
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = plan_manager.create_plan(request)

        # Expires_at should be set to created_at + 30 days (default)
        assert plan.expires_at is not None
        expected_expiry = plan.created_at + timedelta(days=30)
        assert abs((plan.expires_at - expected_expiry).total_seconds()) < 60  # Within 1 minute

    def test_action_execution_order(self, plan_manager, sample_idle_vm_analysis):
        """Test that actions are ordered correctly."""
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = plan_manager.create_plan(request)
        actions = plan_manager.get_actions(plan.plan_id)

        # Actions should be ordered by execution_order
        for i, action in enumerate(actions):
            assert action.execution_order == i + 1

    def test_plan_metrics_update_correctly(self, plan_manager, sample_idle_vm_analysis):
        """Test that plan metrics are updated when actions change."""
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
        )
        plan = plan_manager.create_plan(request)
        actions = plan_manager.get_actions(plan.plan_id)

        # Complete all actions
        for action in actions:
            plan_manager.update_action_status(action.action_id, ActionStatus.COMPLETED)

        # Update metrics
        plan_manager.update_plan_metrics(plan.plan_id)

        updated_plan = plan_manager.get_plan(plan.plan_id)
        assert updated_plan.completed_actions == 2
        assert updated_plan.failed_actions == 0

    def test_severity_filter_case_insensitive(self, plan_manager, sample_idle_vm_analysis):
        """Test severity filter is applied correctly."""
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
            severity_filter="high",
        )
        plan = plan_manager.create_plan(request)

        # Should only include high severity VMs
        assert plan.total_actions == 1

    def test_multiple_severity_filter(self, plan_manager, sample_idle_vm_analysis):
        """Test filtering by multiple severities."""
        request = CreatePlanRequest(
            plan_name="Test Plan",
            created_by="test@example.com",
            analysis_types=["idle-vms"],
            severity_filter="high,medium",
        )
        plan = plan_manager.create_plan(request)

        # Should include both high and medium severity VMs
        assert plan.total_actions == 2
