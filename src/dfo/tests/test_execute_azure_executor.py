"""Tests for Azure VM action executor."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from azure.core.exceptions import ResourceNotFoundError, HttpResponseError

from dfo.execute.azure_executor import AzureVMExecutor, ExecutionResult
from dfo.execute.models import ActionType, PlanAction


@pytest.fixture
def azure_executor():
    """Create AzureVMExecutor with mocked Azure clients."""
    with patch('dfo.execute.azure_executor.get_azure_credential'):
        with patch('dfo.execute.azure_executor.get_settings'):
            executor = AzureVMExecutor()
            return executor


@pytest.fixture
def sample_action():
    """Create sample VM action."""
    return PlanAction(
        action_id="action-test-1",
        plan_id="plan-test-1",
        resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/test-vm",
        resource_name="test-vm",
        resource_type="vm",
        analysis_type="idle-vms",
        action_type=ActionType.DEALLOCATE,
        estimated_monthly_savings=100.0,
    )


# ============================================================================
# RESOURCE ID PARSING TESTS
# ============================================================================

class TestResourceIDParsing:
    """Tests for _parse_resource_id() method."""

    def test_parse_valid_resource_id(self, azure_executor):
        """Test parsing valid Azure resource ID."""
        resource_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1"

        rg, vm_name = azure_executor._parse_resource_id(resource_id)

        assert rg == "rg1"
        assert vm_name == "vm1"

    def test_parse_invalid_resource_id(self, azure_executor):
        """Test that invalid resource ID raises error."""
        invalid_id = "/invalid/format"

        with pytest.raises(ValueError, match="Invalid resource ID format"):
            azure_executor._parse_resource_id(invalid_id)


# ============================================================================
# POWER STATE EXTRACTION TESTS
# ============================================================================

class TestPowerStateExtraction:
    """Tests for _get_power_state() method."""

    def test_get_power_state_running(self, azure_executor):
        """Test extracting running power state."""
        mock_vm = Mock()
        mock_vm.instance_view.statuses = [
            Mock(code="ProvisioningState/succeeded"),
            Mock(code="PowerState/running"),
        ]

        power_state = azure_executor._get_power_state(mock_vm)

        assert power_state == "running"

    def test_get_power_state_stopped(self, azure_executor):
        """Test extracting stopped power state."""
        mock_vm = Mock()
        mock_vm.instance_view.statuses = [
            Mock(code="PowerState/stopped"),
        ]

        power_state = azure_executor._get_power_state(mock_vm)

        assert power_state == "stopped"

    def test_get_power_state_deallocated(self, azure_executor):
        """Test extracting deallocated power state."""
        mock_vm = Mock()
        mock_vm.instance_view.statuses = [
            Mock(code="PowerState/deallocated"),
        ]

        power_state = azure_executor._get_power_state(mock_vm)

        assert power_state == "deallocated"

    def test_get_power_state_no_instance_view(self, azure_executor):
        """Test power state with no instance view."""
        mock_vm = Mock()
        mock_vm.instance_view = None

        power_state = azure_executor._get_power_state(mock_vm)

        assert power_state == "unknown"

    def test_get_power_state_no_statuses(self, azure_executor):
        """Test power state with empty statuses list."""
        mock_vm = Mock()
        mock_vm.instance_view.statuses = []

        power_state = azure_executor._get_power_state(mock_vm)

        assert power_state == "unknown"


# ============================================================================
# EXECUTE ACTION ROUTING TESTS
# ============================================================================

class TestExecuteActionRouting:
    """Tests for execute_action() method routing."""

    @patch.object(AzureVMExecutor, 'stop_vm')
    def test_route_to_stop_vm(self, mock_stop, azure_executor):
        """Test that STOP action routes to stop_vm()."""
        action = PlanAction(
            action_id="a1",
            plan_id="p1",
            resource_id="/test/vm",
            resource_name="vm",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.STOP,
            estimated_monthly_savings=100.0,
        )

        mock_stop.return_value = ExecutionResult(success=True, message="OK")

        azure_executor.execute_action(action)

        mock_stop.assert_called_once_with(action)

    @patch.object(AzureVMExecutor, 'deallocate_vm')
    def test_route_to_deallocate_vm(self, mock_deallocate, azure_executor):
        """Test that DEALLOCATE action routes to deallocate_vm()."""
        action = PlanAction(
            action_id="a1",
            plan_id="p1",
            resource_id="/test/vm",
            resource_name="vm",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.DEALLOCATE,
            estimated_monthly_savings=100.0,
        )

        mock_deallocate.return_value = ExecutionResult(success=True, message="OK")

        azure_executor.execute_action(action)

        mock_deallocate.assert_called_once_with(action)

    @patch.object(AzureVMExecutor, 'delete_vm')
    def test_route_to_delete_vm(self, mock_delete, azure_executor):
        """Test that DELETE action routes to delete_vm()."""
        action = PlanAction(
            action_id="a1",
            plan_id="p1",
            resource_id="/test/vm",
            resource_name="vm",
            resource_type="vm",
            analysis_type="stopped-vms",
            action_type=ActionType.DELETE,
            estimated_monthly_savings=100.0,
        )

        mock_delete.return_value = ExecutionResult(success=True, message="OK")

        azure_executor.execute_action(action)

        mock_delete.assert_called_once_with(action)

    @patch.object(AzureVMExecutor, 'downsize_vm')
    def test_route_to_downsize_vm(self, mock_downsize, azure_executor):
        """Test that DOWNSIZE action routes to downsize_vm()."""
        action = PlanAction(
            action_id="a1",
            plan_id="p1",
            resource_id="/test/vm",
            resource_name="vm",
            resource_type="vm",
            analysis_type="low-cpu",
            action_type=ActionType.DOWNSIZE,
            estimated_monthly_savings=100.0,
        )

        mock_downsize.return_value = ExecutionResult(success=True, message="OK")

        azure_executor.execute_action(action)

        mock_downsize.assert_called_once_with(action)

    @patch.object(AzureVMExecutor, 'start_vm')
    def test_route_to_start_vm(self, mock_start, azure_executor):
        """Test that START action routes to start_vm()."""
        action = PlanAction(
            action_id="a1",
            plan_id="p1",
            resource_id="/test/vm",
            resource_name="vm",
            resource_type="vm",
            analysis_type="rollback",
            action_type=ActionType.START,
            estimated_monthly_savings=0.0,
        )

        mock_start.return_value = ExecutionResult(success=True, message="OK")

        azure_executor.execute_action(action)

        mock_start.assert_called_once_with(action)

    # Note: Can't test unknown action type because Pydantic validates ActionType enum
    # The execute_action() method has defensive code for unknown action types,
    # but Pydantic will reject invalid enum values before that code is reached


# ============================================================================
# STOP VM TESTS
# ============================================================================

class TestStopVM:
    """Tests for stop_vm() method."""

    @patch('dfo.execute.azure_executor.get_compute_client')
    def test_stop_vm_success(self, mock_get_client, azure_executor, sample_action):
        """Test successful VM stop."""
        # Mock VM
        mock_vm = Mock()
        mock_vm.instance_view.statuses = [Mock(code="PowerState/running")]

        # Mock compute client
        mock_client = Mock()
        mock_client.virtual_machines.get.return_value = mock_vm

        mock_poller = Mock()
        mock_poller.wait.return_value = None
        mock_client.virtual_machines.begin_power_off.return_value = mock_poller

        mock_get_client.return_value = mock_client

        sample_action.action_type = ActionType.STOP

        result = azure_executor.stop_vm(sample_action)

        assert result.success is True
        assert "stopped successfully" in result.message.lower()
        assert result.details["previous_state"] == "running"
        assert result.details["new_state"] == "stopped"
        assert result.rollback_data["action_type"] == "start"
        mock_client.virtual_machines.begin_power_off.assert_called_once()

    @patch('dfo.execute.azure_executor.get_compute_client')
    def test_stop_vm_not_found(self, mock_get_client, azure_executor, sample_action):
        """Test stop VM when VM not found."""
        mock_client = Mock()
        mock_client.virtual_machines.get.side_effect = ResourceNotFoundError("VM not found")
        mock_get_client.return_value = mock_client

        sample_action.action_type = ActionType.STOP

        result = azure_executor.stop_vm(sample_action)

        assert result.success is False
        assert "not found" in result.message.lower()
        assert result.error_code == "RESOURCE_NOT_FOUND"

    @patch('dfo.execute.azure_executor.get_compute_client')
    def test_stop_vm_http_error(self, mock_get_client, azure_executor, sample_action):
        """Test stop VM with HTTP error."""
        mock_error = HttpResponseError("API error")
        mock_error.message = "API error"
        mock_error.error = Mock(code="Throttled")

        mock_vm = Mock()
        mock_vm.instance_view.statuses = [Mock(code="PowerState/running")]

        mock_client = Mock()
        mock_client.virtual_machines.get.return_value = mock_vm
        mock_client.virtual_machines.begin_power_off.side_effect = mock_error
        mock_get_client.return_value = mock_client

        sample_action.action_type = ActionType.STOP

        result = azure_executor.stop_vm(sample_action)

        assert result.success is False
        assert "Azure API error" in result.message
        assert result.error_code == "Throttled"


# ============================================================================
# DEALLOCATE VM TESTS
# ============================================================================

class TestDeallocateVM:
    """Tests for deallocate_vm() method."""

    @patch('dfo.execute.azure_executor.get_compute_client')
    def test_deallocate_vm_success(self, mock_get_client, azure_executor, sample_action):
        """Test successful VM deallocation."""
        mock_vm = Mock()
        mock_vm.instance_view.statuses = [Mock(code="PowerState/running")]

        mock_client = Mock()
        mock_client.virtual_machines.get.return_value = mock_vm

        mock_poller = Mock()
        mock_poller.wait.return_value = None
        mock_client.virtual_machines.begin_deallocate.return_value = mock_poller

        mock_get_client.return_value = mock_client

        sample_action.action_type = ActionType.DEALLOCATE

        result = azure_executor.deallocate_vm(sample_action)

        assert result.success is True
        assert "deallocated successfully" in result.message.lower()
        assert result.details["previous_state"] == "running"
        assert result.details["new_state"] == "deallocated"
        assert result.rollback_data["action_type"] == "start"
        mock_client.virtual_machines.begin_deallocate.assert_called_once()

    @patch('dfo.execute.azure_executor.get_compute_client')
    def test_deallocate_vm_already_stopped(self, mock_get_client, azure_executor, sample_action):
        """Test deallocate VM that is already stopped."""
        mock_vm = Mock()
        mock_vm.instance_view.statuses = [Mock(code="PowerState/stopped")]

        mock_client = Mock()
        mock_client.virtual_machines.get.return_value = mock_vm

        mock_poller = Mock()
        mock_poller.wait.return_value = None
        mock_client.virtual_machines.begin_deallocate.return_value = mock_poller

        mock_get_client.return_value = mock_client

        sample_action.action_type = ActionType.DEALLOCATE

        result = azure_executor.deallocate_vm(sample_action)

        assert result.success is True
        # Rollback action_type should be None if VM was not running
        assert result.rollback_data["action_type"] is None


# ============================================================================
# DELETE VM TESTS
# ============================================================================

class TestDeleteVM:
    """Tests for delete_vm() method."""

    @patch('dfo.execute.azure_executor.get_compute_client')
    def test_delete_vm_success(self, mock_get_client, azure_executor, sample_action):
        """Test successful VM deletion."""
        mock_vm = Mock()
        mock_vm.instance_view.statuses = [Mock(code="PowerState/running")]
        mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm.location = "eastus"

        mock_client = Mock()
        mock_client.virtual_machines.get.return_value = mock_vm

        mock_poller = Mock()
        mock_poller.wait.return_value = None
        mock_client.virtual_machines.begin_delete.return_value = mock_poller

        mock_get_client.return_value = mock_client

        sample_action.action_type = ActionType.DELETE

        result = azure_executor.delete_vm(sample_action)

        assert result.success is True
        assert "deleted successfully" in result.message.lower()
        assert "IRREVERSIBLE" in result.message
        assert result.details["new_state"] == "deleted"
        assert "IRREVERSIBLE" in result.rollback_data["warning"]
        mock_client.virtual_machines.begin_delete.assert_called_once()

    @patch('dfo.execute.azure_executor.get_compute_client')
    def test_delete_vm_already_deleted(self, mock_get_client, azure_executor, sample_action):
        """Test delete VM that is already deleted."""
        mock_client = Mock()
        mock_client.virtual_machines.get.side_effect = ResourceNotFoundError("VM not found")
        mock_get_client.return_value = mock_client

        sample_action.action_type = ActionType.DELETE

        result = azure_executor.delete_vm(sample_action)

        # Delete of non-existent VM should succeed (idempotent)
        assert result.success is True
        assert "may already be deleted" in result.message.lower()


# ============================================================================
# DOWNSIZE VM TESTS
# ============================================================================

class TestDownsizeVM:
    """Tests for downsize_vm() method."""

    @patch('dfo.execute.azure_executor.get_compute_client')
    def test_downsize_vm_success(self, mock_get_client, azure_executor, sample_action):
        """Test successful VM downsize."""
        mock_vm = Mock()
        mock_vm.instance_view.statuses = [Mock(code="PowerState/stopped")]
        mock_vm.hardware_profile.vm_size = "Standard_D4s_v3"

        mock_client = Mock()
        mock_client.virtual_machines.get.return_value = mock_vm

        mock_poller = Mock()
        mock_poller.wait.return_value = None
        mock_client.virtual_machines.begin_create_or_update.return_value = mock_poller

        mock_get_client.return_value = mock_client

        sample_action.action_type = ActionType.DOWNSIZE
        sample_action.action_params = {"new_size": "Standard_B2s"}

        result = azure_executor.downsize_vm(sample_action)

        assert result.success is True
        assert "resized successfully" in result.message.lower()
        assert result.details["previous_size"] == "Standard_D4s_v3"
        assert result.details["new_size"] == "Standard_B2s"
        assert result.rollback_data["original_size"] == "Standard_D4s_v3"
        assert result.rollback_data["action_type"] == "downsize"
        mock_client.virtual_machines.begin_create_or_update.assert_called_once()

    @patch('dfo.execute.azure_executor.get_compute_client')
    def test_downsize_vm_missing_parameter(self, mock_get_client, azure_executor, sample_action):
        """Test downsize without new_size parameter."""
        sample_action.action_type = ActionType.DOWNSIZE
        sample_action.action_params = {}  # Missing new_size

        result = azure_executor.downsize_vm(sample_action)

        assert result.success is False
        assert "new_size" in result.message.lower()
        assert result.error_code == "MISSING_PARAMETER"

    @patch('dfo.execute.azure_executor.get_compute_client')
    def test_downsize_vm_not_stopped(self, mock_get_client, azure_executor, sample_action):
        """Test downsize VM that is still running."""
        mock_vm = Mock()
        mock_vm.instance_view.statuses = [Mock(code="PowerState/running")]  # Not stopped
        mock_vm.hardware_profile.vm_size = "Standard_D4s_v3"

        mock_client = Mock()
        mock_client.virtual_machines.get.return_value = mock_vm
        mock_get_client.return_value = mock_client

        sample_action.action_type = ActionType.DOWNSIZE
        sample_action.action_params = {"new_size": "Standard_B2s"}

        result = azure_executor.downsize_vm(sample_action)

        assert result.success is False
        assert "must be stopped" in result.message.lower()
        assert result.error_code == "INVALID_STATE"


# ============================================================================
# START VM TESTS
# ============================================================================

class TestStartVM:
    """Tests for start_vm() method."""

    @patch('dfo.execute.azure_executor.get_compute_client')
    def test_start_vm_success(self, mock_get_client, azure_executor, sample_action):
        """Test successful VM start."""
        mock_vm = Mock()
        mock_vm.instance_view.statuses = [Mock(code="PowerState/deallocated")]

        mock_client = Mock()
        mock_client.virtual_machines.get.return_value = mock_vm

        mock_poller = Mock()
        mock_poller.wait.return_value = None
        mock_client.virtual_machines.begin_start.return_value = mock_poller

        mock_get_client.return_value = mock_client

        sample_action.action_type = ActionType.START

        result = azure_executor.start_vm(sample_action)

        assert result.success is True
        assert "started successfully" in result.message.lower()
        assert result.details["previous_state"] == "deallocated"
        assert result.details["new_state"] == "running"
        assert result.rollback_data["action_type"] == "stop"
        mock_client.virtual_machines.begin_start.assert_called_once()

    @patch('dfo.execute.azure_executor.get_compute_client')
    def test_start_vm_not_found(self, mock_get_client, azure_executor, sample_action):
        """Test start VM when VM not found."""
        mock_client = Mock()
        mock_client.virtual_machines.get.side_effect = ResourceNotFoundError("VM not found")
        mock_get_client.return_value = mock_client

        sample_action.action_type = ActionType.START

        result = azure_executor.start_vm(sample_action)

        assert result.success is False
        assert "not found" in result.message.lower()
        assert result.error_code == "RESOURCE_NOT_FOUND"


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Tests for error handling across all methods."""

    @patch.object(AzureVMExecutor, 'stop_vm')
    def test_execute_action_exception_caught(self, mock_stop, azure_executor, sample_action):
        """Test that unexpected exceptions in execute_action are caught."""
        mock_stop.side_effect = Exception("Unexpected error")

        sample_action.action_type = ActionType.STOP

        result = azure_executor.execute_action(sample_action)

        assert result.success is False
        assert "Execution failed" in result.message
        assert result.error_code == "EXECUTION_ERROR"

    @patch('dfo.execute.azure_executor.get_compute_client')
    def test_stop_vm_generic_exception(self, mock_get_client, azure_executor, sample_action):
        """Test that generic exceptions are caught in stop_vm."""
        mock_client = Mock()
        mock_client.virtual_machines.get.side_effect = Exception("Unexpected error")
        mock_get_client.return_value = mock_client

        sample_action.action_type = ActionType.STOP

        result = azure_executor.stop_vm(sample_action)

        assert result.success is False
        assert "Stop failed" in result.message
        assert result.error_code == "STOP_ERROR"
