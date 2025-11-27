"""Tests for azure execute CLI commands.

Tests the direct execution CLI commands to ensure proper integration
with DirectExecutionManager and correct error handling.
"""
import pytest
from typer.testing import CliRunner
from unittest.mock import Mock, patch, MagicMock

# Import azure app (parent) to test execute commands in full context
from dfo.cmd import azure
from dfo.execute.direct import (
    ExecutionResult,
    FeatureDisabledError,
    ResourceNotFoundError,
    ValidationError,
    ExecutionError,
)

runner = CliRunner()
# Test through azure app to avoid Typer subcommand limitations
app = azure.app


class TestExecuteVMCommand:
    """Tests for execute vm command."""

    @patch('dfo.cmd.azure_execute.DirectExecutionManager')
    def test_execute_vm_dry_run_success(self, mock_manager_class):
        """Test successful dry-run execution."""
        # Mock manager
        mock_manager = Mock()
        mock_result = ExecutionResult(
            success=True,
            action_id="act-123",
            message="[DRY RUN] Would execute stop",
            duration_seconds=0.5
        )
        mock_manager.execute.return_value = mock_result
        mock_manager_class.return_value = mock_manager

        # Run command
        result = runner.invoke(app, ["execute",
            "vm",
            "test-vm",
            "stop",
            "-g", "test-rg"
        ])

        # Verify
        assert result.exit_code == 0
        mock_manager.execute.assert_called_once()

        # Check request parameters
        call_args = mock_manager.execute.call_args
        request = call_args[0][0]
        assert request.resource_name == "test-vm"
        assert request.action == "stop"
        assert request.resource_group == "test-rg"
        assert request.dry_run is True  # Default

    @patch('dfo.cmd.azure_execute.DirectExecutionManager')
    def test_execute_vm_live_execution(self, mock_manager_class):
        """Test live execution with --no-dry-run."""
        # Mock manager
        mock_manager = Mock()
        mock_result = ExecutionResult(
            success=True,
            action_id="act-456",
            message="VM stopped successfully",
            duration_seconds=12.5
        )
        mock_manager.execute.return_value = mock_result
        mock_manager_class.return_value = mock_manager

        # Run command
        result = runner.invoke(app, ["execute",
            "vm",
            "test-vm",
            "stop",
            "-g", "test-rg",
            "--no-dry-run",
            "--yes"
        ])

        # Verify
        assert result.exit_code == 0

        # Check request parameters
        call_args = mock_manager.execute.call_args
        request = call_args[0][0]
        assert request.dry_run is False
        assert request.yes is True

    @patch('dfo.cmd.azure_execute.DirectExecutionManager')
    def test_execute_vm_with_reason(self, mock_manager_class):
        """Test execution with reason parameter."""
        # Mock manager
        mock_manager = Mock()
        mock_result = ExecutionResult(
            success=True,
            action_id="act-789",
            message="[DRY RUN] Would execute deallocate",
            duration_seconds=0.5
        )
        mock_manager.execute.return_value = mock_result
        mock_manager_class.return_value = mock_manager

        # Run command
        result = runner.invoke(app, ["execute",
            "vm",
            "test-vm",
            "deallocate",
            "-g", "test-rg",
            "--reason", "Cost optimization"
        ])

        # Verify
        assert result.exit_code == 0

        # Check request parameters
        call_args = mock_manager.execute.call_args
        request = call_args[0][0]
        assert request.reason == "Cost optimization"

    @patch('dfo.cmd.azure_execute.DirectExecutionManager')
    def test_execute_vm_downsize_with_target_sku(self, mock_manager_class):
        """Test downsize with target SKU."""
        # Mock manager
        mock_manager = Mock()
        mock_result = ExecutionResult(
            success=True,
            action_id="act-abc",
            message="[DRY RUN] Would downsize to Standard_B2s",
            duration_seconds=0.5
        )
        mock_manager.execute.return_value = mock_result
        mock_manager_class.return_value = mock_manager

        # Run command
        result = runner.invoke(app, ["execute",
            "vm",
            "test-vm",
            "downsize",
            "-g", "test-rg",
            "-t", "Standard_B2s"
        ])

        # Verify
        assert result.exit_code == 0

        # Check request parameters
        call_args = mock_manager.execute.call_args
        request = call_args[0][0]
        assert request.action == "downsize"
        assert request.target_sku == "Standard_B2s"

    @patch('dfo.cmd.azure_execute.DirectExecutionManager')
    def test_execute_vm_with_force_flag(self, mock_manager_class):
        """Test execution with force flag."""
        # Mock manager
        mock_manager = Mock()
        mock_result = ExecutionResult(
            success=True,
            action_id="act-def",
            message="[DRY RUN] Would execute stop",
            duration_seconds=0.5
        )
        mock_manager.execute.return_value = mock_result
        mock_manager_class.return_value = mock_manager

        # Run command
        result = runner.invoke(app, ["execute",
            "vm",
            "test-vm",
            "stop",
            "-g", "test-rg",
            "--force"
        ])

        # Verify
        assert result.exit_code == 0

        # Check request parameters
        call_args = mock_manager.execute.call_args
        request = call_args[0][0]
        assert request.force is True

    @patch('dfo.cmd.azure_execute.DirectExecutionManager')
    def test_execute_vm_with_no_validation_flag(self, mock_manager_class):
        """Test execution with no-validation flag."""
        # Mock manager
        mock_manager = Mock()
        mock_result = ExecutionResult(
            success=True,
            action_id="act-ghi",
            message="[DRY RUN] Would execute stop",
            duration_seconds=0.5
        )
        mock_manager.execute.return_value = mock_result
        mock_manager_class.return_value = mock_manager

        # Run command
        result = runner.invoke(app, ["execute",
            "vm",
            "test-vm",
            "stop",
            "-g", "test-rg",
            "--no-validation"
        ])

        # Verify
        assert result.exit_code == 0

        # Check request parameters
        call_args = mock_manager.execute.call_args
        request = call_args[0][0]
        assert request.no_validation is True


class TestExecuteVMCommandErrors:
    """Tests for error handling in execute vm command."""

    @patch('dfo.cmd.azure_execute.DirectExecutionManager')
    def test_feature_disabled_error(self, mock_manager_class):
        """Test feature disabled error is handled correctly."""
        # Mock manager to raise FeatureDisabledError
        mock_manager = Mock()
        mock_manager.execute.side_effect = FeatureDisabledError(
            "Direct execution is disabled. Set DFO_ENABLE_DIRECT_EXECUTION=true to enable."
        )
        mock_manager_class.return_value = mock_manager

        # Run command
        result = runner.invoke(app, ["execute",
            "vm",
            "test-vm",
            "stop",
            "-g", "test-rg"
        ])

        # Verify error handling
        assert result.exit_code == 1
        assert "Feature Disabled" in result.output
        assert "Direct execution is disabled" in result.output

    @patch('dfo.cmd.azure_execute.DirectExecutionManager')
    def test_resource_not_found_error(self, mock_manager_class):
        """Test resource not found error is handled correctly."""
        # Mock manager to raise ResourceNotFoundError
        mock_manager = Mock()
        mock_manager.execute.side_effect = ResourceNotFoundError(
            "VM 'nonexistent-vm' not found in resource group 'test-rg'"
        )
        mock_manager_class.return_value = mock_manager

        # Run command
        result = runner.invoke(app, ["execute",
            "vm",
            "nonexistent-vm",
            "stop",
            "-g", "test-rg"
        ])

        # Verify error handling
        assert result.exit_code == 1
        assert "Resource Not Found" in result.output
        assert "nonexistent-vm" in result.output

    @patch('dfo.cmd.azure_execute.DirectExecutionManager')
    def test_validation_error(self, mock_manager_class):
        """Test validation error is handled correctly."""
        # Mock manager to raise ValidationError
        mock_manager = Mock()
        mock_manager.execute.side_effect = ValidationError(
            "Cannot stop VM - already in state: stopped"
        )
        mock_manager_class.return_value = mock_manager

        # Run command
        result = runner.invoke(app, ["execute",
            "vm",
            "test-vm",
            "stop",
            "-g", "test-rg"
        ])

        # Verify error handling
        assert result.exit_code == 1
        assert "Validation Failed" in result.output
        assert "already in state: stopped" in result.output

    @patch('dfo.cmd.azure_execute.DirectExecutionManager')
    def test_execution_error(self, mock_manager_class):
        """Test execution error is handled correctly."""
        # Mock manager to raise ExecutionError
        mock_manager = Mock()
        mock_manager.execute.side_effect = ExecutionError(
            "Action execution failed: Azure error"
        )
        mock_manager_class.return_value = mock_manager

        # Run command
        result = runner.invoke(app, ["execute",
            "vm",
            "test-vm",
            "stop",
            "-g", "test-rg",
            "--no-dry-run",
            "--yes"
        ])

        # Verify error handling
        assert result.exit_code == 1
        assert "Execution Failed" in result.output
        assert "Azure error" in result.output

    @patch('dfo.cmd.azure_execute.DirectExecutionManager')
    def test_execution_failure_result(self, mock_manager_class):
        """Test handling of failed execution result."""
        # Mock manager to return failed result
        mock_manager = Mock()
        mock_result = ExecutionResult(
            success=False,
            action_id="act-fail",
            message="Execution failed",
            duration_seconds=5.0,
            errors=["Azure error", "Network timeout"]
        )
        mock_manager.execute.return_value = mock_result
        mock_manager_class.return_value = mock_manager

        # Run command
        result = runner.invoke(app, ["execute",
            "vm",
            "test-vm",
            "stop",
            "-g", "test-rg"
        ])

        # Verify exit code indicates failure
        assert result.exit_code == 1

    @patch('dfo.cmd.azure_execute.DirectExecutionManager')
    def test_unexpected_error(self, mock_manager_class):
        """Test handling of unexpected errors."""
        # Mock manager to raise unexpected exception
        mock_manager = Mock()
        mock_manager.execute.side_effect = Exception("Unexpected error occurred")
        mock_manager_class.return_value = mock_manager

        # Run command
        result = runner.invoke(app, ["execute",
            "vm",
            "test-vm",
            "stop",
            "-g", "test-rg"
        ])

        # Verify error handling
        assert result.exit_code == 1
        assert "Unexpected Error" in result.output


class TestExecuteVMCommandValidation:
    """Tests for CLI parameter validation."""

    def test_missing_resource_group(self):
        """Test command fails when resource group is missing."""
        result = runner.invoke(app, ["execute",
            "vm",
            "test-vm",
            "stop"
        ])

        # Should fail due to missing required option
        assert result.exit_code != 0
        assert "--resource-group" in result.output or "required" in result.output.lower()

    def test_missing_vm_name(self):
        """Test command fails when VM name is missing."""
        result = runner.invoke(app, ["execute",
            "vm",
            "stop",
            "-g", "test-rg"
        ])

        # Should fail - action cannot be used as VM name
        assert result.exit_code != 0

    def test_missing_action(self):
        """Test command fails when action is missing."""
        result = runner.invoke(app, ["execute",
            "vm",
            "test-vm",
            "-g", "test-rg"
        ])

        # Should fail due to missing action
        assert result.exit_code != 0
