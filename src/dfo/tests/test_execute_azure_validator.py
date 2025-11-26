"""Tests for Azure-specific resource validation."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from azure.core.exceptions import ResourceNotFoundError, HttpResponseError

from dfo.execute.azure_validator import (
    AzureResourceValidator,
    validate_azure_vm_action,
)
from dfo.execute.models import (
    ActionType,
    PlanAction,
    ValidationStatus,
)


@pytest.fixture
def azure_validator():
    """Create AzureResourceValidator instance with mocked clients."""
    with patch('dfo.execute.azure_validator.get_azure_credential'):
        with patch('dfo.execute.azure_validator.get_settings'):
            validator = AzureResourceValidator()
            return validator


@pytest.fixture
def sample_vm_action():
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


class TestAzureVMValidation:
    """Tests for Azure VM action validation."""

    @patch('dfo.execute.azure_validator.get_compute_client')
    def test_validate_vm_action_success(self, mock_get_client, azure_validator, sample_vm_action):
        """Test successful VM validation."""
        # Mock compute client
        mock_vm = Mock()
        mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm.location = "eastus"
        mock_vm.tags = {}
        mock_vm.instance_view.statuses = [
            Mock(code="PowerState/running")
        ]
        mock_vm.storage_profile.os_disk = Mock(name="os-disk")
        mock_vm.storage_profile.data_disks = []
        mock_vm.network_profile.network_interfaces = []

        mock_client = Mock()
        mock_client.virtual_machines.get.return_value = mock_vm
        mock_get_client.return_value = mock_client

        result = azure_validator.validate_vm_action(sample_vm_action)

        assert result.status == ValidationStatus.SUCCESS
        assert result.resource_exists is True
        assert result.permissions_ok is True
        assert "current_power_state" in result.details
        assert result.details["current_power_state"] == "running"

    @patch('dfo.execute.azure_validator.get_compute_client')
    def test_validate_vm_action_not_found(self, mock_get_client, azure_validator, sample_vm_action):
        """Test VM not found."""
        mock_client = Mock()
        mock_client.virtual_machines.get.side_effect = ResourceNotFoundError("VM not found")
        mock_get_client.return_value = mock_client

        result = azure_validator.validate_vm_action(sample_vm_action)

        assert result.status == ValidationStatus.ERROR
        assert result.resource_exists is False
        assert "not found" in result.errors[0].lower()

    @patch('dfo.execute.azure_validator.get_compute_client')
    def test_validate_vm_action_protected_tag(self, mock_get_client, azure_validator, sample_vm_action):
        """Test VM with protection tag."""
        mock_vm = Mock()
        mock_vm.tags = {"dfo-protected": "true"}
        mock_vm.instance_view.statuses = [Mock(code="PowerState/running")]
        mock_vm.storage_profile.os_disk = Mock(name="os-disk")
        mock_vm.storage_profile.data_disks = []
        mock_vm.network_profile.network_interfaces = []

        mock_client = Mock()
        mock_client.virtual_machines.get.return_value = mock_vm
        mock_get_client.return_value = mock_client

        result = azure_validator.validate_vm_action(sample_vm_action)

        assert result.status == ValidationStatus.ERROR
        assert any("protection tag" in e.lower() for e in result.errors)

    @patch('dfo.execute.azure_validator.get_compute_client')
    def test_validate_delete_action_warning(self, mock_get_client, azure_validator):
        """Test DELETE action generates warning."""
        action = PlanAction(
            action_id="action-test-1",
            plan_id="plan-test-1",
            resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/test-vm",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.DELETE,
            estimated_monthly_savings=100.0,
        )

        mock_vm = Mock()
        mock_vm.tags = {}
        mock_vm.instance_view.statuses = [Mock(code="PowerState/running")]
        mock_vm.storage_profile.os_disk = Mock(name="os-disk")
        mock_vm.storage_profile.data_disks = []
        mock_vm.network_profile.network_interfaces = []
        mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm.location = "eastus"

        mock_client = Mock()
        mock_client.virtual_machines.get.return_value = mock_vm
        mock_get_client.return_value = mock_client

        result = azure_validator.validate_vm_action(action)

        assert result.status == ValidationStatus.WARNING
        assert any("IRREVERSIBLE" in w for w in result.warnings)

    @patch('dfo.execute.azure_validator.get_compute_client')
    def test_validate_stop_already_stopped(self, mock_get_client, azure_validator):
        """Test STOP action on already stopped VM."""
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

        mock_vm = Mock()
        mock_vm.tags = {}
        mock_vm.instance_view.statuses = [Mock(code="PowerState/stopped")]
        mock_vm.storage_profile.os_disk = Mock(name="os-disk")
        mock_vm.storage_profile.data_disks = []
        mock_vm.network_profile.network_interfaces = []
        mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm.location = "eastus"

        mock_client = Mock()
        mock_client.virtual_machines.get.return_value = mock_vm
        mock_get_client.return_value = mock_client

        result = azure_validator.validate_vm_action(action)

        assert result.status == ValidationStatus.WARNING
        assert any("already stopped" in w.lower() for w in result.warnings)

    @patch('dfo.execute.azure_validator.get_compute_client')
    def test_validate_downsize_missing_parameter(self, mock_get_client, azure_validator):
        """Test DOWNSIZE without new_size parameter."""
        action = PlanAction(
            action_id="action-test-1",
            plan_id="plan-test-1",
            resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/test-vm",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="low-cpu",
            action_type=ActionType.DOWNSIZE,
            estimated_monthly_savings=100.0,
            action_params={},
        )

        mock_vm = Mock()
        mock_vm.tags = {}
        mock_vm.instance_view.statuses = [Mock(code="PowerState/running")]
        mock_vm.storage_profile.os_disk = Mock(name="os-disk")
        mock_vm.storage_profile.data_disks = []
        mock_vm.network_profile.network_interfaces = []
        mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm.location = "eastus"

        mock_client = Mock()
        mock_client.virtual_machines.get.return_value = mock_vm
        mock_get_client.return_value = mock_client

        result = azure_validator.validate_vm_action(action)

        assert result.status == ValidationStatus.ERROR
        assert any("new_size" in e.lower() for e in result.errors)

    @patch('dfo.execute.azure_validator.get_compute_client')
    def test_validate_vm_with_data_disks(self, mock_get_client, azure_validator):
        """Test validation includes disk dependencies."""
        action = PlanAction(
            action_id="action-test-1",
            plan_id="plan-test-1",
            resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/test-vm",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.DELETE,
            estimated_monthly_savings=100.0,
        )

        mock_vm = Mock()
        mock_vm.tags = {}
        mock_vm.instance_view.statuses = [Mock(code="PowerState/running")]
        mock_vm.storage_profile.os_disk = Mock(name="os-disk")
        mock_vm.storage_profile.data_disks = [
            Mock(name="data-disk-1"),
            Mock(name="data-disk-2"),
        ]
        mock_vm.network_profile.network_interfaces = []
        mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
        mock_vm.location = "eastus"

        mock_client = Mock()
        mock_client.virtual_machines.get.return_value = mock_vm
        mock_get_client.return_value = mock_client

        result = azure_validator.validate_vm_action(action)

        assert len(result.dependencies) > 0
        assert any("OS Disk" in d for d in result.dependencies)
        assert any("Data Disk" in d for d in result.dependencies)
        assert any("2 attached data disk" in w for w in result.warnings)

    def test_validate_vm_invalid_resource_id(self, azure_validator):
        """Test validation with invalid resource ID format."""
        action = PlanAction(
            action_id="action-test-1",
            plan_id="plan-test-1",
            resource_id="/invalid/resource/id",
            resource_name="test-vm",
            resource_type="vm",
            analysis_type="idle-vms",
            action_type=ActionType.STOP,
            estimated_monthly_savings=100.0,
        )

        result = azure_validator.validate_vm_action(action)

        assert result.status == ValidationStatus.ERROR
        assert any("Invalid resource ID" in e for e in result.errors)

    @patch('dfo.execute.azure_validator.get_compute_client')
    def test_validate_vm_generic_exception(self, mock_get_client, azure_validator, sample_vm_action):
        """Test validation handles generic exceptions."""
        mock_client = Mock()
        mock_client.virtual_machines.get.side_effect = Exception("Unexpected error")
        mock_get_client.return_value = mock_client

        result = azure_validator.validate_vm_action(sample_vm_action)

        assert result.status == ValidationStatus.ERROR
        assert len(result.errors) > 0

    def test_validate_azure_vm_action_convenience_function(self, sample_vm_action):
        """Test convenience function wraps validator correctly."""
        with patch.object(AzureResourceValidator, 'validate_vm_action') as mock_validate:
            mock_validate.return_value = Mock(status=ValidationStatus.SUCCESS)

            result = validate_azure_vm_action(sample_vm_action)

            mock_validate.assert_called_once_with(sample_vm_action)
            assert result.status == ValidationStatus.SUCCESS


class TestPowerStateExtraction:
    """Tests for power state extraction logic."""

    def test_get_power_state_running(self, azure_validator):
        """Test extracting running power state."""
        mock_vm = Mock()
        mock_vm.instance_view.statuses = [
            Mock(code="ProvisioningState/succeeded"),
            Mock(code="PowerState/running"),
        ]

        power_state = azure_validator._get_power_state(mock_vm)

        assert power_state == "running"

    def test_get_power_state_stopped(self, azure_validator):
        """Test extracting stopped power state."""
        mock_vm = Mock()
        mock_vm.instance_view.statuses = [
            Mock(code="PowerState/stopped"),
        ]

        power_state = azure_validator._get_power_state(mock_vm)

        assert power_state == "stopped"

    def test_get_power_state_deallocated(self, azure_validator):
        """Test extracting deallocated power state."""
        mock_vm = Mock()
        mock_vm.instance_view.statuses = [
            Mock(code="PowerState/deallocated"),
        ]

        power_state = azure_validator._get_power_state(mock_vm)

        assert power_state == "deallocated"

    def test_get_power_state_no_instance_view(self, azure_validator):
        """Test power state with no instance view."""
        mock_vm = Mock()
        mock_vm.instance_view = None

        power_state = azure_validator._get_power_state(mock_vm)

        assert power_state == "unknown"

    def test_get_power_state_no_statuses(self, azure_validator):
        """Test power state with no statuses."""
        mock_vm = Mock()
        mock_vm.instance_view.statuses = []

        power_state = azure_validator._get_power_state(mock_vm)

        assert power_state == "unknown"
