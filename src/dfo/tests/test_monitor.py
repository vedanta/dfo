"""Tests for Azure monitor provider."""
from unittest.mock import Mock
from datetime import datetime

# Internal
from dfo.providers.azure.monitor import get_cpu_metrics


def test_get_cpu_metrics_success():
    """Test successful CPU metrics retrieval."""
    mock_client = Mock()

    # Mock metric data
    mock_data1 = Mock()
    mock_data1.time_stamp = datetime(2025, 1, 1, 0, 0, 0)
    mock_data1.average = 5.5
    mock_data1.minimum = 2.0
    mock_data1.maximum = 10.0

    mock_data2 = Mock()
    mock_data2.time_stamp = datetime(2025, 1, 1, 1, 0, 0)
    mock_data2.average = 3.2
    mock_data2.minimum = 1.5
    mock_data2.maximum = 6.0

    mock_timeseries = Mock()
    mock_timeseries.data = [mock_data1, mock_data2]

    mock_metric = Mock()
    mock_metric.timeseries = [mock_timeseries]

    mock_result = Mock()
    mock_result.value = [mock_metric]

    mock_client.metrics.list.return_value = mock_result

    metrics = get_cpu_metrics(
        mock_client,
        "/subscriptions/xxx/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1",
        days=14
    )

    assert len(metrics) == 2
    assert metrics[0]["average"] == 5.5
    assert metrics[0]["minimum"] == 2.0
    assert metrics[0]["maximum"] == 10.0
    assert "timestamp" in metrics[0]
    assert metrics[1]["average"] == 3.2


def test_get_cpu_metrics_null_data():
    """Test metrics retrieval filters null values."""
    mock_client = Mock()

    # Mock data with nulls
    mock_data_null = Mock()
    mock_data_null.average = None  # Null average

    mock_data_valid = Mock()
    mock_data_valid.time_stamp = datetime(2025, 1, 1, 0, 0, 0)
    mock_data_valid.average = 5.5
    mock_data_valid.minimum = None  # Null min is ok
    mock_data_valid.maximum = None  # Null max is ok

    mock_timeseries = Mock()
    mock_timeseries.data = [mock_data_null, mock_data_valid]

    mock_metric = Mock()
    mock_metric.timeseries = [mock_timeseries]

    mock_result = Mock()
    mock_result.value = [mock_metric]

    mock_client.metrics.list.return_value = mock_result

    metrics = get_cpu_metrics(
        mock_client,
        "/subscriptions/xxx/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1",
        days=7
    )

    # Should only return valid data point
    assert len(metrics) == 1
    assert metrics[0]["average"] == 5.5


def test_get_cpu_metrics_default_days():
    """Test metrics retrieval with default days parameter."""
    mock_client = Mock()

    mock_data = Mock()
    mock_data.time_stamp = datetime(2025, 1, 1, 0, 0, 0)
    mock_data.average = 5.5
    mock_data.minimum = 2.0
    mock_data.maximum = 10.0

    mock_timeseries = Mock()
    mock_timeseries.data = [mock_data]

    mock_metric = Mock()
    mock_metric.timeseries = [mock_timeseries]

    mock_result = Mock()
    mock_result.value = [mock_metric]

    mock_client.metrics.list.return_value = mock_result

    # Use default days (14)
    metrics = get_cpu_metrics(
        mock_client,
        "/subscriptions/xxx/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1"
    )

    assert len(metrics) == 1
    assert metrics[0]["average"] == 5.5


def test_get_cpu_metrics_empty_result():
    """Test metrics retrieval with no data."""
    mock_client = Mock()

    mock_result = Mock()
    mock_result.value = []

    mock_client.metrics.list.return_value = mock_result

    metrics = get_cpu_metrics(
        mock_client,
        "/subscriptions/xxx/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1",
        days=7
    )

    assert len(metrics) == 0


def test_get_cpu_metrics_iso_timestamp():
    """Test that timestamps are in ISO format."""
    mock_client = Mock()

    mock_data = Mock()
    mock_data.time_stamp = datetime(2025, 1, 15, 14, 30, 0)
    mock_data.average = 5.5
    mock_data.minimum = 2.0
    mock_data.maximum = 10.0

    mock_timeseries = Mock()
    mock_timeseries.data = [mock_data]

    mock_metric = Mock()
    mock_metric.timeseries = [mock_timeseries]

    mock_result = Mock()
    mock_result.value = [mock_metric]

    mock_client.metrics.list.return_value = mock_result

    metrics = get_cpu_metrics(
        mock_client,
        "/subscriptions/xxx/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1",
        days=7
    )

    # Verify timestamp is ISO format string
    assert isinstance(metrics[0]["timestamp"], str)
    assert "2025-01-15" in metrics[0]["timestamp"]
