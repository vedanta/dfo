"""Tests for plan approval logic."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from dfo.execute.approvals import (
    approve_plan,
    get_approval_summary,
    ApprovalError,
)
from dfo.execute.models import (
    ActionType,
    CreatePlanRequest,
    PlanStatus,
    ValidationStatus,
)
from dfo.execute.plan_manager import PlanManager
from dfo.db.duck import DuckDBManager


@pytest.fixture
def sample_plan_validated(test_db):
    """Create a validated plan ready for approval."""
    # Insert idle VM analysis
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

    # Create and validate plan
    manager = PlanManager()
    request = CreatePlanRequest(
        plan_name="Test Plan",
        created_by="test@example.com",
        analysis_types=["idle-vms"],
    )
    plan = manager.create_plan(request)

    # Mark as validated
    manager.update_plan_status(plan.plan_id, PlanStatus.VALIDATED)

    # Mark actions as validated
    actions = manager.get_actions(plan.plan_id)
    for action in actions:
        manager.update_action_status(
            action.action_id,
            action.status,
            validation_status=ValidationStatus.SUCCESS,
        )

    yield plan, manager


class TestApprovalWorkflow:
    """Tests for plan approval workflow."""

    def test_approve_plan_success(self, sample_plan_validated):
        """Test successful plan approval."""
        plan, manager = sample_plan_validated

        approve_plan(plan.plan_id, approved_by="approver@example.com")

        updated_plan = manager.get_plan(plan.plan_id)
        assert updated_plan.status == PlanStatus.APPROVED
        assert updated_plan.approved_by == "approver@example.com"
        assert updated_plan.approved_at is not None

    def test_approve_plan_with_notes(self, sample_plan_validated):
        """Test approval with notes."""
        plan, manager = sample_plan_validated

        approve_plan(
            plan.plan_id,
            approved_by="approver@example.com",
            notes="Approved for weekend maintenance"
        )

        updated_plan = manager.get_plan(plan.plan_id)
        assert updated_plan.status == PlanStatus.APPROVED
        assert updated_plan.metadata is not None
        assert "approval_notes" in updated_plan.metadata

    def test_approve_draft_plan_fails(self, sample_plan_validated):
        """Test approving draft plan fails."""
        plan, manager = sample_plan_validated

        # Set back to draft
        manager.update_plan_status(plan.plan_id, PlanStatus.DRAFT)

        with pytest.raises(ApprovalError, match="Run validation first"):
            approve_plan(plan.plan_id, approved_by="approver@example.com")

    def test_approve_already_approved_plan_fails(self, sample_plan_validated):
        """Test approving already approved plan fails."""
        plan, manager = sample_plan_validated

        approve_plan(plan.plan_id, approved_by="approver@example.com")

        with pytest.raises(ApprovalError, match="already approved"):
            approve_plan(plan.plan_id, approved_by="another@example.com")

    @patch('dfo.execute.approvals.should_revalidate')
    def test_approve_stale_validation_fails(self, mock_should_revalidate, sample_plan_validated):
        """Test approving plan with stale validation fails."""
        plan, manager = sample_plan_validated

        mock_should_revalidate.return_value = True

        with pytest.raises(ApprovalError, match="validation is stale"):
            approve_plan(plan.plan_id, approved_by="approver@example.com")

    def test_approve_plan_with_error_actions_fails(self, sample_plan_validated):
        """Test approving plan with actions having validation errors fails."""
        plan, manager = sample_plan_validated

        # Mark an action with ERROR validation status
        actions = manager.get_actions(plan.plan_id)
        manager.update_action_status(
            actions[0].action_id,
            actions[0].status,
            validation_status=ValidationStatus.ERROR,
            validation_details={"errors": ["Resource not found"]},
        )

        with pytest.raises(ApprovalError, match="validation errors"):
            approve_plan(plan.plan_id, approved_by="approver@example.com")

    def test_approve_plan_no_actions_fails(self, test_db):
        """Test approving plan with no actions fails."""
        db = DuckDBManager()
        plan_id = "plan-empty-test"
        db.conn.execute("""
            INSERT INTO execution_plans (
                plan_id, plan_name, created_by, status, analysis_types, validated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, [plan_id, "Empty Plan", "test@example.com", "validated", "[]", datetime.now()])

        with pytest.raises(ApprovalError, match="no actions"):
            approve_plan(plan_id, approved_by="approver@example.com")


class TestApprovalSummary:
    """Tests for approval summary."""

    def test_get_approval_summary_validated_plan(self, sample_plan_validated):
        """Test approval summary for validated plan."""
        plan, manager = sample_plan_validated

        summary = get_approval_summary(plan.plan_id)

        assert summary["plan_id"] == plan.plan_id
        assert summary["plan_name"] == plan.plan_name
        assert summary["plan_status"] == PlanStatus.VALIDATED
        assert summary["total_actions"] == 1
        assert summary["ready_actions"] == 1
        assert summary["error_actions"] == 0
        assert summary["can_approve"] is True

    def test_get_approval_summary_with_destructive_actions(self, sample_plan_validated):
        """Test summary identifies destructive actions."""
        plan, manager = sample_plan_validated

        # Add a DELETE action
        manager.add_action(
            plan_id=plan.plan_id,
            resource_id="/test/vm",
            resource_name="test-vm",
            analysis_type="idle-vms",
            action_type=ActionType.DELETE,
            estimated_monthly_savings=50.0,
        )

        summary = get_approval_summary(plan.plan_id)

        assert summary["destructive_actions"] == 1

    def test_get_approval_summary_action_counts(self, sample_plan_validated):
        """Test summary includes action counts by type."""
        plan, manager = sample_plan_validated

        summary = get_approval_summary(plan.plan_id)

        assert "action_counts" in summary
        assert ActionType.DEALLOCATE in summary["action_counts"]

    def test_get_approval_summary_validation_age(self, sample_plan_validated):
        """Test summary includes validation age."""
        plan, manager = sample_plan_validated

        summary = get_approval_summary(plan.plan_id)

        assert summary["validated_at"] is not None
        assert summary["validation_age_hours"] is not None
        assert summary["validation_age_hours"] < 1  # Recently validated

    def test_get_approval_summary_cannot_approve(self, sample_plan_validated):
        """Test summary indicates plan cannot be approved."""
        plan, manager = sample_plan_validated

        # Mark action with ERROR
        actions = manager.get_actions(plan.plan_id)
        manager.update_action_status(
            actions[0].action_id,
            actions[0].status,
            validation_status=ValidationStatus.ERROR,
        )

        summary = get_approval_summary(plan.plan_id)

        assert summary["can_approve"] is False
        assert summary["error_actions"] == 1
