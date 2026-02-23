"""Integration tests for direct execution feature.

These tests verify the full end-to-end workflow from CLI command
through validation, execution, and logging. They test the integration
between multiple components rather than individual units.
"""
import pytest
import tempfile
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, call
from typer.testing import CliRunner

from dfo.cmd import azure
from dfo.execute.direct import (
    DirectExecutionManager,
    DirectExecutionRequest,
    ExecutionResult,
)
from dfo.execute.action_logger import ActionLogger
from dfo.db.duck import DuckDBManager


runner = CliRunner()


class TestFullExecutionWorkflow:
    """Integration tests for complete execution workflow."""

    @patch('dfo.execute.action_logger.ActionLogger.create_log_entry')
    @patch('dfo.execute.action_logger.ActionLogger.update_log_entry')
    @patch('dfo.execute.direct.get_compute_client')
    @patch('dfo.execute.direct.get_settings')
    def test_dry_run_full_workflow(self, mock_settings, mock_compute, mock_update_log, mock_create_log):
        """Test complete dry-run workflow from request to result."""
        # Setup mocks
        mock_settings.return_value.dfo_enable_direct_execution = True

        # Mock VM data
        mock_vm = Mock()
        mock_vm.id = "/subscriptions/sub1/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm"
        mock_vm.name = "test-vm"
        mock_vm.location = "eastus"
        mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm.instance_view.statuses = [Mock(code="PowerState/running")]
        mock_vm.storage_profile.os_disk.os_type = "Linux"
        mock_vm.tags = {}

        mock_compute.return_value.virtual_machines.get.return_value = mock_vm

        # Mock ActionLogger
        mock_create_log.return_value = "act-test-123"

        # Execute workflow
        manager = DirectExecutionManager()
        request = DirectExecutionRequest(
            resource_type="vm",
            resource_name="test-vm",
            action="stop",
            resource_group="test-rg",
            dry_run=True,
            yes=True
        )

        result = manager.execute(request)

        # Verify result
        assert result.success is True
        assert result.action_id == "act-test-123"
        assert "[DRY RUN]" in result.message
        assert result.post_state is None  # Dry-run doesn't capture post-state

        # Verify log entry was created
        mock_create_log.assert_called_once()
        call_kwargs = mock_create_log.call_args[1]
        assert call_kwargs["action_type"] == "stop"
        assert call_kwargs["vm_name"] == "test-vm"
        assert call_kwargs["executed"] is False

        # Verify log entry was updated
        assert mock_update_log.call_count >= 1

        # Verify no Azure action was called
        mock_compute.return_value.virtual_machines.begin_power_off.assert_not_called()

    @patch('dfo.execute.action_logger.ActionLogger.create_log_entry')
    @patch('dfo.execute.action_logger.ActionLogger.update_log_entry')
    @patch('dfo.execute.direct.get_compute_client')
    @patch('dfo.execute.direct.get_settings')
    def test_live_execution_full_workflow(self, mock_settings, mock_compute, mock_update_log, mock_create_log):
        """Test complete live execution workflow with actual Azure calls."""
        # Setup mocks
        mock_settings.return_value.dfo_enable_direct_execution = True

        # Mock VM data (before action)
        mock_vm_running = Mock()
        mock_vm_running.id = "/subscriptions/sub1/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm"
        mock_vm_running.name = "test-vm"
        mock_vm_running.location = "eastus"
        mock_vm_running.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm_running.instance_view.statuses = [Mock(code="PowerState/running")]
        mock_vm_running.storage_profile.os_disk.os_type = "Linux"
        mock_vm_running.tags = {}

        # Mock VM data (after action)
        mock_vm_stopped = Mock()
        mock_vm_stopped.id = mock_vm_running.id
        mock_vm_stopped.name = "test-vm"
        mock_vm_stopped.location = "eastus"
        mock_vm_stopped.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm_stopped.instance_view.statuses = [Mock(code="PowerState/stopped")]
        mock_vm_stopped.storage_profile.os_disk.os_type = "Linux"
        mock_vm_stopped.tags = {}

        # First call returns running, second call (post-execution) returns stopped
        mock_compute_client = mock_compute.return_value
        mock_compute_client.virtual_machines.get.side_effect = [mock_vm_running, mock_vm_stopped]

        # Mock Azure operation
        mock_poller = Mock()
        mock_poller.wait.return_value = None
        mock_compute_client.virtual_machines.begin_power_off.return_value = mock_poller

        # Mock ActionLogger
        mock_create_log.return_value = "act-live-test-123"

        # Execute workflow
        manager = DirectExecutionManager()
        request = DirectExecutionRequest(
            resource_type="vm",
            resource_name="test-vm",
            action="stop",
            resource_group="test-rg",
            dry_run=False,
            yes=True,
            reason="Integration test"
        )

        result = manager.execute(request)

        # Verify result
        assert result.success is True
        assert result.action_id == "act-live-test-123"
        assert "stopped successfully" in result.message
        assert result.post_state is not None
        assert result.post_state["power_state"] == "stopped"
        assert result.duration_seconds > 0

        # Verify Azure action was called
        mock_compute_client.virtual_machines.begin_power_off.assert_called_once_with(
            resource_group_name="test-rg",
            vm_name="test-vm"
        )
        mock_poller.wait.assert_called_once()

        # Verify log entry was created
        mock_create_log.assert_called_once()
        call_kwargs = mock_create_log.call_args[1]
        assert call_kwargs["action_type"] == "stop"
        assert call_kwargs["vm_name"] == "test-vm"
        assert call_kwargs["executed"] is True
        assert call_kwargs["reason"] == "Integration test"

        # Verify log entry was updated
        assert mock_update_log.call_count >= 1


class TestValidationIntegration:
    """Integration tests for validation workflow."""

    @patch('dfo.execute.direct.get_db')
    @patch('dfo.execute.direct.get_compute_client')
    @patch('dfo.execute.direct.get_settings')
    def test_multi_layer_validation_flow(self, mock_settings, mock_compute, mock_db):
        """Test that all validation layers are executed in correct order."""
        # Setup
        mock_settings.return_value.dfo_enable_direct_execution = True

        # Mock VM with protected tag (should fail Azure validation)
        mock_vm = Mock()
        mock_vm.id = "/subscriptions/sub1/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm"
        mock_vm.name = "test-vm"
        mock_vm.location = "eastus"
        mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm.instance_view.statuses = [Mock(code="PowerState/running")]
        mock_vm.storage_profile.os_disk.os_type = "Linux"
        mock_vm.tags = {"dfo-protected": "true"}  # Protection tag

        mock_compute.return_value.virtual_machines.get.return_value = mock_vm

        # Mock database
        mock_db_instance = Mock()
        mock_db.return_value = mock_db_instance
        mock_db_instance.get_connection.return_value = Mock()

        # Execute
        manager = DirectExecutionManager()
        request = DirectExecutionRequest(
            resource_type="vm",
            resource_name="test-vm",
            action="stop",
            resource_group="test-rg",
            dry_run=True
        )

        # Should fail at Azure validation layer
        from dfo.execute.direct import ValidationError
        with pytest.raises(ValidationError) as exc_info:
            manager.execute(request)

        assert "dfo-protected" in str(exc_info.value)

        # Verify resource validation passed (VM was found)
        mock_compute.return_value.virtual_machines.get.assert_called_once()

    @patch('dfo.execute.action_logger.ActionLogger.create_log_entry')
    @patch('dfo.execute.action_logger.ActionLogger.update_log_entry')
    @patch('dfo.execute.direct.get_compute_client')
    @patch('dfo.execute.direct.get_settings')
    def test_validation_skip_with_no_validation_flag(self, mock_settings, mock_compute, mock_update_log, mock_create_log):
        """Test that --no-validation flag skips validation layers."""
        # Setup
        mock_settings.return_value.dfo_enable_direct_execution = True

        # Mock VM with issues that would normally fail validation
        mock_vm = Mock()
        mock_vm.id = "/subscriptions/sub1/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm"
        mock_vm.name = "test-vm"
        mock_vm.location = "eastus"
        mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm.instance_view.statuses = [Mock(code="PowerState/stopped")]  # Already stopped
        mock_vm.storage_profile.os_disk.os_type = "Linux"
        mock_vm.tags = {"dfo-protected": "true"}  # Would fail validation

        mock_compute.return_value.virtual_machines.get.return_value = mock_vm

        # Mock ActionLogger
        mock_create_log.return_value = "act-validation-skip-123"

        # Execute with no_validation flag
        manager = DirectExecutionManager()
        request = DirectExecutionRequest(
            resource_type="vm",
            resource_name="test-vm",
            action="stop",
            resource_group="test-rg",
            dry_run=True,
            yes=True,
            no_validation=True  # Skip validations
        )

        result = manager.execute(request)

        # Should succeed despite validation issues
        assert result.success is True
        assert result.action_id == "act-validation-skip-123"

        # Verify log entry was created
        mock_create_log.assert_called_once()
        mock_update_log.assert_called()


class TestCLIIntegration:
    """Integration tests for CLI to execution flow."""

    @patch('dfo.cmd.azure_execute.DirectExecutionManager')
    def test_cli_to_manager_integration(self, mock_manager_class):
        """Test that CLI correctly invokes DirectExecutionManager."""
        # Mock manager
        mock_manager = Mock()
        mock_result = ExecutionResult(
            success=True,
            action_id="act-integration-123",
            message="[DRY RUN] Would execute deallocate",
            duration_seconds=0.5
        )
        mock_manager.execute.return_value = mock_result
        mock_manager_class.return_value = mock_manager

        # Execute CLI command
        result = runner.invoke(azure.app, [
            "execute", "vm",
            "test-vm",
            "deallocate",
            "-g", "test-rg",
            "--reason", "Integration test",
            "--dry-run"
        ])

        # Verify CLI succeeded
        assert result.exit_code == 0

        # Verify manager was called correctly
        mock_manager.execute.assert_called_once()
        call_args = mock_manager.execute.call_args
        request = call_args[0][0]

        # Verify request parameters
        assert request.resource_name == "test-vm"
        assert request.action == "deallocate"
        assert request.resource_group == "test-rg"
        assert request.reason == "Integration test"
        assert request.dry_run is True


class TestErrorPropagation:
    """Integration tests for error handling across components."""

    @patch('dfo.execute.action_logger.ActionLogger.create_log_entry')
    @patch('dfo.execute.action_logger.ActionLogger.update_log_entry')
    @patch('dfo.execute.direct.get_compute_client')
    @patch('dfo.execute.direct.get_settings')
    def test_azure_error_propagation(self, mock_settings, mock_compute, mock_update_log, mock_create_log):
        """Test that Azure errors are properly caught and logged."""
        # Setup
        mock_settings.return_value.dfo_enable_direct_execution = True

        # Mock VM
        mock_vm = Mock()
        mock_vm.id = "/subscriptions/sub1/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm"
        mock_vm.name = "test-vm"
        mock_vm.location = "eastus"
        mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm.instance_view.statuses = [Mock(code="PowerState/running")]
        mock_vm.storage_profile.os_disk.os_type = "Linux"
        mock_vm.tags = {}

        mock_compute.return_value.virtual_machines.get.return_value = mock_vm

        # Mock Azure operation failure
        mock_compute.return_value.virtual_machines.begin_power_off.side_effect = Exception("Azure error: Insufficient permissions")

        # Mock ActionLogger
        mock_create_log.return_value = "act-error-test-123"

        # Execute
        manager = DirectExecutionManager()
        request = DirectExecutionRequest(
            resource_type="vm",
            resource_name="test-vm",
            action="stop",
            resource_group="test-rg",
            dry_run=False,
            yes=True
        )

        result = manager.execute(request)

        # Verify failure is captured
        assert result.success is False
        assert "Azure error" in result.message
        assert result.errors is not None
        assert result.action_id == "act-error-test-123"

        # Verify log entry was created
        mock_create_log.assert_called_once()

        # Verify failure was logged (update should be called with status="failed")
        assert mock_update_log.call_count >= 1
        # Check that one of the update calls includes failure status
        update_calls = [call[1] for call in mock_update_log.call_args_list]
        assert any("failed" in str(call.get("status", "")) for call in update_calls)

    @patch('dfo.cmd.azure_execute.DirectExecutionManager')
    def test_cli_error_handling(self, mock_manager_class):
        """Test that CLI properly handles and displays errors."""
        from dfo.execute.direct import ValidationError

        # Mock manager to raise validation error
        mock_manager = Mock()
        mock_manager.execute.side_effect = ValidationError(
            "Cannot stop VM - already in state: stopped"
        )
        mock_manager_class.return_value = mock_manager

        # Execute CLI command
        result = runner.invoke(azure.app, [
            "execute", "vm",
            "test-vm",
            "stop",
            "-g", "test-rg"
        ])

        # Verify error exit code
        assert result.exit_code == 1

        # Verify error message in output
        assert "Validation Failed" in result.output
        assert "already in state: stopped" in result.output


class TestLogIntegration:
    """Integration tests for action logging."""

    @patch('dfo.execute.action_logger.get_db')
    @patch('dfo.execute.action_logger.get_settings')
    def test_action_logger_integration(self, mock_settings, mock_db):
        """Test ActionLogger database integration."""
        # Setup
        mock_settings.return_value.azure_subscription_id = "sub-123"
        mock_settings.return_value.azure_client_id = "client-123"

        # Create real database connection (in-memory)
        import duckdb
        conn = duckdb.connect(":memory:")

        # Create schema
        conn.execute("""
            CREATE TABLE vm_actions (
                action_id TEXT PRIMARY KEY,
                plan_id TEXT,
                vm_id TEXT,
                vm_name TEXT NOT NULL,
                resource_group TEXT NOT NULL,
                action_type TEXT NOT NULL,
                action_status TEXT NOT NULL DEFAULT 'pending',
                executed BOOLEAN NOT NULL,
                execution_time TIMESTAMP NOT NULL,
                duration_seconds DOUBLE,
                result_message TEXT,
                reason TEXT,
                metadata JSON
            )
        """)

        mock_db_instance = Mock()
        mock_db_instance.get_connection.return_value = conn
        mock_db.return_value = mock_db_instance

        # Create logger
        logger = ActionLogger()

        # Create log entry
        action_id = logger.create_log_entry(
            action_type="stop",
            vm_name="integration-test-vm",
            resource_group="test-rg",
            executed=False,
            reason="Integration test",
            pre_state={"power_state": "running"}
        )

        # Verify entry was created
        assert action_id is not None
        assert action_id.startswith("act-")

        # Query entry
        action = logger.get_action(action_id)
        assert action is not None
        assert action.vm_name == "integration-test-vm"
        assert action.action_type == "stop"
        assert action.executed is False

        # Update entry
        logger.update_log_entry(
            action_id=action_id,
            status="completed",
            result_message="Test completed",
            duration_seconds=1.5
        )

        # Verify update
        action = logger.get_action(action_id)
        assert action.action_status == "completed"
        assert action.result_message == "Test completed"
        assert action.duration_seconds == 1.5

        # Clean up
        conn.close()


class TestEdgeCases:
    """Integration tests for edge cases and boundary conditions."""

    @patch('dfo.execute.action_logger.ActionLogger.create_log_entry')
    @patch('dfo.execute.action_logger.ActionLogger.update_log_entry')
    @patch('dfo.execute.direct.get_compute_client')
    @patch('dfo.execute.direct.get_settings')
    def test_concurrent_execution_attempts(self, mock_settings, mock_compute, mock_update_log, mock_create_log):
        """Test that concurrent executions on same VM are handled."""
        # This is a basic test - real concurrency would need more complex setup
        mock_settings.return_value.dfo_enable_direct_execution = True

        mock_vm = Mock()
        mock_vm.id = "/subscriptions/sub1/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm"
        mock_vm.name = "test-vm"
        mock_vm.location = "eastus"
        mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm.instance_view.statuses = [Mock(code="PowerState/running")]
        mock_vm.storage_profile.os_disk.os_type = "Linux"
        mock_vm.tags = {}

        mock_compute.return_value.virtual_machines.get.return_value = mock_vm

        # Mock ActionLogger to return different IDs
        mock_create_log.side_effect = ["act-concurrent-1", "act-concurrent-2"]

        # Execute multiple requests
        manager1 = DirectExecutionManager()
        manager2 = DirectExecutionManager()

        request1 = DirectExecutionRequest(
            resource_type="vm",
            resource_name="test-vm",
            action="stop",
            resource_group="test-rg",
            dry_run=True,
            yes=True
        )

        request2 = DirectExecutionRequest(
            resource_type="vm",
            resource_name="test-vm",
            action="deallocate",
            resource_group="test-rg",
            dry_run=True,
            yes=True
        )

        # Both should succeed (dry-run)
        result1 = manager1.execute(request1)
        result2 = manager2.execute(request2)

        assert result1.success is True
        assert result2.success is True
        assert result1.action_id == "act-concurrent-1"
        assert result2.action_id == "act-concurrent-2"
        assert result1.action_id != result2.action_id  # Different action IDs

        # Verify both actions were logged
        assert mock_create_log.call_count == 2

    @patch('dfo.execute.action_logger.ActionLogger.create_log_entry')
    @patch('dfo.execute.action_logger.ActionLogger.update_log_entry')
    @patch('dfo.execute.direct.get_compute_client')
    @patch('dfo.execute.direct.get_settings')
    def test_execution_with_missing_optional_data(self, mock_settings, mock_compute, mock_update_log, mock_create_log):
        """Test execution when optional VM data is missing."""
        mock_settings.return_value.dfo_enable_direct_execution = True

        # Mock VM with minimal data
        mock_vm = Mock()
        mock_vm.id = None  # Missing ID
        mock_vm.name = "test-vm"
        mock_vm.location = "eastus"
        mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm.instance_view.statuses = [Mock(code="PowerState/running")]
        mock_vm.storage_profile = None  # Missing storage profile
        mock_vm.tags = None  # Missing tags

        mock_compute.return_value.virtual_machines.get.return_value = mock_vm

        # Mock ActionLogger
        mock_create_log.return_value = "act-missing-data-123"

        # Execute - should handle missing data gracefully
        manager = DirectExecutionManager()
        request = DirectExecutionRequest(
            resource_type="vm",
            resource_name="test-vm",
            action="stop",
            resource_group="test-rg",
            dry_run=True,
            yes=True
        )

        result = manager.execute(request)

        # Should succeed despite missing data
        assert result.success is True
        assert result.action_id == "act-missing-data-123"

        # Verify log entry was created
        mock_create_log.assert_called_once()
        mock_update_log.assert_called()
