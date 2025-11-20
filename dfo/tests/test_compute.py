"""Tests for Azure compute provider."""
from unittest.mock import Mock

# Internal
from dfo.providers.azure.compute import list_vms, stop_vm, deallocate_vm


def test_list_vms_stub():
    """Test list_vms stub returns empty list."""
    mock_client = Mock()
    result = list_vms(mock_client)
    assert result == []


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
