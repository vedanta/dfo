"""Tests for direct execution module.

Tests DirectExecutionRequest and DirectExecutionManager classes.
Covers validation, feature flags, execution flow, and error handling.
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from dataclasses import asdict

from dfo.execute.direct import (
    DirectExecutionRequest,
    DirectExecutionManager,
    ExecutionResult,
    ActionType,
    ResourceType,
    FeatureDisabledError,
    ResourceNotFoundError,
    ValidationError,
    ExecutionError,
)


class TestDirectExecutionRequest:
    """Tests for DirectExecutionRequest dataclass."""

    def test_valid_request_vm_stop(self):
        """Test creating valid VM stop request."""
        request = DirectExecutionRequest(
            resource_type="vm",
            resource_name="test-vm",
            action="stop",
            resource_group="test-rg"
        )

        assert request.resource_type == "vm"
        assert request.resource_name == "test-vm"
        assert request.action == "stop"
        assert request.resource_group == "test-rg"
        assert request.dry_run is True  # Default
        assert request.force is False
        assert request.yes is False

    def test_valid_request_vm_deallocate(self):
        """Test creating valid VM deallocate request."""
        request = DirectExecutionRequest(
            resource_type="vm",
            resource_name="test-vm",
            action="deallocate",
            resource_group="test-rg",
            reason="Cost savings"
        )

        assert request.action == "deallocate"
        assert request.reason == "Cost savings"

    def test_valid_request_vm_downsize(self):
        """Test creating valid VM downsize request."""
        request = DirectExecutionRequest(
            resource_type="vm",
            resource_name="test-vm",
            action="downsize",
            resource_group="test-rg",
            target_sku="Standard_B2s"
        )

        assert request.action == "downsize"
        assert request.target_sku == "Standard_B2s"

    def test_invalid_resource_type(self):
        """Test invalid resource type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            DirectExecutionRequest(
                resource_type="invalid",
                resource_name="test-vm",
                action="stop",
                resource_group="test-rg"
            )

        assert "Invalid resource type: invalid" in str(exc_info.value)
        assert "vm" in str(exc_info.value)

    def test_invalid_action_type(self):
        """Test invalid action type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            DirectExecutionRequest(
                resource_type="vm",
                resource_name="test-vm",
                action="invalid",
                resource_group="test-rg"
            )

        assert "Invalid action: invalid" in str(exc_info.value)
        assert "stop" in str(exc_info.value)

    def test_downsize_without_target_sku(self):
        """Test downsize without target_sku raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            DirectExecutionRequest(
                resource_type="vm",
                resource_name="test-vm",
                action="downsize",
                resource_group="test-rg"
            )

        assert "target_sku" in str(exc_info.value)

    def test_missing_resource_group(self):
        """Test missing resource_group raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            DirectExecutionRequest(
                resource_type="vm",
                resource_name="test-vm",
                action="stop",
                resource_group=""
            )

        assert "resource_group is required" in str(exc_info.value)


class TestDirectExecutionManagerFeatureFlag:
    """Tests for feature flag checking."""

    @patch('dfo.execute.direct.get_settings')
    def test_feature_disabled(self, mock_settings):
        """Test execution fails when feature is disabled."""
        # Mock settings with feature disabled
        mock_settings.return_value.dfo_enable_direct_execution = False

        manager = DirectExecutionManager()
        request = DirectExecutionRequest(
            resource_type="vm",
            resource_name="test-vm",
            action="stop",
            resource_group="test-rg"
        )

        with pytest.raises(FeatureDisabledError) as exc_info:
            manager.execute(request)

        assert "Direct execution is disabled" in str(exc_info.value)
        assert "DFO_ENABLE_DIRECT_EXECUTION=true" in str(exc_info.value)

    @patch('dfo.execute.direct.get_db')
    @patch('dfo.execute.direct.get_compute_client')
    @patch('dfo.execute.direct.ActionLogger')
    @patch('dfo.execute.direct.get_settings')
    def test_feature_enabled(self, mock_settings, mock_logger, mock_compute, mock_db):
        """Test execution proceeds when feature is enabled."""
        # Mock settings with feature enabled
        mock_settings.return_value.dfo_enable_direct_execution = True

        # Mock Azure client
        mock_vm = Mock()
        mock_vm.id = "/subscriptions/sub1/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm"
        mock_vm.name = "test-vm"
        mock_vm.location = "eastus"
        mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm.instance_view.statuses = [Mock(code="PowerState/running")]
        mock_vm.storage_profile.os_disk.os_type = "Linux"
        mock_vm.tags = {}

        mock_compute.return_value.virtual_machines.get.return_value = mock_vm

        # Mock database
        mock_db_instance = Mock()
        mock_db.return_value.get_connection.return_value = mock_db_instance

        # Mock logger
        mock_logger_instance = Mock()
        mock_logger_instance.create_log_entry.return_value = "act-123"
        mock_logger.return_value = mock_logger_instance

        # Create manager and execute (dry run)
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

        # Should succeed
        assert result.success is True
        assert result.action_id == "act-123"


class TestDirectExecutionManagerResourceValidation:
    """Tests for resource validation."""

    @patch('dfo.execute.direct.get_db')
    @patch('dfo.execute.direct.get_compute_client')
    @patch('dfo.execute.direct.ActionLogger')
    @patch('dfo.execute.direct.get_settings')
    def test_vm_found(self, mock_settings, mock_logger, mock_compute, mock_db):
        """Test VM validation succeeds when VM exists."""
        # Mock settings
        mock_settings.return_value.dfo_enable_direct_execution = True

        # Mock Azure client
        mock_vm = Mock()
        mock_vm.id = "/subscriptions/sub1/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm"
        mock_vm.name = "test-vm"
        mock_vm.location = "eastus"
        mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm.instance_view.statuses = [Mock(code="PowerState/running")]
        mock_vm.storage_profile.os_disk.os_type = "Linux"
        mock_vm.tags = {}

        mock_compute.return_value.virtual_machines.get.return_value = mock_vm

        # Mock database
        mock_db_instance = Mock()
        mock_db.return_value.get_connection.return_value = mock_db_instance

        # Mock logger
        mock_logger_instance = Mock()
        mock_logger_instance.create_log_entry.return_value = "act-123"
        mock_logger.return_value = mock_logger_instance

        # Execute
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
        assert result.success is True

    @patch('dfo.execute.direct.get_db')
    @patch('dfo.execute.direct.get_compute_client')
    @patch('dfo.execute.direct.ActionLogger')
    @patch('dfo.execute.direct.get_settings')
    def test_vm_not_found(self, mock_settings, mock_logger, mock_compute, mock_db):
        """Test VM validation fails when VM doesn't exist."""
        # Mock settings
        mock_settings.return_value.dfo_enable_direct_execution = True

        # Mock Azure client to raise ResourceNotFound
        from azure.core.exceptions import ResourceNotFoundError as AzureNotFound
        mock_compute.return_value.virtual_machines.get.side_effect = AzureNotFound("VM not found")

        # Mock database
        mock_db_instance = Mock()
        mock_db.return_value.get_connection.return_value = mock_db_instance

        # Execute
        manager = DirectExecutionManager()
        request = DirectExecutionRequest(
            resource_type="vm",
            resource_name="nonexistent-vm",
            action="stop",
            resource_group="test-rg"
        )

        with pytest.raises(ResourceNotFoundError) as exc_info:
            manager.execute(request)

        assert "nonexistent-vm" in str(exc_info.value)
        assert "test-rg" in str(exc_info.value)


class TestDirectExecutionManagerActionValidation:
    """Tests for action validation."""

    @patch('dfo.execute.direct.get_db')
    @patch('dfo.execute.direct.get_compute_client')
    @patch('dfo.execute.direct.ActionLogger')
    @patch('dfo.execute.direct.get_settings')
    def test_stop_already_stopped_vm(self, mock_settings, mock_logger, mock_compute, mock_db):
        """Test stopping already stopped VM raises ValidationError."""
        # Mock settings
        mock_settings.return_value.dfo_enable_direct_execution = True

        # Mock Azure client with stopped VM
        mock_vm = Mock()
        mock_vm.id = "/subscriptions/sub1/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm"
        mock_vm.name = "test-vm"
        mock_vm.location = "eastus"
        mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm.instance_view.statuses = [Mock(code="PowerState/stopped")]
        mock_vm.storage_profile.os_disk.os_type = "Linux"
        mock_vm.tags = {}

        mock_compute.return_value.virtual_machines.get.return_value = mock_vm

        # Mock database
        mock_db_instance = Mock()
        mock_db.return_value.get_connection.return_value = mock_db_instance

        # Execute
        manager = DirectExecutionManager()
        request = DirectExecutionRequest(
            resource_type="vm",
            resource_name="test-vm",
            action="stop",
            resource_group="test-rg"
        )

        with pytest.raises(ValidationError) as exc_info:
            manager.execute(request)

        assert "already in state: stopped" in str(exc_info.value)

    @patch('dfo.execute.direct.get_db')
    @patch('dfo.execute.direct.get_compute_client')
    @patch('dfo.execute.direct.ActionLogger')
    @patch('dfo.execute.direct.get_settings')
    def test_restart_stopped_vm(self, mock_settings, mock_logger, mock_compute, mock_db):
        """Test restarting stopped VM raises ValidationError."""
        # Mock settings
        mock_settings.return_value.dfo_enable_direct_execution = True

        # Mock Azure client with stopped VM
        mock_vm = Mock()
        mock_vm.id = "/subscriptions/sub1/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm"
        mock_vm.name = "test-vm"
        mock_vm.location = "eastus"
        mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm.instance_view.statuses = [Mock(code="PowerState/stopped")]
        mock_vm.storage_profile.os_disk.os_type = "Linux"
        mock_vm.tags = {}

        mock_compute.return_value.virtual_machines.get.return_value = mock_vm

        # Mock database
        mock_db_instance = Mock()
        mock_db.return_value.get_connection.return_value = mock_db_instance

        # Execute
        manager = DirectExecutionManager()
        request = DirectExecutionRequest(
            resource_type="vm",
            resource_name="test-vm",
            action="restart",
            resource_group="test-rg"
        )

        with pytest.raises(ValidationError) as exc_info:
            manager.execute(request)

        assert "Cannot restart VM" in str(exc_info.value)
        assert "stopped" in str(exc_info.value)

    @patch('dfo.execute.direct.get_db')
    @patch('dfo.execute.direct.get_compute_client')
    @patch('dfo.execute.direct.ActionLogger')
    @patch('dfo.execute.direct.get_settings')
    def test_downsize_running_vm(self, mock_settings, mock_logger, mock_compute, mock_db):
        """Test downsizing running VM raises ValidationError."""
        # Mock settings
        mock_settings.return_value.dfo_enable_direct_execution = True

        # Mock Azure client with running VM
        mock_vm = Mock()
        mock_vm.id = "/subscriptions/sub1/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm"
        mock_vm.name = "test-vm"
        mock_vm.location = "eastus"
        mock_vm.hardware_profile.vm_size = "Standard_D4s_v3"
        mock_vm.instance_view.statuses = [Mock(code="PowerState/running")]
        mock_vm.storage_profile.os_disk.os_type = "Linux"
        mock_vm.tags = {}

        mock_compute.return_value.virtual_machines.get.return_value = mock_vm

        # Mock database
        mock_db_instance = Mock()
        mock_db.return_value.get_connection.return_value = mock_db_instance

        # Execute
        manager = DirectExecutionManager()
        request = DirectExecutionRequest(
            resource_type="vm",
            resource_name="test-vm",
            action="downsize",
            resource_group="test-rg",
            target_sku="Standard_D2s_v3"
        )

        with pytest.raises(ValidationError) as exc_info:
            manager.execute(request)

        assert "Cannot downsize running VM" in str(exc_info.value)

    @patch('dfo.execute.direct.get_db')
    @patch('dfo.execute.direct.get_compute_client')
    @patch('dfo.execute.direct.ActionLogger')
    @patch('dfo.execute.direct.get_settings')
    def test_downsize_same_sku(self, mock_settings, mock_logger, mock_compute, mock_db):
        """Test downsizing to same SKU raises ValidationError."""
        # Mock settings
        mock_settings.return_value.dfo_enable_direct_execution = True

        # Mock Azure client with deallocated VM
        mock_vm = Mock()
        mock_vm.id = "/subscriptions/sub1/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm"
        mock_vm.name = "test-vm"
        mock_vm.location = "eastus"
        mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm.instance_view.statuses = [Mock(code="PowerState/deallocated")]
        mock_vm.storage_profile.os_disk.os_type = "Linux"
        mock_vm.tags = {}

        mock_compute.return_value.virtual_machines.get.return_value = mock_vm

        # Mock database
        mock_db_instance = Mock()
        mock_db.return_value.get_connection.return_value = mock_db_instance

        # Execute
        manager = DirectExecutionManager()
        request = DirectExecutionRequest(
            resource_type="vm",
            resource_name="test-vm",
            action="downsize",
            resource_group="test-rg",
            target_sku="Standard_D2s_v3"  # Same as current
        )

        with pytest.raises(ValidationError) as exc_info:
            manager.execute(request)

        assert "same as current SKU" in str(exc_info.value)


class TestDirectExecutionManagerAzureValidation:
    """Tests for Azure-side validation."""

    @patch('dfo.execute.direct.get_db')
    @patch('dfo.execute.direct.get_compute_client')
    @patch('dfo.execute.direct.ActionLogger')
    @patch('dfo.execute.direct.get_settings')
    def test_protected_tag(self, mock_settings, mock_logger, mock_compute, mock_db):
        """Test protected tag prevents execution."""
        # Mock settings
        mock_settings.return_value.dfo_enable_direct_execution = True

        # Mock Azure client with protected VM
        mock_vm = Mock()
        mock_vm.id = "/subscriptions/sub1/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm"
        mock_vm.name = "test-vm"
        mock_vm.location = "eastus"
        mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm.instance_view.statuses = [Mock(code="PowerState/running")]
        mock_vm.storage_profile.os_disk.os_type = "Linux"
        mock_vm.tags = {"dfo-protected": "true"}

        mock_compute.return_value.virtual_machines.get.return_value = mock_vm

        # Mock database
        mock_db_instance = Mock()
        mock_db.return_value.get_connection.return_value = mock_db_instance

        # Execute
        manager = DirectExecutionManager()
        request = DirectExecutionRequest(
            resource_type="vm",
            resource_name="test-vm",
            action="stop",
            resource_group="test-rg"
        )

        with pytest.raises(ValidationError) as exc_info:
            manager.execute(request)

        assert "dfo-protected=true" in str(exc_info.value)


class TestDirectExecutionManagerExecution:
    """Tests for execution flow."""

    @patch('dfo.execute.direct.get_db')
    @patch('dfo.execute.direct.get_compute_client')
    @patch('dfo.execute.direct.ActionLogger')
    @patch('dfo.execute.direct.get_settings')
    def test_dry_run_execution(self, mock_settings, mock_logger, mock_compute, mock_db):
        """Test dry run execution completes without Azure calls."""
        # Mock settings
        mock_settings.return_value.dfo_enable_direct_execution = True

        # Mock Azure client
        mock_vm = Mock()
        mock_vm.id = "/subscriptions/sub1/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm"
        mock_vm.name = "test-vm"
        mock_vm.location = "eastus"
        mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm.instance_view.statuses = [Mock(code="PowerState/running")]
        mock_vm.storage_profile.os_disk.os_type = "Linux"
        mock_vm.tags = {}

        mock_compute.return_value.virtual_machines.get.return_value = mock_vm

        # Mock database
        mock_db_instance = Mock()
        mock_db.return_value.get_connection.return_value = mock_db_instance

        # Mock logger
        mock_logger_instance = Mock()
        mock_logger_instance.create_log_entry.return_value = "act-123"
        mock_logger.return_value = mock_logger_instance

        # Execute
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
        assert result.action_id == "act-123"
        assert "[DRY RUN]" in result.message
        assert result.post_state is None

        # Verify logger called
        mock_logger_instance.create_log_entry.assert_called_once()
        assert mock_logger_instance.create_log_entry.call_args[1]["executed"] is False

        # Verify Azure action NOT called
        mock_compute.return_value.virtual_machines.begin_power_off.assert_not_called()

    @patch('dfo.execute.direct.get_db')
    @patch('dfo.execute.direct.get_compute_client')
    @patch('dfo.execute.direct.ActionLogger')
    @patch('dfo.execute.direct.get_settings')
    def test_live_execution_stop(self, mock_settings, mock_logger, mock_compute, mock_db):
        """Test live execution of stop action."""
        # Mock settings
        mock_settings.return_value.dfo_enable_direct_execution = True

        # Mock Azure client
        mock_vm = Mock()
        mock_vm.id = "/subscriptions/sub1/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm"
        mock_vm.name = "test-vm"
        mock_vm.location = "eastus"
        mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm.instance_view.statuses = [Mock(code="PowerState/running")]
        mock_vm.storage_profile.os_disk.os_type = "Linux"
        mock_vm.tags = {}

        mock_vm_stopped = Mock()
        mock_vm_stopped.id = mock_vm.id
        mock_vm_stopped.name = "test-vm"
        mock_vm_stopped.location = "eastus"
        mock_vm_stopped.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm_stopped.instance_view.statuses = [Mock(code="PowerState/stopped")]
        mock_vm_stopped.storage_profile.os_disk.os_type = "Linux"
        mock_vm_stopped.tags = {}

        mock_compute_client = mock_compute.return_value
        mock_compute_client.virtual_machines.get.side_effect = [mock_vm, mock_vm_stopped]

        # Mock poller for Azure operation
        mock_poller = Mock()
        mock_poller.wait.return_value = None
        mock_compute_client.virtual_machines.begin_power_off.return_value = mock_poller

        # Mock database
        mock_db_instance = Mock()
        mock_db.return_value.get_connection.return_value = mock_db_instance

        # Mock logger
        mock_logger_instance = Mock()
        mock_logger_instance.create_log_entry.return_value = "act-456"
        mock_logger.return_value = mock_logger_instance

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

        # Verify result
        assert result.success is True
        assert result.action_id == "act-456"
        assert "stopped successfully" in result.message
        assert result.post_state is not None
        assert result.post_state["power_state"] == "stopped"

        # Verify logger called
        mock_logger_instance.create_log_entry.assert_called_once()
        assert mock_logger_instance.create_log_entry.call_args[1]["executed"] is True

        # Verify Azure action called
        mock_compute_client.virtual_machines.begin_power_off.assert_called_once_with(
            resource_group_name="test-rg",
            vm_name="test-vm"
        )

    @patch('dfo.execute.direct.get_db')
    @patch('dfo.execute.direct.get_compute_client')
    @patch('dfo.execute.direct.ActionLogger')
    @patch('dfo.execute.direct.get_settings')
    def test_execution_failure(self, mock_settings, mock_logger, mock_compute, mock_db):
        """Test execution failure is handled and logged."""
        # Mock settings
        mock_settings.return_value.dfo_enable_direct_execution = True

        # Mock Azure client
        mock_vm = Mock()
        mock_vm.id = "/subscriptions/sub1/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm"
        mock_vm.name = "test-vm"
        mock_vm.location = "eastus"
        mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm.instance_view.statuses = [Mock(code="PowerState/running")]
        mock_vm.storage_profile.os_disk.os_type = "Linux"
        mock_vm.tags = {}

        mock_compute_client = mock_compute.return_value
        mock_compute_client.virtual_machines.get.return_value = mock_vm

        # Mock Azure operation failure
        mock_compute_client.virtual_machines.begin_power_off.side_effect = Exception("Azure error")

        # Mock database
        mock_db_instance = Mock()
        mock_db.return_value.get_connection.return_value = mock_db_instance

        # Mock logger
        mock_logger_instance = Mock()
        mock_logger_instance.create_log_entry.return_value = "act-789"
        mock_logger.return_value = mock_logger_instance

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

        # Verify result
        assert result.success is False
        assert result.action_id == "act-789"
        assert "Azure error" in result.message
        assert result.errors is not None

        # Verify logger updated with failure
        update_calls = mock_logger_instance.update_log_entry.call_args_list
        assert any(call[1]["status"] == "failed" for call in update_calls)


class TestDirectExecutionManagerSkipValidation:
    """Tests for no_validation flag."""

    @patch('dfo.execute.direct.get_db')
    @patch('dfo.execute.direct.get_compute_client')
    @patch('dfo.execute.direct.ActionLogger')
    @patch('dfo.execute.direct.get_settings')
    def test_skip_validation_with_protected_tag(self, mock_settings, mock_logger, mock_compute, mock_db):
        """Test no_validation flag bypasses Azure validation."""
        # Mock settings
        mock_settings.return_value.dfo_enable_direct_execution = True

        # Mock Azure client with protected VM
        mock_vm = Mock()
        mock_vm.id = "/subscriptions/sub1/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm"
        mock_vm.name = "test-vm"
        mock_vm.location = "eastus"
        mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm.instance_view.statuses = [Mock(code="PowerState/running")]
        mock_vm.storage_profile.os_disk.os_type = "Linux"
        mock_vm.tags = {"dfo-protected": "true"}  # Should be blocked normally

        mock_compute.return_value.virtual_machines.get.return_value = mock_vm

        # Mock database
        mock_db_instance = Mock()
        mock_db.return_value.get_connection.return_value = mock_db_instance

        # Mock logger
        mock_logger_instance = Mock()
        mock_logger_instance.create_log_entry.return_value = "act-999"
        mock_logger.return_value = mock_logger_instance

        # Execute with no_validation
        manager = DirectExecutionManager()
        request = DirectExecutionRequest(
            resource_type="vm",
            resource_name="test-vm",
            action="stop",
            resource_group="test-rg",
            dry_run=True,
            yes=True,
            no_validation=True
        )

        result = manager.execute(request)

        # Should succeed despite protected tag
        assert result.success is True


class TestExecutionResult:
    """Tests for ExecutionResult dataclass."""

    def test_execution_result_success(self):
        """Test successful ExecutionResult."""
        result = ExecutionResult(
            success=True,
            action_id="act-123",
            message="VM stopped successfully",
            duration_seconds=12.5,
            pre_state={"power_state": "running"},
            post_state={"power_state": "stopped"}
        )

        assert result.success is True
        assert result.action_id == "act-123"
        assert result.duration_seconds == 12.5
        assert result.pre_state["power_state"] == "running"
        assert result.post_state["power_state"] == "stopped"
        assert result.errors is None

    def test_execution_result_failure(self):
        """Test failed ExecutionResult."""
        result = ExecutionResult(
            success=False,
            action_id="act-456",
            message="Execution failed",
            duration_seconds=5.2,
            errors=["Azure error", "Network timeout"]
        )

        assert result.success is False
        assert len(result.errors) == 2
        assert "Azure error" in result.errors
