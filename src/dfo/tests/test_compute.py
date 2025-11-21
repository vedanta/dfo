"""Tests for Azure compute provider."""
from unittest.mock import Mock

# Internal
from dfo.providers.azure.compute import list_vms, stop_vm, deallocate_vm


def test_list_vms_success():
    """Test successful VM listing."""
    mock_client = Mock()

    # Create mock VM
    mock_vm = Mock()
    mock_vm.id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1"
    mock_vm.name = "vm1"
    mock_vm.location = "eastus"
    mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
    mock_vm.tags = {"env": "prod"}
    mock_vm.priority = "Regular"
    mock_vm.storage_profile.os_disk.os_type = "Linux"

    # Mock instance view
    mock_instance_view = Mock()
    mock_status = Mock()
    mock_status.code = "PowerState/running"
    mock_instance_view.statuses = [mock_status]

    mock_client.virtual_machines.list_all.return_value = [mock_vm]
    mock_client.virtual_machines.instance_view.return_value = mock_instance_view

    vms = list_vms(mock_client)

    assert len(vms) == 1
    assert vms[0]["name"] == "vm1"
    assert vms[0]["resource_group"] == "rg1"
    assert vms[0]["location"] == "eastus"
    assert vms[0]["size"] == "Standard_D2s_v3"
    assert vms[0]["power_state"] == "running"
    assert vms[0]["os_type"] == "Linux"
    assert vms[0]["priority"] == "Regular"
    assert vms[0]["tags"] == {"env": "prod"}


def test_list_vms_no_tags():
    """Test VM listing when VM has no tags."""
    mock_client = Mock()

    mock_vm = Mock()
    mock_vm.id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1"
    mock_vm.name = "vm1"
    mock_vm.location = "eastus"
    mock_vm.hardware_profile.vm_size = "Standard_B2s"
    mock_vm.tags = None  # No tags
    mock_vm.priority = "Regular"
    mock_vm.storage_profile.os_disk.os_type = "Windows"

    mock_instance_view = Mock()
    mock_instance_view.statuses = []  # No power state

    mock_client.virtual_machines.list_all.return_value = [mock_vm]
    mock_client.virtual_machines.instance_view.return_value = mock_instance_view

    vms = list_vms(mock_client)

    assert len(vms) == 1
    assert vms[0]["tags"] == {}
    assert vms[0]["power_state"] == "unknown"
    assert vms[0]["os_type"] == "Windows"
    assert vms[0]["priority"] == "Regular"


def test_list_vms_multiple_states():
    """Test extracting different power states."""
    mock_client = Mock()

    mock_vm = Mock()
    mock_vm.id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1"
    mock_vm.name = "vm1"
    mock_vm.location = "eastus"
    mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
    mock_vm.tags = {}
    mock_vm.priority = "Regular"
    mock_vm.storage_profile.os_disk.os_type = "Linux"

    # Test different power states
    for power_state in ["running", "stopped", "deallocated"]:
        mock_instance_view = Mock()
        mock_status = Mock()
        mock_status.code = f"PowerState/{power_state}"
        mock_instance_view.statuses = [mock_status]

        mock_client.virtual_machines.list_all.return_value = [mock_vm]
        mock_client.virtual_machines.instance_view.return_value = mock_instance_view

        vms = list_vms(mock_client)
        assert vms[0]["power_state"] == power_state


def test_list_vms_instance_view_failure():
    """Test VM listing when instance view fails."""
    mock_client = Mock()

    mock_vm = Mock()
    mock_vm.id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1"
    mock_vm.name = "vm1"
    mock_vm.location = "eastus"
    mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
    mock_vm.tags = {}
    mock_vm.priority = "Regular"
    mock_vm.storage_profile.os_disk.os_type = "Linux"

    mock_client.virtual_machines.list_all.return_value = [mock_vm]
    mock_client.virtual_machines.instance_view.side_effect = Exception("API error")

    vms = list_vms(mock_client)

    # Should still return VM with unknown power state
    assert len(vms) == 1
    assert vms[0]["power_state"] == "unknown"
    assert vms[0]["os_type"] == "Linux"
    assert vms[0]["priority"] == "Regular"


def test_list_vms_missing_os_type():
    """Test VM listing when storage_profile is None."""
    mock_client = Mock()

    mock_vm = Mock()
    mock_vm.id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1"
    mock_vm.name = "vm1"
    mock_vm.location = "eastus"
    mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
    mock_vm.tags = {}
    mock_vm.priority = "Regular"
    mock_vm.storage_profile = None  # Missing storage profile

    mock_instance_view = Mock()
    mock_status = Mock()
    mock_status.code = "PowerState/running"
    mock_instance_view.statuses = [mock_status]

    mock_client.virtual_machines.list_all.return_value = [mock_vm]
    mock_client.virtual_machines.instance_view.return_value = mock_instance_view

    vms = list_vms(mock_client)

    # Should still return VM with None os_type
    assert len(vms) == 1
    assert vms[0]["os_type"] is None
    assert vms[0]["priority"] == "Regular"


def test_list_vms_spot_priority():
    """Test VM listing with Spot priority."""
    mock_client = Mock()

    mock_vm = Mock()
    mock_vm.id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1"
    mock_vm.name = "spot-vm1"
    mock_vm.location = "eastus"
    mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"
    mock_vm.tags = {}
    mock_vm.priority = "Spot"
    mock_vm.storage_profile.os_disk.os_type = "Linux"

    mock_instance_view = Mock()
    mock_status = Mock()
    mock_status.code = "PowerState/running"
    mock_instance_view.statuses = [mock_status]

    mock_client.virtual_machines.list_all.return_value = [mock_vm]
    mock_client.virtual_machines.instance_view.return_value = mock_instance_view

    vms = list_vms(mock_client)

    assert len(vms) == 1
    assert vms[0]["priority"] == "Spot"
    assert vms[0]["os_type"] == "Linux"


def test_list_vms_empty_subscription():
    """Test VM listing with no VMs."""
    mock_client = Mock()
    mock_client.virtual_machines.list_all.return_value = []

    vms = list_vms(mock_client)

    assert len(vms) == 0


def test_stop_vm_stub():
    """Test stop_vm stub returns success message."""
    mock_client = Mock()
    result = stop_vm(mock_client, "test-rg", "test-vm")
    assert result["status"] == "stub"
    assert "Not implemented" in result["message"]


def test_deallocate_vm_stub():
    """Test deallocate_vm stub returns success message."""
    mock_client = Mock()
    result = deallocate_vm(mock_client, "test-rg", "test-vm")
    assert result["status"] == "stub"
    assert "Not implemented" in result["message"]
