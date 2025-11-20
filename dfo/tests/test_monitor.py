"""Tests for Azure monitor provider."""
from unittest.mock import Mock

# Internal
from dfo.providers.azure.monitor import get_cpu_metrics


def test_get_cpu_metrics_stub():
    """Test get_cpu_metrics stub returns empty list."""
    mock_client = Mock()
    result = get_cpu_metrics(
        mock_client,
        "/subscriptions/xxx/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1",
        days=14
    )
    assert result == []


def test_get_cpu_metrics_with_default_days():
    """Test get_cpu_metrics stub with default days parameter."""
    mock_client = Mock()
    result = get_cpu_metrics(
        mock_client,
        "/subscriptions/xxx/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1"
    )
    assert result == []
