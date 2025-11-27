"""Tests for ActionLogger module.

Tests cover:
- Log entry creation
- Log entry updates
- Query with filters
- Summary statistics
- Metadata handling
- Edge cases and error scenarios
"""
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from dfo.execute.action_logger import ActionLogger, ActionLog
from dfo.db.duck import DuckDBManager, reset_db
from dfo.core.config import reset_settings


@pytest.fixture
def action_logger(test_db):
    """Create ActionLogger instance with test database."""
    return ActionLogger()


@pytest.fixture
def sample_actions(test_db, action_logger):
    """Create sample action log entries for testing."""
    actions = []

    # Direct execution - completed
    action_id_1 = action_logger.create_log_entry(
        action_type="stop",
        vm_name="vm-prod-001",
        resource_group="production-rg",
        executed=True,
        source="direct_execution",
        reason="Cost optimization Q4"
    )
    action_logger.update_log_entry(
        action_id=action_id_1,
        status="completed",
        result_message="VM stopped successfully",
        duration_seconds=12.4
    )
    actions.append(action_id_1)

    # Direct execution - dry-run
    action_id_2 = action_logger.create_log_entry(
        action_type="deallocate",
        vm_name="vm-test-001",
        resource_group="test-rg",
        executed=False,
        source="direct_execution",
        reason="Testing"
    )
    action_logger.update_log_entry(
        action_id=action_id_2,
        status="completed",
        result_message="Dry-run completed",
        duration_seconds=0.0
    )
    actions.append(action_id_2)

    # Plan execution - completed
    action_id_3 = action_logger.create_log_entry(
        action_type="downsize",
        vm_name="vm-web-001",
        resource_group="web-rg",
        executed=True,
        source="plan_execution",
        reason="Plan: Q4 Cleanup"
    )
    action_logger.update_log_entry(
        action_id=action_id_3,
        status="completed",
        result_message="VM downsized successfully",
        duration_seconds=45.2
    )
    actions.append(action_id_3)

    # Direct execution - failed
    action_id_4 = action_logger.create_log_entry(
        action_type="delete",
        vm_name="vm-db-001",
        resource_group="database-rg",
        executed=True,
        source="direct_execution",
        reason="Emergency cleanup"
    )
    action_logger.update_log_entry(
        action_id=action_id_4,
        status="failed",
        result_message="Permission denied",
        duration_seconds=2.1
    )
    actions.append(action_id_4)

    return actions


# ============================================================================
# LOG ENTRY CREATION TESTS
# ============================================================================

class TestLogCreation:
    """Tests for creating log entries."""

    def test_create_log_entry_basic(self, action_logger):
        """Test creating basic log entry."""
        action_id = action_logger.create_log_entry(
            action_type="stop",
            vm_name="vm-test-001",
            resource_group="test-rg",
            executed=False
        )

        assert action_id.startswith("act-")
        assert len(action_id) > 10

        # Verify entry was created
        action = action_logger.get_action(action_id)
        assert action is not None
        assert action.action_type == "stop"
        assert action.vm_name == "vm-test-001"
        assert action.resource_group == "test-rg"
        assert action.executed is False
        assert action.action_status == "pending"

    def test_create_log_entry_with_metadata(self, action_logger):
        """Test creating log entry with full metadata."""
        pre_state = {
            "power_state": "VM running",
            "size": "Standard_D4s_v3",
            "monthly_cost": 292.00
        }

        action_id = action_logger.create_log_entry(
            action_type="stop",
            vm_name="vm-prod-001",
            resource_group="production-rg",
            executed=True,
            source="direct_execution",
            vm_id="/subscriptions/sub1/resourceGroups/production-rg/providers/Microsoft.Compute/virtualMachines/vm-prod-001",
            reason="Cost optimization",
            command="./dfo azure execute vm vm-prod-001 stop --force",
            pre_state=pre_state
        )

        action = action_logger.get_action(action_id)
        assert action is not None
        assert action.vm_id is not None
        assert action.reason == "Cost optimization"
        assert "pre_state" in action.metadata
        assert action.metadata["pre_state"] == pre_state
        assert action.metadata["source"] == "direct_execution"
        assert "command" in action.metadata

    def test_create_log_entry_plan_execution(self, action_logger):
        """Test creating log entry for plan-based execution."""
        action_id = action_logger.create_log_entry(
            action_type="deallocate",
            vm_name="vm-prod-002",
            resource_group="production-rg",
            executed=True,
            source="plan_execution",
            reason="Plan: Q4 2025 Cleanup"
        )

        action = action_logger.get_action(action_id)
        assert action is not None
        assert action.metadata["source"] == "plan_execution"
        assert action.reason == "Plan: Q4 2025 Cleanup"

    def test_create_log_entry_generates_unique_ids(self, action_logger):
        """Test that action IDs are unique."""
        ids = set()
        for i in range(10):
            action_id = action_logger.create_log_entry(
                action_type="stop",
                vm_name=f"vm-test-{i}",
                resource_group="test-rg",
                executed=False
            )
            ids.add(action_id)

        assert len(ids) == 10  # All IDs should be unique


# ============================================================================
# LOG UPDATE TESTS
# ============================================================================

class TestLogUpdate:
    """Tests for updating log entries."""

    def test_update_log_entry_status(self, action_logger):
        """Test updating log entry status."""
        action_id = action_logger.create_log_entry(
            action_type="stop",
            vm_name="vm-test-001",
            resource_group="test-rg",
            executed=True
        )

        action_logger.update_log_entry(
            action_id=action_id,
            status="completed",
            result_message="VM stopped successfully"
        )

        action = action_logger.get_action(action_id)
        assert action.action_status == "completed"
        assert action.result_message == "VM stopped successfully"

    def test_update_log_entry_with_duration(self, action_logger):
        """Test updating log entry with duration."""
        action_id = action_logger.create_log_entry(
            action_type="deallocate",
            vm_name="vm-test-001",
            resource_group="test-rg",
            executed=True
        )

        action_logger.update_log_entry(
            action_id=action_id,
            status="completed",
            duration_seconds=15.7
        )

        action = action_logger.get_action(action_id)
        assert action.duration_seconds == 15.7

    def test_update_log_entry_with_post_state(self, action_logger):
        """Test updating log entry with post-execution state."""
        pre_state = {
            "power_state": "VM running",
            "monthly_cost": 292.00
        }

        action_id = action_logger.create_log_entry(
            action_type="stop",
            vm_name="vm-prod-001",
            resource_group="production-rg",
            executed=True,
            pre_state=pre_state
        )

        post_state = {
            "power_state": "VM stopped",
            "monthly_cost": 0.00
        }

        action_logger.update_log_entry(
            action_id=action_id,
            status="completed",
            post_state=post_state
        )

        action = action_logger.get_action(action_id)
        assert "pre_state" in action.metadata
        assert "post_state" in action.metadata
        assert action.metadata["post_state"] == post_state

    def test_update_log_entry_failed_status(self, action_logger):
        """Test updating log entry with failure."""
        action_id = action_logger.create_log_entry(
            action_type="delete",
            vm_name="vm-test-001",
            resource_group="test-rg",
            executed=True
        )

        action_logger.update_log_entry(
            action_id=action_id,
            status="failed",
            result_message="Permission denied: Insufficient privileges",
            duration_seconds=1.2
        )

        action = action_logger.get_action(action_id)
        assert action.action_status == "failed"
        assert "Permission denied" in action.result_message


# ============================================================================
# QUERY TESTS
# ============================================================================

class TestQueryLogs:
    """Tests for querying log entries."""

    def test_query_logs_default(self, action_logger, sample_actions):
        """Test querying logs with default parameters."""
        actions = action_logger.query_logs()
        assert len(actions) > 0
        assert len(actions) <= 20  # Default limit

    def test_query_logs_with_limit(self, action_logger, sample_actions):
        """Test querying logs with custom limit."""
        actions = action_logger.query_logs(limit=2)
        assert len(actions) == 2

    def test_query_logs_by_vm_name(self, action_logger, sample_actions):
        """Test filtering logs by VM name."""
        actions = action_logger.query_logs(
            filters={"vm_name": "vm-prod-001"}
        )
        assert len(actions) >= 1
        for action in actions:
            assert action.vm_name == "vm-prod-001"

    def test_query_logs_by_action_type(self, action_logger, sample_actions):
        """Test filtering logs by action type."""
        actions = action_logger.query_logs(
            filters={"action_type": "stop"}
        )
        assert len(actions) >= 1
        for action in actions:
            assert action.action_type == "stop"

    def test_query_logs_by_source_direct(self, action_logger, sample_actions):
        """Test filtering logs by source (direct execution)."""
        actions = action_logger.query_logs(
            filters={"source": "direct"}
        )
        assert len(actions) >= 1
        for action in actions:
            assert action.metadata["source"] == "direct_execution"

    def test_query_logs_by_source_plan(self, action_logger, sample_actions):
        """Test filtering logs by source (plan execution)."""
        actions = action_logger.query_logs(
            filters={"source": "plan"}
        )
        assert len(actions) >= 1
        for action in actions:
            assert action.metadata["source"] == "plan_execution"

    def test_query_logs_by_status(self, action_logger, sample_actions):
        """Test filtering logs by status."""
        actions = action_logger.query_logs(
            filters={"action_status": "failed"}
        )
        assert len(actions) >= 1
        for action in actions:
            assert action.action_status == "failed"

    def test_query_logs_by_executed(self, action_logger, sample_actions):
        """Test filtering logs by executed flag."""
        # Live executions only
        actions = action_logger.query_logs(
            filters={"executed": True}
        )
        assert len(actions) >= 1
        for action in actions:
            assert action.executed is True

    def test_query_logs_by_date_range(self, action_logger, sample_actions):
        """Test filtering logs by date range."""
        since = datetime.utcnow() - timedelta(hours=1)
        until = datetime.utcnow() + timedelta(hours=1)

        actions = action_logger.query_logs(
            filters={"since": since, "until": until}
        )
        assert len(actions) >= 1

    def test_query_logs_multiple_filters(self, action_logger, sample_actions):
        """Test querying logs with multiple filters."""
        actions = action_logger.query_logs(
            filters={
                "source": "direct",
                "executed": True,
                "action_status": "completed"
            }
        )
        # Should only return direct executions that were actually executed and completed
        for action in actions:
            assert action.metadata["source"] == "direct_execution"
            assert action.executed is True
            assert action.action_status == "completed"

    def test_query_logs_empty_result(self, action_logger, sample_actions):
        """Test querying logs with filters that match nothing."""
        actions = action_logger.query_logs(
            filters={"vm_name": "nonexistent-vm"}
        )
        assert len(actions) == 0


# ============================================================================
# GET ACTION TESTS
# ============================================================================

class TestGetAction:
    """Tests for retrieving specific action."""

    def test_get_action_existing(self, action_logger, sample_actions):
        """Test getting existing action."""
        action_id = sample_actions[0]
        action = action_logger.get_action(action_id)

        assert action is not None
        assert action.action_id == action_id
        assert isinstance(action, ActionLog)

    def test_get_action_nonexistent(self, action_logger):
        """Test getting nonexistent action."""
        action = action_logger.get_action("act-nonexistent")
        assert action is None


# ============================================================================
# SUMMARY TESTS
# ============================================================================

class TestLogsSummary:
    """Tests for logs summary statistics."""

    def test_get_logs_summary_all(self, action_logger, sample_actions):
        """Test getting summary for all logs."""
        summary = action_logger.get_logs_summary()

        assert "total_actions" in summary
        assert "live_executions" in summary
        assert "dry_run_simulations" in summary
        assert summary["total_actions"] >= 4
        assert summary["live_executions"] >= 3
        assert summary["dry_run_simulations"] >= 1

    def test_get_logs_summary_with_filters(self, action_logger, sample_actions):
        """Test getting summary with filters."""
        summary = action_logger.get_logs_summary(
            filters={"source": "direct"}
        )

        assert summary["total_actions"] >= 3  # We created 3 direct execution logs

    def test_get_logs_summary_empty(self, action_logger):
        """Test getting summary with no logs."""
        summary = action_logger.get_logs_summary()

        assert summary["total_actions"] == 0
        assert summary["live_executions"] == 0
        assert summary["dry_run_simulations"] == 0


# ============================================================================
# ACTIONLOG DATACLASS TESTS
# ============================================================================

class TestActionLogDataclass:
    """Tests for ActionLog dataclass."""

    def test_action_log_to_dict(self, action_logger, sample_actions):
        """Test converting ActionLog to dictionary."""
        action_id = sample_actions[0]
        action = action_logger.get_action(action_id)

        action_dict = action.to_dict()

        assert isinstance(action_dict, dict)
        assert "action_id" in action_dict
        assert "vm_name" in action_dict
        assert "action_type" in action_dict
        assert "execution_time" in action_dict
        assert isinstance(action_dict["execution_time"], str)  # Should be ISO format


# ============================================================================
# HELPER METHOD TESTS
# ============================================================================

class TestHelperMethods:
    """Tests for internal helper methods."""

    def test_generate_action_id_format(self, action_logger):
        """Test action ID generation format."""
        action_id = action_logger._generate_action_id()
        assert action_id.startswith("act-")
        # Format: act-YYYYMMDD-HHMMSS-mmmmmm (with microseconds)
        assert len(action_id.split("-")) == 4

    def test_get_command_line(self, action_logger):
        """Test getting command line."""
        command = action_logger._get_command_line()
        assert isinstance(command, str)
        assert len(command) > 0

    def test_get_current_user(self, action_logger):
        """Test getting current user."""
        user = action_logger._get_current_user()
        assert isinstance(user, str)
        assert len(user) > 0

    def test_get_service_principal(self, action_logger):
        """Test getting service principal."""
        sp = action_logger._get_service_principal()
        assert isinstance(sp, str)

    def test_get_environment(self, action_logger):
        """Test environment detection."""
        env = action_logger._get_environment()
        assert isinstance(env, str)
        assert env in ["production", "staging", "development", "unknown"]


# ============================================================================
# EDGE CASES AND ERROR SCENARIOS
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error scenarios."""

    def test_create_log_with_minimal_data(self, action_logger):
        """Test creating log with only required fields."""
        action_id = action_logger.create_log_entry(
            action_type="restart",
            vm_name="vm-minimal",
            resource_group="minimal-rg",
            executed=False
        )

        action = action_logger.get_action(action_id)
        assert action is not None
        assert action.reason is not None  # Should have default reason
        assert action.metadata["source"] == "direct_execution"  # Default source

    def test_update_nonexistent_action(self, action_logger):
        """Test updating nonexistent action (should not raise error)."""
        # This should not raise an error, just silently do nothing
        action_logger.update_log_entry(
            action_id="act-nonexistent",
            status="completed"
        )
        # If we got here without error, test passes

    def test_query_with_invalid_filter_keys(self, action_logger, sample_actions):
        """Test querying with invalid filter keys (should be ignored)."""
        actions = action_logger.query_logs(
            filters={"invalid_key": "some_value"}
        )
        # Should return all actions (invalid filter ignored)
        assert len(actions) > 0

    def test_metadata_with_special_characters(self, action_logger):
        """Test metadata with special characters."""
        action_id = action_logger.create_log_entry(
            action_type="stop",
            vm_name="vm-test",
            resource_group="test-rg",
            executed=False,
            reason="Cost optimization: $100/month savings (50% reduction)"
        )

        action = action_logger.get_action(action_id)
        assert "$" in action.reason
        assert "%" in action.reason
