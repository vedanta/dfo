"""Tests for Azure authentication layer."""
import pytest
from unittest.mock import Mock, patch
from azure.core.exceptions import ClientAuthenticationError

# Internal
from dfo.core.auth import (
    get_azure_credential,
    get_cached_credential,
    reset_credential,
    AzureAuthError,
    _validate_credential
)
from dfo.core.config import reset_settings


@pytest.fixture(autouse=True)
def reset_auth():
    """Reset auth singleton before each test."""
    reset_credential()
    reset_settings()
    yield
    reset_credential()
    reset_settings()


@pytest.fixture
def mock_env(monkeypatch):
    """Set up mock Azure environment variables."""
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant-id")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-subscription")


def test_get_credential_with_default_credential(mock_env):
    """Test successful authentication with DefaultAzureCredential."""
    with patch('dfo.core.auth.DefaultAzureCredential') as mock_default:
        mock_cred = Mock()
        mock_cred.get_token.return_value = Mock(token="test-token")
        mock_default.return_value = mock_cred

        credential = get_azure_credential()

        assert credential is not None
        mock_default.assert_called_once()
        mock_cred.get_token.assert_called_once()


def test_get_credential_fallback_to_service_principal(mock_env):
    """Test fallback to ClientSecretCredential when DefaultAzureCredential fails."""
    with patch('dfo.core.auth.DefaultAzureCredential') as mock_default, \
         patch('dfo.core.auth.ClientSecretCredential') as mock_sp:

        # Make DefaultAzureCredential fail
        mock_default.return_value.get_token.side_effect = ClientAuthenticationError("Failed")

        # Make ClientSecretCredential succeed
        mock_cred = Mock()
        mock_cred.get_token.return_value = Mock(token="test-token")
        mock_sp.return_value = mock_cred

        credential = get_azure_credential()

        assert credential is not None
        mock_sp.assert_called_once_with(
            tenant_id="test-tenant-id",
            client_id="test-client-id",
            client_secret="test-secret"
        )


def test_get_credential_both_methods_fail(mock_env):
    """Test that AzureAuthError is raised when both auth methods fail."""
    with patch('dfo.core.auth.DefaultAzureCredential') as mock_default, \
         patch('dfo.core.auth.ClientSecretCredential') as mock_sp:

        # Make both fail
        mock_default.return_value.get_token.side_effect = ClientAuthenticationError("Default failed")
        mock_sp.return_value.get_token.side_effect = ClientAuthenticationError("SP failed")

        with pytest.raises(AzureAuthError) as exc_info:
            get_azure_credential()

        assert "Azure authentication failed" in str(exc_info.value)
        assert "AZURE_TENANT_ID" in str(exc_info.value)


def test_validate_credential_success():
    """Test credential validation with valid credential."""
    mock_cred = Mock()
    mock_cred.get_token.return_value = Mock(token="valid-token")

    # Should not raise
    _validate_credential(mock_cred)

    mock_cred.get_token.assert_called_once_with(
        "https://management.azure.com/.default"
    )


def test_validate_credential_failure():
    """Test credential validation with invalid credential."""
    mock_cred = Mock()
    mock_cred.get_token.side_effect = ClientAuthenticationError("Invalid")

    with pytest.raises(ClientAuthenticationError):
        _validate_credential(mock_cred)


def test_cached_credential_singleton(mock_env):
    """Test that cached credential returns same instance."""
    with patch('dfo.core.auth.DefaultAzureCredential') as mock_default:
        mock_cred = Mock()
        mock_cred.get_token.return_value = Mock(token="test-token")
        mock_default.return_value = mock_cred

        cred1 = get_cached_credential()
        cred2 = get_cached_credential()

        assert cred1 is cred2
        # DefaultAzureCredential should only be called once
        assert mock_default.call_count == 1


def test_reset_credential(mock_env):
    """Test that reset_credential clears the singleton."""
    with patch('dfo.core.auth.DefaultAzureCredential') as mock_default:
        mock_cred1 = Mock()
        mock_cred1.get_token.return_value = Mock(token="test-token")
        mock_cred2 = Mock()
        mock_cred2.get_token.return_value = Mock(token="test-token")
        mock_default.side_effect = [mock_cred1, mock_cred2]

        cred1 = get_cached_credential()
        reset_credential()
        cred2 = get_cached_credential()

        assert cred1 is not cred2
        assert mock_default.call_count == 2


def test_get_credential_validates_token_scope(mock_env):
    """Test that credential validation uses correct scope."""
    with patch('dfo.core.auth.DefaultAzureCredential') as mock_default:
        mock_cred = Mock()
        mock_cred.get_token.return_value = Mock(token="test-token")
        mock_default.return_value = mock_cred

        get_azure_credential()

        # Verify the correct scope was used for validation
        mock_cred.get_token.assert_called_with(
            "https://management.azure.com/.default"
        )
