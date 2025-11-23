"""Tests for VM discovery layer."""
import pytest
from unittest.mock import Mock, patch, ANY
from datetime import datetime

# Internal
from dfo.discover.vms import discover_vms
from dfo.core.models import VMInventory
from dfo.core.config import reset_settings
from dfo.rules import reset_rule_engine


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons before each test."""
    reset_settings()
    reset_rule_engine()
    yield
    reset_settings()
    reset_rule_engine()


@pytest.fixture
def mock_env(monkeypatch):
    """Set up mock environment."""
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-sub")


@pytest.fixture
def mock_vms():
    """Sample VM data from Azure."""
    return [
        {
            "vm_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "resource_group": "rg1",
            "location": "eastus",
            "size": "Standard_D2s_v3",
            "power_state": "running",
            "tags": {"env": "prod"}
        },
        {
            "vm_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm2",
            "name": "vm2",
            "resource_group": "rg1",
            "location": "eastus",
            "size": "Standard_B2s",
            "power_state": "stopped",
            "tags": {}
        }
    ]


@pytest.fixture
def mock_metrics():
    """Sample CPU metrics."""
    return [
        {"timestamp": "2025-01-01T00:00:00Z", "average": 2.5, "minimum": 1.0, "maximum": 5.0},
        {"timestamp": "2025-01-01T01:00:00Z", "average": 3.2, "minimum": 2.0, "maximum": 6.0},
        {"timestamp": "2025-01-01T02:00:00Z", "average": 2.8, "minimum": 1.5, "maximum": 4.5}
    ]


def test_discover_vms_success(mock_env, mock_vms, mock_metrics):
    """Test successful VM discovery."""
    with patch('dfo.discover.vms.list_vms') as mock_list, \
         patch('dfo.discover.vms.get_cpu_metrics') as mock_metrics_fn, \
         patch('dfo.discover.vms.get_cached_credential') as mock_cred, \
         patch('dfo.discover.vms.get_compute_client') as mock_compute, \
         patch('dfo.discover.vms.get_monitor_client') as mock_monitor, \
         patch('dfo.discover.vms.get_db') as mock_db:

        mock_list.return_value = mock_vms
        mock_metrics_fn.return_value = mock_metrics
        mock_cred.return_value = Mock()
        mock_compute.return_value = Mock()
        mock_monitor.return_value = Mock()

        # Mock database manager
        mock_db_manager = Mock()
        mock_db.return_value = mock_db_manager

        inventory = discover_vms(subscription_id="test-sub", refresh=True)

        assert len(inventory) == 2
        assert inventory[0].name == "vm1"
        assert inventory[0].resource_group == "rg1"
        assert len(inventory[0].cpu_timeseries) == 3
        assert inventory[0].tags == {"env": "prod"}

        # Verify clear_table was called (refresh=True)
        mock_db_manager.clear_table.assert_called_once_with("vm_inventory")

        # Verify insert_records was called
        mock_db_manager.insert_records.assert_called_once()


def test_discover_vms_uses_rule_period(mock_env, mock_vms, mock_metrics, monkeypatch):
    """Test that discovery uses rule period for metric collection."""
    # Explicitly set period to 7 days for this test
    monkeypatch.setenv("DFO_IDLE_DAYS", "7")
    reset_settings()
    reset_rule_engine()

    with patch('dfo.discover.vms.list_vms') as mock_list, \
         patch('dfo.discover.vms.get_cpu_metrics') as mock_metrics_fn, \
         patch('dfo.discover.vms.get_cached_credential') as mock_cred, \
         patch('dfo.discover.vms.get_compute_client') as mock_compute, \
         patch('dfo.discover.vms.get_monitor_client') as mock_monitor, \
         patch('dfo.discover.vms.get_db') as mock_db:

        mock_list.return_value = mock_vms
        mock_metrics_fn.return_value = mock_metrics
        mock_cred.return_value = Mock()
        mock_compute.return_value = Mock()
        mock_monitor.return_value = Mock()
        mock_db.return_value = Mock()

        discover_vms(subscription_id="test-sub", refresh=True)

        # Should call get_cpu_metrics with days=7 (from env override)
        assert mock_metrics_fn.call_count == 2  # Called for each VM
        first_call = mock_metrics_fn.call_args_list[0]
        assert first_call[1]['days'] == 7


def test_discover_vms_config_override(mock_env, mock_vms, mock_metrics, monkeypatch):
    """Test that user config overrides rule period."""
    # User overrides period to 14 days
    monkeypatch.setenv("DFO_IDLE_DAYS", "14")

    with patch('dfo.discover.vms.list_vms') as mock_list, \
         patch('dfo.discover.vms.get_cpu_metrics') as mock_metrics_fn, \
         patch('dfo.discover.vms.get_cached_credential') as mock_cred, \
         patch('dfo.discover.vms.get_compute_client') as mock_compute, \
         patch('dfo.discover.vms.get_monitor_client') as mock_monitor, \
         patch('dfo.discover.vms.get_db') as mock_db:

        # Reset singletons to pick up new config
        reset_settings()
        reset_rule_engine()

        mock_list.return_value = mock_vms
        mock_metrics_fn.return_value = mock_metrics
        mock_cred.return_value = Mock()
        mock_compute.return_value = Mock()
        mock_monitor.return_value = Mock()
        mock_db.return_value = Mock()

        discover_vms(subscription_id="test-sub", refresh=True)

        # Should use user override (14 days)
        first_call = mock_metrics_fn.call_args_list[0]
        assert first_call[1]['days'] == 14


def test_discover_vms_metrics_failure(mock_env, mock_vms):
    """Test discovery continues when metrics fail for some VMs."""
    with patch('dfo.discover.vms.list_vms') as mock_list, \
         patch('dfo.discover.vms.get_cpu_metrics') as mock_metrics_fn, \
         patch('dfo.discover.vms.get_cached_credential') as mock_cred, \
         patch('dfo.discover.vms.get_compute_client') as mock_compute, \
         patch('dfo.discover.vms.get_monitor_client') as mock_monitor, \
         patch('dfo.discover.vms.get_db') as mock_db:

        mock_list.return_value = mock_vms
        # First VM succeeds, second VM fails
        mock_metrics_fn.side_effect = [
            [{"timestamp": "2025-01-01T00:00:00Z", "average": 2.5, "minimum": 1.0, "maximum": 5.0}],
            Exception("Metrics API error")
        ]
        mock_cred.return_value = Mock()
        mock_compute.return_value = Mock()
        mock_monitor.return_value = Mock()
        mock_db.return_value = Mock()

        inventory = discover_vms(subscription_id="test-sub", refresh=True)

        # Should still return both VMs
        assert len(inventory) == 2
        # First VM has metrics
        assert len(inventory[0].cpu_timeseries) == 1
        # Second VM has no metrics (empty list)
        assert inventory[1].cpu_timeseries == []


def test_discover_vms_no_refresh(mock_env, mock_vms, mock_metrics):
    """Test discovery without clearing existing data."""
    with patch('dfo.discover.vms.list_vms') as mock_list, \
         patch('dfo.discover.vms.get_cpu_metrics') as mock_metrics_fn, \
         patch('dfo.discover.vms.get_cached_credential') as mock_cred, \
         patch('dfo.discover.vms.get_compute_client') as mock_compute, \
         patch('dfo.discover.vms.get_monitor_client') as mock_monitor, \
         patch('dfo.discover.vms.get_db') as mock_db:

        mock_list.return_value = mock_vms
        mock_metrics_fn.return_value = mock_metrics
        mock_cred.return_value = Mock()
        mock_compute.return_value = Mock()
        mock_monitor.return_value = Mock()

        mock_db_manager = Mock()
        mock_db.return_value = mock_db_manager

        discover_vms(subscription_id="test-sub", refresh=False)

        # clear_table should not be called
        mock_db_manager.clear_table.assert_not_called()


def test_discover_vms_empty_subscription(mock_env):
    """Test discovery with no VMs."""
    with patch('dfo.discover.vms.list_vms') as mock_list, \
         patch('dfo.discover.vms.get_cached_credential') as mock_cred, \
         patch('dfo.discover.vms.get_compute_client') as mock_compute, \
         patch('dfo.discover.vms.get_monitor_client') as mock_monitor, \
         patch('dfo.discover.vms.get_db') as mock_db:

        mock_list.return_value = []  # No VMs
        mock_cred.return_value = Mock()
        mock_compute.return_value = Mock()
        mock_monitor.return_value = Mock()

        mock_db_manager = Mock()
        mock_db.return_value = mock_db_manager

        inventory = discover_vms(subscription_id="test-sub", refresh=True)

        assert len(inventory) == 0
        # insert_records should not be called with empty list
        mock_db_manager.insert_records.assert_not_called()


def test_discover_vms_with_custom_subscription(mock_env, mock_vms, mock_metrics):
    """Test discovery with custom subscription ID."""
    custom_sub = "custom-sub-id"

    with patch('dfo.discover.vms.list_vms') as mock_list, \
         patch('dfo.discover.vms.get_cpu_metrics') as mock_metrics_fn, \
         patch('dfo.discover.vms.get_cached_credential') as mock_cred, \
         patch('dfo.discover.vms.get_compute_client') as mock_compute, \
         patch('dfo.discover.vms.get_monitor_client') as mock_monitor, \
         patch('dfo.discover.vms.get_db') as mock_db:

        mock_list.return_value = mock_vms
        mock_metrics_fn.return_value = mock_metrics
        mock_cred.return_value = Mock()
        mock_compute.return_value = Mock()
        mock_monitor.return_value = Mock()
        mock_db.return_value = Mock()

        discover_vms(subscription_id=custom_sub, refresh=True)

        # Verify clients were created with custom subscription
        mock_compute.assert_called_with(custom_sub, ANY)
        mock_monitor.assert_called_with(custom_sub, ANY)
