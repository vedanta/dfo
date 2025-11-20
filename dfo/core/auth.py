"""Azure authentication layer.

This module provides centralized Azure credential management using
Azure SDK's DefaultAzureCredential with fallback to service principal.

Per CODE_STYLE.md:
- This is a core module, so NO Azure SDK calls beyond credential creation
- NO database operations
- Return credentials only; let provider layer use them
"""
from typing import Optional

# Third-party
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.core.credentials import TokenCredential
from azure.core.exceptions import ClientAuthenticationError

# Internal
from dfo.core.config import get_settings


class AzureAuthError(Exception):
    """Raised when Azure authentication fails."""
    pass


def get_azure_credential() -> TokenCredential:
    """Get Azure credential using DefaultAzureCredential.

    Authentication flow:
    1. Try DefaultAzureCredential (supports multiple methods):
       - Environment variables (AZURE_CLIENT_ID, AZURE_TENANT_ID, etc.)
       - Managed Identity (if running in Azure)
       - Azure CLI credentials (if az login is active)
       - Visual Studio Code credentials
    2. Fallback to explicit ClientSecretCredential using settings

    Returns:
        TokenCredential: Azure credential object.

    Raises:
        AzureAuthError: If authentication fails with actionable message.
    """
    settings = get_settings()

    try:
        # Try DefaultAzureCredential first (recommended approach)
        credential = DefaultAzureCredential(
            additionally_allowed_tenants=['*'],
            exclude_interactive_browser_credential=True,  # Non-interactive
            exclude_shared_token_cache_credential=True    # More predictable
        )

        # Validate credential by attempting to get a token
        # Using management scope as a test
        _validate_credential(credential)

        return credential

    except Exception as default_error:
        # Fallback to explicit service principal from env vars
        try:
            credential = ClientSecretCredential(
                tenant_id=settings.azure_tenant_id,
                client_id=settings.azure_client_id,
                client_secret=settings.azure_client_secret
            )

            _validate_credential(credential)
            return credential

        except Exception as sp_error:
            raise AzureAuthError(
                "Azure authentication failed. Please check:\n"
                "1. Environment variables are set correctly:\n"
                "   - AZURE_TENANT_ID\n"
                "   - AZURE_CLIENT_ID\n"
                "   - AZURE_CLIENT_SECRET\n"
                "   - AZURE_SUBSCRIPTION_ID\n"
                "2. Service principal has required permissions\n"
                "3. Or run 'az login' for CLI-based authentication\n"
                f"\nDefault credential error: {default_error}\n"
                f"Service principal error: {sp_error}"
            )


def _validate_credential(credential: TokenCredential) -> None:
    """Validate credential by attempting to get a token.

    Args:
        credential: The credential to validate.

    Raises:
        ClientAuthenticationError: If token acquisition fails.
    """
    # Attempt to get a token for Azure Resource Manager
    # This validates the credential without making any actual API calls
    scope = "https://management.azure.com/.default"
    credential.get_token(scope)


# Singleton instance
_credential: Optional[TokenCredential] = None


def get_cached_credential() -> TokenCredential:
    """Get or create cached Azure credential (singleton).

    Returns:
        TokenCredential: Cached credential instance.
    """
    global _credential
    if _credential is None:
        _credential = get_azure_credential()
    return _credential


def reset_credential() -> None:
    """Reset cached credential (useful for testing).

    Should not be called in production code.
    """
    global _credential
    _credential = None
