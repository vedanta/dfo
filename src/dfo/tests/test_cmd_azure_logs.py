"""Tests for azure logs CLI commands.

Tests the action logs CLI commands to ensure proper integration
with ActionLogger and correct output formatting.
"""
import pytest
from datetime import datetime, timedelta
from typer.testing import CliRunner
from unittest.mock import Mock, patch

from dfo.cmd.azure_logs import app, _parse_since
from dfo.execute.action_logger import ActionLog

runner = CliRunner()


class TestLogsListCommand:
    """Tests for logs list command."""

    @patch('dfo.cmd.azure_logs.ActionLogger')
    def test_list_logs_default(self, mock_logger_class):
        """Test listing logs with default parameters."""
        # Mock logger
        mock_logger = Mock()
        mock_logs = [
            ActionLog(
                action_id="act-123",
                plan_id="direct-123",
                vm_id="vm-id-1",
                vm_name="test-vm-1",
                resource_group="test-rg",
                action_type="stop",
                action_status="completed",
                executed=False,
                execution_time=datetime(2025, 11, 27, 14, 30),
                duration_seconds=0.5,
                result_message="[DRY RUN] Would execute stop",
                reason="Cost optimization",
                metadata={"source": "direct_execution"}
            )
        ]
        mock_logger.query_logs.return_value = mock_logs
        mock_logger.get_logs_summary.return_value = {
            "total_actions": 1,
            "live_executions": 0,
            "dry_run_simulations": 1
        }
        mock_logger_class.return_value = mock_logger

        # Run command
        result = runner.invoke(app, ["list"])

        # Verify
        assert result.exit_code == 0
        mock_logger.query_logs.assert_called_once_with(limit=20, filters={})
        assert "test-vm-1" in result.stdout
        assert "stop" in result.stdout
        assert "completed" in result.stdout

    @patch('dfo.cmd.azure_logs.ActionLogger')
    def test_list_logs_with_limit(self, mock_logger_class):
        """Test listing logs with custom limit."""
        # Mock logger
        mock_logger = Mock()
        mock_logger.query_logs.return_value = []
        mock_logger.get_logs_summary.return_value = {
            "total_actions": 0,
            "live_executions": 0,
            "dry_run_simulations": 0
        }
        mock_logger_class.return_value = mock_logger

        # Run command
        result = runner.invoke(app, ["list", "--limit", "50"])

        # Verify
        assert result.exit_code == 0
        mock_logger.query_logs.assert_called_once_with(limit=50, filters={})

    @patch('dfo.cmd.azure_logs.ActionLogger')
    def test_list_logs_filter_by_vm_name(self, mock_logger_class):
        """Test filtering logs by VM name."""
        # Mock logger
        mock_logger = Mock()
        mock_logger.query_logs.return_value = []
        mock_logger.get_logs_summary.return_value = {
            "total_actions": 0,
            "live_executions": 0,
            "dry_run_simulations": 0
        }
        mock_logger_class.return_value = mock_logger

        # Run command
        result = runner.invoke(app, ["list", "--vm-name", "test-vm"])

        # Verify
        assert result.exit_code == 0
        call_args = mock_logger.query_logs.call_args
        assert call_args[1]["filters"]["vm_name"] == "test-vm"

    @patch('dfo.cmd.azure_logs.ActionLogger')
    def test_list_logs_filter_by_action(self, mock_logger_class):
        """Test filtering logs by action type."""
        # Mock logger
        mock_logger = Mock()
        mock_logger.query_logs.return_value = []
        mock_logger.get_logs_summary.return_value = {
            "total_actions": 0,
            "live_executions": 0,
            "dry_run_simulations": 0
        }
        mock_logger_class.return_value = mock_logger

        # Run command
        result = runner.invoke(app, ["list", "--action", "stop"])

        # Verify
        assert result.exit_code == 0
        call_args = mock_logger.query_logs.call_args
        assert call_args[1]["filters"]["action_type"] == "stop"

    @patch('dfo.cmd.azure_logs.ActionLogger')
    def test_list_logs_filter_by_source(self, mock_logger_class):
        """Test filtering logs by source."""
        # Mock logger
        mock_logger = Mock()
        mock_logger.query_logs.return_value = []
        mock_logger.get_logs_summary.return_value = {
            "total_actions": 0,
            "live_executions": 0,
            "dry_run_simulations": 0
        }
        mock_logger_class.return_value = mock_logger

        # Run command
        result = runner.invoke(app, ["list", "--source", "direct"])

        # Verify
        assert result.exit_code == 0
        call_args = mock_logger.query_logs.call_args
        assert call_args[1]["filters"]["source"] == "direct"

    @patch('dfo.cmd.azure_logs.ActionLogger')
    def test_list_logs_filter_by_status(self, mock_logger_class):
        """Test filtering logs by status."""
        # Mock logger
        mock_logger = Mock()
        mock_logger.query_logs.return_value = []
        mock_logger.get_logs_summary.return_value = {
            "total_actions": 0,
            "live_executions": 0,
            "dry_run_simulations": 0
        }
        mock_logger_class.return_value = mock_logger

        # Run command
        result = runner.invoke(app, ["list", "--status", "failed"])

        # Verify
        assert result.exit_code == 0
        call_args = mock_logger.query_logs.call_args
        assert call_args[1]["filters"]["action_status"] == "failed"

    @patch('dfo.cmd.azure_logs.ActionLogger')
    def test_list_logs_filter_executed(self, mock_logger_class):
        """Test filtering logs by executed flag (live executions)."""
        # Mock logger
        mock_logger = Mock()
        mock_logger.query_logs.return_value = []
        mock_logger.get_logs_summary.return_value = {
            "total_actions": 0,
            "live_executions": 0,
            "dry_run_simulations": 0
        }
        mock_logger_class.return_value = mock_logger

        # Run command
        result = runner.invoke(app, ["list", "--executed"])

        # Verify
        assert result.exit_code == 0
        call_args = mock_logger.query_logs.call_args
        assert call_args[1]["filters"]["executed"] is True

    @patch('dfo.cmd.azure_logs.ActionLogger')
    def test_list_logs_filter_dry_run(self, mock_logger_class):
        """Test filtering logs by dry-run flag."""
        # Mock logger
        mock_logger = Mock()
        mock_logger.query_logs.return_value = []
        mock_logger.get_logs_summary.return_value = {
            "total_actions": 0,
            "live_executions": 0,
            "dry_run_simulations": 0
        }
        mock_logger_class.return_value = mock_logger

        # Run command
        result = runner.invoke(app, ["list", "--dry-run"])

        # Verify
        assert result.exit_code == 0
        call_args = mock_logger.query_logs.call_args
        assert call_args[1]["filters"]["executed"] is False

    @patch('dfo.cmd.azure_logs.ActionLogger')
    def test_list_logs_filter_by_user(self, mock_logger_class):
        """Test filtering logs by user."""
        # Mock logger
        mock_logger = Mock()
        mock_logger.query_logs.return_value = []
        mock_logger.get_logs_summary.return_value = {
            "total_actions": 0,
            "live_executions": 0,
            "dry_run_simulations": 0
        }
        mock_logger_class.return_value = mock_logger

        # Run command
        result = runner.invoke(app, ["list", "--user", "john"])

        # Verify
        assert result.exit_code == 0
        call_args = mock_logger.query_logs.call_args
        assert call_args[1]["filters"]["user"] == "john"

    @patch('dfo.cmd.azure_logs.ActionLogger')
    def test_list_logs_no_results(self, mock_logger_class):
        """Test handling when no logs match filters."""
        # Mock logger with empty results
        mock_logger = Mock()
        mock_logger.query_logs.return_value = []
        mock_logger_class.return_value = mock_logger

        # Run command
        result = runner.invoke(app, ["list"])

        # Verify
        assert result.exit_code == 0
        assert "No logs found" in result.stdout

    @patch('dfo.cmd.azure_logs.ActionLogger')
    def test_list_logs_json_format(self, mock_logger_class):
        """Test JSON output format."""
        # Mock logger
        mock_logger = Mock()
        mock_logs = [
            ActionLog(
                action_id="act-123",
                plan_id="direct-123",
                vm_id="vm-id-1",
                vm_name="test-vm-1",
                resource_group="test-rg",
                action_type="stop",
                action_status="completed",
                executed=False,
                execution_time=datetime(2025, 11, 27, 14, 30),
                duration_seconds=0.5,
                result_message="[DRY RUN] Would execute stop",
                reason="Cost optimization",
                metadata={"source": "direct_execution"}
            )
        ]
        mock_logger.query_logs.return_value = mock_logs
        mock_logger.get_logs_summary.return_value = {
            "total_actions": 1,
            "live_executions": 0,
            "dry_run_simulations": 1
        }
        mock_logger_class.return_value = mock_logger

        # Run command
        result = runner.invoke(app, ["list", "--format", "json"])

        # Verify JSON output
        assert result.exit_code == 0
        assert "act-123" in result.stdout
        assert "test-vm-1" in result.stdout

    @patch('dfo.cmd.azure_logs.ActionLogger')
    def test_list_logs_compact_format(self, mock_logger_class):
        """Test compact output format."""
        # Mock logger
        mock_logger = Mock()
        mock_logs = [
            ActionLog(
                action_id="act-123",
                plan_id="direct-123",
                vm_id="vm-id-1",
                vm_name="test-vm-1",
                resource_group="test-rg",
                action_type="stop",
                action_status="completed",
                executed=False,
                execution_time=datetime(2025, 11, 27, 14, 30),
                duration_seconds=0.5,
                result_message="[DRY RUN] Would execute stop",
                reason="Cost optimization",
                metadata={"source": "direct_execution"}
            )
        ]
        mock_logger.query_logs.return_value = mock_logs
        mock_logger.get_logs_summary.return_value = {
            "total_actions": 1,
            "live_executions": 0,
            "dry_run_simulations": 1
        }
        mock_logger_class.return_value = mock_logger

        # Run command
        result = runner.invoke(app, ["list", "--format", "compact"])

        # Verify compact output
        assert result.exit_code == 0
        assert "test-vm-1" in result.stdout


class TestLogsShowCommand:
    """Tests for logs show command."""

    @patch('dfo.cmd.azure_logs.ActionLogger')
    def test_show_log_success(self, mock_logger_class):
        """Test showing a specific log."""
        # Mock logger
        mock_logger = Mock()
        mock_log = ActionLog(
            action_id="act-123",
            plan_id="direct-123",
            vm_id="vm-id-1",
            vm_name="test-vm-1",
            resource_group="test-rg",
            action_type="stop",
            action_status="completed",
            executed=False,
            execution_time=datetime(2025, 11, 27, 14, 30),
            duration_seconds=0.5,
            result_message="[DRY RUN] Would execute stop",
            reason="Cost optimization",
            metadata={"source": "direct_execution", "user": "john"}
        )
        mock_logger.get_action.return_value = mock_log
        mock_logger_class.return_value = mock_logger

        # Run command
        result = runner.invoke(app, ["show", "act-123"])

        # Verify
        assert result.exit_code == 0
        mock_logger.get_action.assert_called_once_with("act-123")
        assert "act-123" in result.stdout
        assert "test-vm-1" in result.stdout
        assert "stop" in result.stdout

    @patch('dfo.cmd.azure_logs.ActionLogger')
    def test_show_log_not_found(self, mock_logger_class):
        """Test showing non-existent log."""
        # Mock logger to return None
        mock_logger = Mock()
        mock_logger.get_action.return_value = None
        mock_logger_class.return_value = mock_logger

        # Run command
        result = runner.invoke(app, ["show", "act-nonexistent"])

        # Verify
        assert result.exit_code == 1
        assert "Action not found" in result.stdout

    @patch('dfo.cmd.azure_logs.ActionLogger')
    def test_show_log_json_format(self, mock_logger_class):
        """Test showing log in JSON format."""
        # Mock logger
        mock_logger = Mock()
        mock_log = ActionLog(
            action_id="act-123",
            plan_id="direct-123",
            vm_id="vm-id-1",
            vm_name="test-vm-1",
            resource_group="test-rg",
            action_type="stop",
            action_status="completed",
            executed=False,
            execution_time=datetime(2025, 11, 27, 14, 30),
            duration_seconds=0.5,
            result_message="[DRY RUN] Would execute stop",
            reason="Cost optimization",
            metadata={"source": "direct_execution"}
        )
        mock_logger.get_action.return_value = mock_log
        mock_logger_class.return_value = mock_logger

        # Run command
        result = runner.invoke(app, ["show", "act-123", "--format", "json"])

        # Verify
        assert result.exit_code == 0
        assert "act-123" in result.stdout


class TestParseSince:
    """Tests for _parse_since helper function."""

    def test_parse_since_days(self):
        """Test parsing relative days format."""
        result = _parse_since("7d")
        expected = datetime.utcnow() - timedelta(days=7)

        # Allow 1 second tolerance for test execution time
        assert abs((result - expected).total_seconds()) < 1

    def test_parse_since_hours(self):
        """Test parsing relative hours format."""
        result = _parse_since("24h")
        expected = datetime.utcnow() - timedelta(hours=24)

        # Allow 1 second tolerance
        assert abs((result - expected).total_seconds()) < 1

    def test_parse_since_absolute_date(self):
        """Test parsing absolute date format."""
        result = _parse_since("2025-01-01")
        expected = datetime(2025, 1, 1, 0, 0, 0)

        assert result == expected

    def test_parse_since_invalid_format(self):
        """Test invalid format raises error."""
        with pytest.raises(ValueError) as exc_info:
            _parse_since("invalid")

        assert "Invalid since format" in str(exc_info.value)


class TestLogsCommandErrors:
    """Tests for error handling in logs commands."""

    @patch('dfo.cmd.azure_logs.ActionLogger')
    def test_list_logs_exception(self, mock_logger_class):
        """Test handling of unexpected exception in list."""
        # Mock logger to raise exception
        mock_logger = Mock()
        mock_logger.query_logs.side_effect = Exception("Database error")
        mock_logger_class.return_value = mock_logger

        # Run command
        result = runner.invoke(app, ["list"])

        # Verify error handling
        assert result.exit_code == 1
        assert "Error listing logs" in result.stdout

    @patch('dfo.cmd.azure_logs.ActionLogger')
    def test_show_log_exception(self, mock_logger_class):
        """Test handling of unexpected exception in show."""
        # Mock logger to raise exception
        mock_logger = Mock()
        mock_logger.get_action.side_effect = Exception("Database error")
        mock_logger_class.return_value = mock_logger

        # Run command
        result = runner.invoke(app, ["show", "act-123"])

        # Verify error handling
        assert result.exit_code == 1
        assert "Error showing log" in result.stdout
