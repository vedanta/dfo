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
    """Get Azure credential using service principal or DefaultAzureCredential.

    Authentication flow:
    1. If service principal credentials are in .env, use ClientSecretCredential
       - Clean output, no noisy DefaultAzureCredential errors
       - Fastest path for configured environments
    2. Otherwise, fall back to DefaultAzureCredential:
       - Azure CLI credentials (if az login is active)
       - Managed Identity (if running in Azure)
       - Visual Studio Code credentials
       - Other Azure SDK credential methods

    Returns:
        TokenCredential: Azure credential object.

    Raises:
        AzureAuthError: If authentication fails with actionable message.
    """
    settings = get_settings()

    # Check if we have complete service principal credentials
    has_sp_creds = all([
        settings.azure_tenant_id,
        settings.azure_client_id,
        settings.azure_client_secret
    ])

    # Try service principal first if configured in .env
    if has_sp_creds:
        try:
            credential = ClientSecretCredential(
                tenant_id=settings.azure_tenant_id,
                client_id=settings.azure_client_id,
                client_secret=settings.azure_client_secret
            )

            _validate_credential(credential)
            return credential

        except Exception as sp_error:
            # If service principal fails, we'll try DefaultAzureCredential as fallback
            # This handles cases where .env has partial/invalid credentials
            pass

    # Fallback to DefaultAzureCredential (for az login, managed identity, etc.)
    try:
        credential = DefaultAzureCredential(
            additionally_allowed_tenants=['*'],
            exclude_interactive_browser_credential=True,  # Non-interactive
            exclude_shared_token_cache_credential=True    # More predictable
        )

        _validate_credential(credential)
        return credential

    except Exception as default_error:
        # Both methods failed - provide helpful error message
        raise AzureAuthError(
            "Azure authentication failed. Please check:\n"
            "1. Service Principal (recommended):\n"
            "   - Set AZURE_TENANT_ID in .env\n"
            "   - Set AZURE_CLIENT_ID in .env\n"
            "   - Set AZURE_CLIENT_SECRET in .env\n"
            "   - Ensure service principal has required permissions\n"
            "2. OR use Azure CLI:\n"
            "   - Run: az login\n"
            "   - Then retry dfo command\n"
            f"\nError: {default_error}"
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
