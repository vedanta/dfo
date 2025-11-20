"""Tests for Azure client factory."""
import pytest
from unittest.mock import Mock, patch

# Internal
from dfo.providers.azure.client import (
    get_compute_client,
    get_monitor_client,
    reset_clients
)
from dfo.core.config import reset_settings
from dfo.core.auth import reset_credential


@pytest.fixture(autouse=True)
def reset_all():
    """Reset all singletons before each test."""
    reset_clients()
    reset_credential()
    reset_settings()
    yield
    reset_clients()
    reset_credential()
    reset_settings()


@pytest.fixture
def mock_env(monkeypatch):
    """Set up mock Azure environment variables."""
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-subscription")


@pytest.fixture
def mock_credential():
    """Create a mock credential."""
    cred = Mock()
    cred.get_token.return_value = Mock(token="test-token")
    return cred


def test_get_compute_client_creates_new(mock_env, mock_credential):
    """Test that get_compute_client creates a new client."""
    with patch('dfo.providers.azure.client.ComputeManagementClient') as mock_compute:
        mock_client = Mock()
        mock_compute.return_value = mock_client

        client = get_compute_client("sub-123", credential=mock_credential)

        assert client is mock_client
        mock_compute.assert_called_once_with(
            credential=mock_credential,
            subscription_id="sub-123"
        )


def test_get_compute_client_returns_cached(mock_env, mock_credential):
    """Test that get_compute_client returns cached instance."""
    with patch('dfo.providers.azure.client.ComputeManagementClient') as mock_compute:
        mock_client = Mock()
        mock_compute.return_value = mock_client

        client1 = get_compute_client("sub-123", credential=mock_credential)
        client2 = get_compute_client("sub-123", credential=mock_credential)

        assert client1 is client2
        # Should only create once
        assert mock_compute.call_count == 1


def test_get_compute_client_different_subscriptions(mock_env, mock_credential):
    """Test that different subscriptions get different clients."""
    with patch('dfo.providers.azure.client.ComputeManagementClient') as mock_compute:
        mock_client1 = Mock()
        mock_client2 = Mock()
        mock_compute.side_effect = [mock_client1, mock_client2]

        client1 = get_compute_client("sub-123", credential=mock_credential)
        client2 = get_compute_client("sub-456", credential=mock_credential)

        assert client1 is not client2
        assert mock_compute.call_count == 2


def test_get_monitor_client_creates_new(mock_env, mock_credential):
    """Test that get_monitor_client creates a new client."""
    with patch('dfo.providers.azure.client.MonitorManagementClient') as mock_monitor:
        mock_client = Mock()
        mock_monitor.return_value = mock_client

        client = get_monitor_client("sub-123", credential=mock_credential)

        assert client is mock_client
        mock_monitor.assert_called_once_with(
            credential=mock_credential,
            subscription_id="sub-123"
        )


def test_get_monitor_client_returns_cached(mock_env, mock_credential):
    """Test that get_monitor_client returns cached instance."""
    with patch('dfo.providers.azure.client.MonitorManagementClient') as mock_monitor:
        mock_client = Mock()
        mock_monitor.return_value = mock_client

        client1 = get_monitor_client("sub-123", credential=mock_credential)
        client2 = get_monitor_client("sub-123", credential=mock_credential)

        assert client1 is client2
        assert mock_monitor.call_count == 1


def test_reset_clients_clears_cache(mock_env, mock_credential):
    """Test that reset_clients clears the cache."""
    with patch('dfo.providers.azure.client.ComputeManagementClient') as mock_compute, \
         patch('dfo.providers.azure.client.MonitorManagementClient') as mock_monitor:

        mock_compute.return_value = Mock()
        mock_monitor.return_value = Mock()

        get_compute_client("sub-123", credential=mock_credential)
        get_monitor_client("sub-123", credential=mock_credential)

        reset_clients()

        get_compute_client("sub-123", credential=mock_credential)
        get_monitor_client("sub-123", credential=mock_credential)

        # Should be called twice each (once before reset, once after)
        assert mock_compute.call_count == 2
        assert mock_monitor.call_count == 2


def test_get_compute_client_uses_cached_credential(mock_env):
    """Test that get_compute_client uses cached credential when none provided."""
    with patch('dfo.providers.azure.client.get_cached_credential') as mock_get_cred, \
         patch('dfo.providers.azure.client.ComputeManagementClient') as mock_compute:

        mock_cred = Mock()
        mock_cred.get_token.return_value = Mock(token="test-token")
        mock_get_cred.return_value = mock_cred
        mock_compute.return_value = Mock()

        client = get_compute_client("sub-123")

        mock_get_cred.assert_called_once()
        mock_compute.assert_called_once_with(
            credential=mock_cred,
            subscription_id="sub-123"
        )


def test_get_monitor_client_uses_cached_credential(mock_env):
    """Test that get_monitor_client uses cached credential when none provided."""
    with patch('dfo.providers.azure.client.get_cached_credential') as mock_get_cred, \
         patch('dfo.providers.azure.client.MonitorManagementClient') as mock_monitor:

        mock_cred = Mock()
        mock_cred.get_token.return_value = Mock(token="test-token")
        mock_get_cred.return_value = mock_cred
        mock_monitor.return_value = Mock()

        client = get_monitor_client("sub-123")

        mock_get_cred.assert_called_once()
        mock_monitor.assert_called_once_with(
            credential=mock_cred,
            subscription_id="sub-123"
        )
