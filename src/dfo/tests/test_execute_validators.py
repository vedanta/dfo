"""Tests for plan and action validation logic."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from dfo.execute.validators import (
    validate_plan,
    validate_action,
    should_revalidate,
    get_validation_summary,
    DESTRUCTIVE_ACTIONS,
    PROTECTION_TAGS,
)
from dfo.execute.models import (
    ActionStatus,
    ActionType,
    CreatePlanRequest,
    PlanAction,
    PlanStatus,
    ValidationResult,
    ValidationStatus,
)
from dfo.execute.plan_manager import PlanManager
from dfo.db.duck import DuckDBManager


@pytest.fixture
def plan_manager(test_db):
    """Create PlanManager instance with test database."""
    return PlanManager()


@pytest.fixture
def sample_plan_with_actions(test_db):
    """Create a plan with sample actions."""
    # Insert idle VM analysis
    db = DuckDBManager()
    conn = db.get_connection()
    conn.execute("""
        INSERT INTO vm_idle_analysis (
            vm_id, cpu_avg, days_under_threshold, estimated_monthly_savings,
            severity, recommended_action, equivalent_sku, analyzed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/test-vm1",
        2.5,
        14,
        100.0,
        "high",
        "DEALLOCATE",
        "Standard_B2s",
        datetime.now()
    ])

    # Create plan
    manager = PlanManager()
    request = CreatePlanRequest(
        plan_name="Test Plan",
        created_by="test@example.com",
        analysis_types=["idle-vms"],
    )
    plan = manager.create_plan(request)

    yield plan, manager


# ============================================================================
# PLAN VALIDATION TESTS
# ============================================================================

class TestPlanValidation:
    """Tests for plan validation."""

    @patch('dfo.execute.validators.validate_action')
    def test_validate_plan_success(self, mock_validate_action, sample_plan_with_actions):
        """Test successful plan validation."""
        plan, manager = sample_plan_with_actions

        # Mock all actions as valid
        mock_validate_action.return_value = ValidationResult(
            action_id="action-1",
            status=ValidationStatus.SUCCESS,
            resource_exists=True,
            permissions_ok=True,
            dependencies=[],
            warnings=[],
            errors=[],
        )

        result = validate_plan(plan.plan_id)

        assert result.status == ValidationStatus.SUCCESS
        assert result.total_actions == 1
        assert result.ready_actions == 1
        assert result.warning_actions == 0
        assert result.error_actions == 0
        assert "ready" in result.summary

        # Verify plan status updated to VALIDATED
        updated_plan = manager.get_plan(plan.plan_id)
        assert updated_plan.status == PlanStatus.VALIDATED

    @patch('dfo.execute.validators.validate_action')
    def test_validate_plan_with_warnings(self, mock_validate_action, sample_plan_with_actions):
        """Test plan validation with warnings."""
        plan, manager = sample_plan_with_actions

        mock_validate_action.return_value = ValidationResult(
            action_id="action-1",
            status=ValidationStatus.WARNING,
            resource_exists=True,
            permissions_ok=True,
            dependencies=[],
            warnings=["VM is already stopped"],
            errors=[],
        )

        result = validate_plan(plan.plan_id)

        assert result.status == ValidationStatus.WARNING
        assert result.warning_actions == 1
        assert result.error_actions == 0
        assert "warnings" in result.summary

        # Plan should still be VALIDATED even with warnings
        updated_plan = manager.get_plan(plan.plan_id)
        assert updated_plan.status == PlanStatus.VALIDATED

    @patch('dfo.execute.validators.validate_action')
    def test_validate_plan_with_errors(self, mock_validate_action, sample_plan_with_actions):
        """Test plan validation with errors."""
        plan, manager = sample_plan_with_actions

        mock_validate_action.return_value = ValidationResult(
            action_id="action-1",
            status=ValidationStatus.ERROR,
            resource_exists=False,
            permissions_ok=False,
            dependencies=[],
            warnings=[],
            errors=["Resource not found"],
        )

        result = validate_plan(plan.plan_id)

        assert result.status == ValidationStatus.ERROR
        assert result.error_actions == 1
        assert "errors" in result.summary

        # Plan should remain DRAFT when there are errors
        updated_plan = manager.get_plan(plan.plan_id)
        assert updated_plan.status == PlanStatus.DRAFT

    def test_validate_plan_no_actions(self, plan_manager, test_db):
        """Test validating plan with no actions."""
        # Create plan without analysis data (no actions will be added)
        request = CreatePlanRequest(
            plan_name="Empty Plan",
            created_by="test@example.com",
            analysis_types=[],  # No analysis types = no actions
        )
        plan = plan_manager.create_plan(request)

        result = validate_plan(plan.plan_id)

        assert result.status == ValidationStatus.ERROR
        assert result.total_actions == 0
        assert "no actions" in result.summary.lower()

    def test_validate_plan_not_found(self, plan_manager):
        """Test validating non-existent plan."""
        with pytest.raises(ValueError, match="Plan not found"):
            validate_plan("plan-nonexistent")

    @patch('dfo.execute.validators.validate_action')
    def test_validate_plan_mixed_results(self, mock_validate_action, sample_plan_with_actions):
        """Test plan with mix of success, warnings, and errors."""
        plan, manager = sample_plan_with_actions

        # Add more actions to test
        manager.add_action(
            plan_id=plan.plan_id,
            resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm2",
            resource_name="vm2",
            analysis_type="idle-vms",
            action_type=ActionType.STOP,
            estimated_monthly_savings=50.0,
        )
        manager.add_action(
            plan_id=plan.plan_id,
            resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm3",
            resource_name="vm3",
            analysis_type="idle-vms",
            action_type=ActionType.DELETE,
            estimated_monthly_savings=75.0,
        )

        # Mock different results for each action
        actions = manager.get_actions(plan.plan_id)
        results = [
            ValidationResult(action_id=actions[0].action_id, status=ValidationStatus.SUCCESS,
                           resource_exists=True, permissions_ok=True, dependencies=[], warnings=[], errors=[]),
            ValidationResult(action_id=actions[1].action_id, status=ValidationStatus.WARNING,
                           resource_exists=True, permissions_ok=True, dependencies=[],
                           warnings=["Already stopped"], errors=[]),
            ValidationResult(action_id=actions[2].action_id, status=ValidationStatus.ERROR,
                           resource_exists=False, permissions_ok=False, dependencies=[],
                           warnings=[], errors=["Not found"]),
        ]

        call_count = [0]
        def side_effect(action):
            result = results[call_count[0] % len(results)]
            call_count[0] += 1
            return result

        mock_validate_action.side_effect = side_effect

        result = validate_plan(plan.plan_id)

        assert result.status == ValidationStatus.ERROR  # Errors take precedence
        assert result.total_actions == 3
        assert result.ready_actions == 1
        assert result.warning_actions == 1
        assert result.error_actions == 1


# ============================================================================
# ACTION VALIDATION TESTS
# ============================================================================

class TestActionValidation:
    """Tests for individual action validation."""

    def test_validate_action_basic_success(self):
        """Test basic action validation without Azure."""
        action = PlanAction(
            action_id="action-test-1",
            plan_id="plan-test-1",
            resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/test-vm",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.STOP,
            estimated_monthly_savings=100.0,
        )

        result = validate_action(action, use_azure_validation=False)

        assert result.status == ValidationStatus.SUCCESS
        assert result.resource_exists is True
        assert result.permissions_ok is True

    def test_validate_action_destructive_warning(self):
        """Test that destructive actions generate warnings."""
        action = PlanAction(
            action_id="action-test-1",
            plan_id="plan-test-1",
            resource_id="/test/vm",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.DELETE,
            estimated_monthly_savings=100.0,
        )

        result = validate_action(action, use_azure_validation=False)

        assert result.status == ValidationStatus.WARNING
        assert len(result.warnings) > 0
        assert any("IRREVERSIBLE" in w for w in result.warnings)

    def test_validate_action_downsize_missing_parameter(self):
        """Test downsize action without new_size parameter."""
        action = PlanAction(
            action_id="action-test-1",
            plan_id="plan-test-1",
            resource_id="/test/vm",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="low-cpu",
            action_type=ActionType.DOWNSIZE,
            estimated_monthly_savings=100.0,
            action_params={},  # Missing 'new_size'
        )

        result = validate_action(action, use_azure_validation=False)

        assert result.status == ValidationStatus.ERROR
        assert len(result.errors) > 0
        assert any("new_size" in e for e in result.errors)

    def test_validate_action_downsize_with_parameter(self):
        """Test downsize action with valid new_size parameter."""
        action = PlanAction(
            action_id="action-test-1",
            plan_id="plan-test-1",
            resource_id="/test/vm",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="low-cpu",
            action_type=ActionType.DOWNSIZE,
            estimated_monthly_savings=100.0,
            action_params={"new_size": "Standard_B2s"},
        )

        result = validate_action(action, use_azure_validation=False)

        # Should still be warning because DOWNSIZE is destructive
        assert result.status == ValidationStatus.WARNING

    @patch('dfo.execute.azure_validator.validate_azure_vm_action')
    def test_validate_action_with_azure_validation(self, mock_azure_validate):
        """Test action validation uses Azure validator when enabled."""
        action = PlanAction(
            action_id="action-test-1",
            plan_id="plan-test-1",
            resource_id="/test/vm",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.STOP,
            estimated_monthly_savings=100.0,
        )

        mock_azure_validate.return_value = ValidationResult(
            action_id="action-test-1",
            status=ValidationStatus.SUCCESS,
            resource_exists=True,
            permissions_ok=True,
        )

        result = validate_action(action, use_azure_validation=True)

        mock_azure_validate.assert_called_once_with(action)
        assert result.status == ValidationStatus.SUCCESS

    @patch('dfo.execute.azure_validator.validate_azure_vm_action')
    def test_validate_action_azure_validation_fallback(self, mock_azure_validate):
        """Test fallback to basic validation when Azure validation fails."""
        action = PlanAction(
            action_id="action-test-1",
            plan_id="plan-test-1",
            resource_id="/test/vm",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.STOP,
            estimated_monthly_savings=100.0,
        )

        mock_azure_validate.side_effect = Exception("Azure connection failed")

        result = validate_action(action, use_azure_validation=True)

        assert result.status == ValidationStatus.WARNING
        assert len(result.warnings) > 0
        assert any("Azure validation unavailable" in w for w in result.warnings)


# ============================================================================
# REVALIDATION TESTS
# ============================================================================

class TestRevalidation:
    """Tests for revalidation logic."""

    def test_should_revalidate_never_validated(self, sample_plan_with_actions):
        """Test that plan without validation needs revalidation."""
        plan, manager = sample_plan_with_actions

        assert should_revalidate(plan.plan_id) is True

    def test_should_revalidate_fresh_validation(self, sample_plan_with_actions):
        """Test that recently validated plan doesn't need revalidation."""
        plan, manager = sample_plan_with_actions

        # Validate the plan
        manager.update_plan_status(plan.plan_id, PlanStatus.VALIDATED)

        assert should_revalidate(plan.plan_id) is False

    def test_should_revalidate_stale_validation(self, sample_plan_with_actions):
        """Test that old validation needs revalidation."""
        plan, manager = sample_plan_with_actions

        # Validate the plan with an old timestamp
        old_time = datetime.now() - timedelta(hours=2)
        db = DuckDBManager()
        conn = db.get_connection()
        conn.execute("""
            UPDATE execution_plans
            SET status = 'validated', validated_at = ?
            WHERE plan_id = ?
        """, [old_time, plan.plan_id])

        assert should_revalidate(plan.plan_id) is True

    def test_should_revalidate_exact_threshold(self, sample_plan_with_actions):
        """Test revalidation at exactly 1 hour threshold."""
        plan, manager = sample_plan_with_actions

        # Validate exactly 1 hour ago
        exact_threshold = datetime.now() - timedelta(hours=1, minutes=0, seconds=1)
        db = DuckDBManager()
        conn = db.get_connection()
        conn.execute("""
            UPDATE execution_plans
            SET status = 'validated', validated_at = ?
            WHERE plan_id = ?
        """, [exact_threshold, plan.plan_id])

        assert should_revalidate(plan.plan_id) is True


# ============================================================================
# VALIDATION SUMMARY TESTS
# ============================================================================

class TestValidationSummary:
    """Tests for validation summary."""

    @patch('dfo.execute.validators.validate_action')
    def test_get_validation_summary_after_validation(self, mock_validate_action, sample_plan_with_actions):
        """Test validation summary after validating a plan."""
        plan, manager = sample_plan_with_actions

        mock_validate_action.return_value = ValidationResult(
            action_id="action-1",
            status=ValidationStatus.SUCCESS,
            resource_exists=True,
            permissions_ok=True,
            dependencies=[],
            warnings=[],
            errors=[],
        )

        # Validate the plan first
        validate_plan(plan.plan_id)

        summary = get_validation_summary(plan.plan_id)

        assert summary["plan_id"] == plan.plan_id
        assert summary["plan_status"] == PlanStatus.VALIDATED
        assert summary["total_actions"] == 1
        assert summary["validated"] == 1
        assert summary["errors"] == 0
        assert summary["needs_revalidation"] is False

    def test_get_validation_summary_before_validation(self, sample_plan_with_actions):
        """Test validation summary before any validation."""
        plan, manager = sample_plan_with_actions

        summary = get_validation_summary(plan.plan_id)

        assert summary["plan_id"] == plan.plan_id
        assert summary["plan_status"] == PlanStatus.DRAFT
        assert summary["total_actions"] == 1
        assert summary["validated_at"] is None
        assert summary["needs_revalidation"] is True

    @patch('dfo.execute.validators.validate_action')
    def test_get_validation_summary_mixed_statuses(self, mock_validate_action, sample_plan_with_actions):
        """Test validation summary with mixed validation statuses."""
        plan, manager = sample_plan_with_actions

        # Add more actions
        manager.add_action(
            plan_id=plan.plan_id,
            resource_id="/test/vm2",
            resource_name="vm2",
            analysis_type="idle-vms",
            action_type=ActionType.STOP,
            estimated_monthly_savings=50.0,
        )

        # Mock different results
        actions = manager.get_actions(plan.plan_id)
        results = [
            ValidationResult(action_id=actions[0].action_id, status=ValidationStatus.SUCCESS,
                           resource_exists=True, permissions_ok=True, dependencies=[], warnings=[], errors=[]),
            ValidationResult(action_id=actions[1].action_id, status=ValidationStatus.WARNING,
                           resource_exists=True, permissions_ok=True, dependencies=[], warnings=["Warning"], errors=[]),
        ]

        call_count = [0]
        def side_effect(action):
            result = results[call_count[0] % len(results)]
            call_count[0] += 1
            return result

        mock_validate_action.side_effect = side_effect

        validate_plan(plan.plan_id)
        summary = get_validation_summary(plan.plan_id)

        assert summary["total_actions"] == 2
        assert summary["validated"] == 1
        assert summary["warnings"] == 1
        assert summary["errors"] == 0


# ============================================================================
# EDGE CASES
# ============================================================================

class TestValidationEdgeCases:
    """Tests for edge cases in validation."""

    def test_validate_action_all_action_types(self):
        """Test validation for all action types."""
        action_types = [
            ActionType.STOP,
            ActionType.DEALLOCATE,
            ActionType.DELETE,
            ActionType.DOWNSIZE,
            ActionType.START,
        ]

        for action_type in action_types:
            action = PlanAction(
                action_id=f"action-{action_type}",
                plan_id="plan-test",
                resource_id="/test/vm",
                resource_name="test-vm",
                resource_type="vm",
                analysis_type="test",
                action_type=action_type,
                estimated_monthly_savings=100.0,
                action_params={"new_size": "Standard_B2s"} if action_type == ActionType.DOWNSIZE else None,
            )

            result = validate_action(action, use_azure_validation=False)
            assert result is not None
            assert result.status in [ValidationStatus.SUCCESS, ValidationStatus.WARNING, ValidationStatus.ERROR]

    def test_destructive_actions_constant(self):
        """Test DESTRUCTIVE_ACTIONS constant is defined correctly."""
        assert ActionType.DELETE in DESTRUCTIVE_ACTIONS
        assert ActionType.DOWNSIZE in DESTRUCTIVE_ACTIONS

    def test_protection_tags_constant(self):
        """Test PROTECTION_TAGS constant is defined correctly."""
        assert "dfo-protected" in PROTECTION_TAGS
        assert "dfo-exclude" in PROTECTION_TAGS

    def test_validation_result_details_populated(self):
        """Test that validation result includes detailed information."""
        action = PlanAction(
            action_id="action-test-1",
            plan_id="plan-test-1",
            resource_id="/test/vm",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.STOP,
            estimated_monthly_savings=100.0,
        )

        result = validate_action(action, use_azure_validation=False)

        assert result.details is not None
        assert "resource_id" in result.details
        assert "resource_name" in result.details
        assert "action_type" in result.details
        assert "estimated_savings" in result.details
