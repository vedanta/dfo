# Milestone 2: Authentication & Azure Provider Setup - Implementation Plan

## Overview
**Goal:** Establish Azure authentication and basic provider client infrastructure.
**Duration:** Week 2 (3-4 days)

**Exit Criteria:**
- Can authenticate to Azure using DefaultAzureCredential or service principal
- Can instantiate Azure SDK clients (Compute, Monitor) successfully
- All client instantiation is cached/reused (singleton pattern)
- Credential validation works with clear error messages
- All tests pass with >80% coverage
- All code follows CODE_STYLE.md standards

---

## Code Style & Standards

**All code MUST follow CODE_STYLE.md:**
- Import order: stdlib → third-party → internal
- Type hints on all functions
- Max 250 lines per file, 40 lines per function
- No print() statements (use logging or Rich console)
- DFO_ prefix for custom environment variables
- Proper error handling with actionable messages

---

## Task Breakdown

### Task 1: Core Authentication Layer

**File:** `dfo/core/auth.py`

**Objective:** Create centralized Azure authentication with credential management and validation.

#### Implementation

```python
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
```

#### Tests

**File:** `dfo/tests/test_auth.py`

```python
"""Tests for Azure authentication layer."""
import pytest
from unittest.mock import Mock, patch, MagicMock
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
        mock_cred = Mock()
        mock_cred.get_token.return_value = Mock(token="test-token")
        mock_default.return_value = mock_cred

        cred1 = get_cached_credential()
        reset_credential()
        cred2 = get_cached_credential()

        assert cred1 is not cred2
        assert mock_default.call_count == 2
```

#### Acceptance Criteria
- [ ] `core/auth.py` implements authentication with DefaultAzureCredential
- [ ] Fallback to ClientSecretCredential works correctly
- [ ] Credential validation catches auth failures early
- [ ] Singleton pattern for credential caching
- [ ] Clear, actionable error messages
- [ ] 9 tests pass covering all auth scenarios
- [ ] No violations of CODE_STYLE.md

---

### Task 2: Azure Client Factory

**File:** `dfo/providers/azure/client.py`

**Objective:** Create factory functions for Azure SDK clients with caching.

#### Implementation

```python
"""Azure SDK client factory.

This module provides factory functions for creating and caching Azure SDK clients.
Clients are expensive to create, so we use a singleton pattern per subscription.

Per CODE_STYLE.md:
- This is a provider module - only Azure SDK calls allowed
- No database operations
- No business logic
"""
from typing import Dict, Optional

# Third-party
from azure.core.credentials import TokenCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.monitor import MonitorManagementClient

# Internal
from dfo.core.auth import get_cached_credential


# Client caches (keyed by subscription_id)
_compute_clients: Dict[str, ComputeManagementClient] = {}
_monitor_clients: Dict[str, MonitorManagementClient] = {}


def get_compute_client(
    subscription_id: str,
    credential: Optional[TokenCredential] = None
) -> ComputeManagementClient:
    """Get or create a ComputeManagementClient for the subscription.

    Args:
        subscription_id: Azure subscription ID.
        credential: Optional credential. If not provided, uses get_cached_credential().

    Returns:
        ComputeManagementClient: Cached or newly created client.
    """
    if subscription_id in _compute_clients:
        return _compute_clients[subscription_id]

    if credential is None:
        credential = get_cached_credential()

    client = ComputeManagementClient(
        credential=credential,
        subscription_id=subscription_id
    )

    _compute_clients[subscription_id] = client
    return client


def get_monitor_client(
    subscription_id: str,
    credential: Optional[TokenCredential] = None
) -> MonitorManagementClient:
    """Get or create a MonitorManagementClient for the subscription.

    Args:
        subscription_id: Azure subscription ID.
        credential: Optional credential. If not provided, uses get_cached_credential().

    Returns:
        MonitorManagementClient: Cached or newly created client.
    """
    if subscription_id in _monitor_clients:
        return _monitor_clients[subscription_id]

    if credential is None:
        credential = get_cached_credential()

    client = MonitorManagementClient(
        credential=credential,
        subscription_id=subscription_id
    )

    _monitor_clients[subscription_id] = client
    return client


def reset_clients() -> None:
    """Clear all cached clients (useful for testing).

    Should not be called in production code.
    """
    global _compute_clients, _monitor_clients
    _compute_clients.clear()
    _monitor_clients.clear()
```

#### Tests

**File:** `dfo/tests/test_client.py`

```python
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
```

#### Acceptance Criteria
- [ ] `providers/azure/client.py` implements client factory functions
- [ ] Clients are cached per subscription (singleton pattern)
- [ ] Falls back to cached credential when none provided
- [ ] 8 tests pass covering all client scenarios
- [ ] No violations of CODE_STYLE.md

---

### Task 3: Azure Provider Stub Implementations

**File:** `dfo/providers/azure/compute.py`

**Objective:** Create stub functions for compute operations (to be fully implemented in Milestone 3).

#### Implementation

```python
"""Azure Compute provider operations.

This module contains Azure SDK wrappers for compute operations.

Per CODE_STYLE.md:
- This is a provider module - Azure SDK calls only
- No database operations
- No business logic (that belongs in discover/analyze layers)
"""
from typing import List, Dict, Any

# Third-party
from azure.mgmt.compute import ComputeManagementClient


def list_vms(client: ComputeManagementClient) -> List[Dict[str, Any]]:
    """List all VMs in the subscription.

    Args:
        client: ComputeManagementClient instance.

    Returns:
        List of VM dictionaries with basic metadata.

    Note:
        This is a stub implementation for Milestone 2.
        Full implementation in Milestone 3.
    """
    # Stub: return empty list
    # Milestone 3 will implement actual VM listing
    return []


def stop_vm(
    client: ComputeManagementClient,
    resource_group: str,
    vm_name: str
) -> Dict[str, Any]:
    """Stop a VM (keeps it allocated).

    Args:
        client: ComputeManagementClient instance.
        resource_group: Resource group name.
        vm_name: VM name.

    Returns:
        Operation result dictionary.

    Note:
        This is a stub implementation for Milestone 2.
        Full implementation in Milestone 6.
    """
    # Stub: return success
    return {"status": "stub", "message": "Not implemented yet"}


def deallocate_vm(
    client: ComputeManagementClient,
    resource_group: str,
    vm_name: str
) -> Dict[str, Any]:
    """Deallocate a VM (releases compute resources).

    Args:
        client: ComputeManagementClient instance.
        resource_group: Resource group name.
        vm_name: VM name.

    Returns:
        Operation result dictionary.

    Note:
        This is a stub implementation for Milestone 2.
        Full implementation in Milestone 6.
    """
    # Stub: return success
    return {"status": "stub", "message": "Not implemented yet"}
```

**File:** `dfo/providers/azure/monitor.py`

```python
"""Azure Monitor provider operations.

This module contains Azure SDK wrappers for Monitor/metrics operations.

Per CODE_STYLE.md:
- This is a provider module - Azure SDK calls only
- No database operations
- No business logic
"""
from typing import List, Dict, Any
from datetime import datetime

# Third-party
from azure.mgmt.monitor import MonitorManagementClient


def get_cpu_metrics(
    client: MonitorManagementClient,
    resource_id: str,
    days: int = 14
) -> List[Dict[str, Any]]:
    """Get CPU metrics for a VM.

    Args:
        client: MonitorManagementClient instance.
        resource_id: Full Azure resource ID of the VM.
        days: Number of days of metrics to retrieve.

    Returns:
        List of metric data points with timestamps and values.

    Note:
        This is a stub implementation for Milestone 2.
        Full implementation in Milestone 3.
    """
    # Stub: return empty list
    # Milestone 3 will implement actual metric retrieval
    return []
```

**File:** `dfo/providers/azure/__init__.py`

```python
"""Azure provider package."""
```

#### Tests

**File:** `dfo/tests/test_compute.py`

```python
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
```

**File:** `dfo/tests/test_monitor.py`

```python
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
```

#### Acceptance Criteria
- [ ] `providers/azure/compute.py` implements stub functions
- [ ] `providers/azure/monitor.py` implements stub functions
- [ ] All functions have proper type hints and docstrings
- [ ] 4 tests pass for stub implementations
- [ ] Ready for full implementation in Milestones 3 and 6

---

### Task 4: CLI Command for Testing Authentication

**Update File:** `dfo/cmd/azure.py`

**Objective:** Add a test command to verify Azure authentication works.

#### Implementation

Add this command to the existing `dfo/cmd/azure.py`:

```python
@app.command()
def test_auth():
    """Test Azure authentication and client creation.

    This command verifies that:
    - Azure credentials are configured correctly
    - Authentication succeeds
    - SDK clients can be instantiated

    Useful for validating Milestone 2 setup.

    Example:
        ./dfo.sh azure test-auth
    """
    from dfo.core.config import get_settings
    from dfo.core.auth import get_azure_credential, AzureAuthError
    from dfo.providers.azure.client import get_compute_client, get_monitor_client
    from rich.console import Console
    from rich.panel import Panel

    console = Console()

    try:
        # Get settings
        console.print("\n[cyan]1/4[/cyan] Loading configuration...")
        settings = get_settings()
        console.print(f"[green]✓[/green] Subscription: {settings.azure_subscription_id}")

        # Test authentication
        console.print("\n[cyan]2/4[/cyan] Authenticating to Azure...")
        credential = get_azure_credential()
        console.print("[green]✓[/green] Authentication successful")

        # Test compute client
        console.print("\n[cyan]3/4[/cyan] Creating Compute client...")
        compute_client = get_compute_client(settings.azure_subscription_id, credential)
        console.print(f"[green]✓[/green] Compute client created")

        # Test monitor client
        console.print("\n[cyan]4/4[/cyan] Creating Monitor client...")
        monitor_client = get_monitor_client(settings.azure_subscription_id, credential)
        console.print(f"[green]✓[/green] Monitor client created")

        # Success summary
        console.print("\n")
        console.print(Panel(
            "[bold green]Authentication test passed![/bold green]\n\n"
            "All Azure clients initialized successfully.\n"
            "You are ready to proceed with VM discovery.",
            title="Success",
            border_style="green"
        ))

    except AzureAuthError as e:
        console.print(f"\n[red]✗[/red] Authentication failed:\n")
        console.print(Panel(str(e), title="Authentication Error", border_style="red"))
        raise typer.Exit(1)

    except Exception as e:
        console.print(f"\n[red]✗[/red] Unexpected error: {e}")
        raise typer.Exit(1)
```

#### Tests

Update `dfo/tests/test_cmd_azure.py`:

```python
def test_azure_test_auth_success(setup_env):
    """Test azure test-auth command with valid credentials."""
    with patch('dfo.cmd.azure.get_azure_credential') as mock_cred, \
         patch('dfo.cmd.azure.get_compute_client') as mock_compute, \
         patch('dfo.cmd.azure.get_monitor_client') as mock_monitor:

        mock_cred.return_value = Mock()
        mock_compute.return_value = Mock()
        mock_monitor.return_value = Mock()

        result = runner.invoke(app, ["azure", "test-auth"])

        assert result.exit_code == 0
        assert "Authentication successful" in result.stdout
        assert "Compute client created" in result.stdout
        assert "Monitor client created" in result.stdout


def test_azure_test_auth_failure(setup_env):
    """Test azure test-auth command with invalid credentials."""
    from dfo.core.auth import AzureAuthError

    with patch('dfo.cmd.azure.get_azure_credential') as mock_cred:
        mock_cred.side_effect = AzureAuthError("Invalid credentials")

        result = runner.invoke(app, ["azure", "test-auth"])

        assert result.exit_code == 1
        assert "Authentication failed" in result.stdout
```

#### Acceptance Criteria
- [ ] `azure test-auth` command implemented
- [ ] Shows clear progress for each authentication step
- [ ] Success panel displays when auth works
- [ ] Clear error messages when auth fails
- [ ] 2 new tests pass

---

### Task 5: Directory Structure Setup

**Objective:** Create provider directory structure.

#### Implementation

```bash
# Create directories
mkdir -p dfo/providers/azure

# Create __init__ files
touch dfo/providers/__init__.py
touch dfo/providers/azure/__init__.py
```

**File:** `dfo/providers/__init__.py`

```python
"""Provider package for cloud SDK integrations."""
```

#### Acceptance Criteria
- [ ] `dfo/providers/` directory exists
- [ ] `dfo/providers/azure/` directory exists
- [ ] Proper `__init__.py` files in place

---

### Task 6: Verify Exit Criteria

**Objective:** Ensure all Milestone 2 requirements are met.

#### Verification Checklist

```bash
# 1. Test authentication
./dfo.sh azure test-auth
# Expected: All 4 steps pass with green checkmarks

# 2. Run all tests
pytest dfo/tests/ -v
# Expected: All tests pass (52 from M1 + ~23 new from M2 = ~75 total)

# 3. Check test coverage
pytest --cov=dfo dfo/tests/ --cov-report=term-missing
# Expected: >80% coverage

# 4. Verify code style
# - All imports follow stdlib → third-party → internal
# - All functions have type hints
# - No print() statements in modules
# - All error messages are actionable

# 5. Verify files created
ls -la dfo/core/auth.py
ls -la dfo/providers/azure/client.py
ls -la dfo/providers/azure/compute.py
ls -la dfo/providers/azure/monitor.py
ls -la dfo/tests/test_auth.py
ls -la dfo/tests/test_client.py
ls -la dfo/tests/test_compute.py
ls -la dfo/tests/test_monitor.py
# Expected: All files exist
```

#### Acceptance Criteria
- [x] All authentication scenarios tested and passing
- [x] Client factory with caching works correctly
- [x] Azure SDK clients instantiate successfully
- [x] CLI test command provides clear feedback
- [x] All tests pass with >80% coverage
- [x] All code follows CODE_STYLE.md standards
- [x] Clear, actionable error messages
- [x] Ready to begin Milestone 3: Discovery Layer

---

## Implementation Timeline

**Day 1 (3-4 hours):**
- Task 1: Core authentication layer
- Write tests for authentication
- Verify auth with real Azure credentials

**Day 2 (3-4 hours):**
- Task 2: Azure client factory
- Task 3: Provider stub implementations
- Write tests for clients and providers

**Day 3 (2-3 hours):**
- Task 4: CLI test-auth command
- Task 5: Directory structure
- Task 6: Verify all exit criteria
- Documentation updates

---

## Dependencies

```
Task 1 (Auth) ──┬──> Task 2 (Client Factory) ──> Task 4 (CLI Command)
                │
                └──> Task 3 (Provider Stubs) ──> Task 4 (CLI Command)

Task 5 (Directories) can be done first or in parallel
Task 6 (Verification) must be last
```

---

## Testing Strategy

### Unit Tests
- Mock all Azure SDK calls
- Test authentication flow with both success and failure paths
- Test client caching behavior
- Test credential validation

### Integration Tests (Optional)
If you have access to a test Azure subscription:
```python
# dfo/tests/test_azure_integration.py
"""Integration tests with real Azure (optional)."""
import pytest
from dfo.core.auth import get_azure_credential
from dfo.providers.azure.client import get_compute_client, get_monitor_client
from dfo.core.config import get_settings


@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("RUN_INTEGRATION_TESTS"), reason="Integration tests disabled")
def test_real_azure_authentication():
    """Test authentication with real Azure."""
    credential = get_azure_credential()
    assert credential is not None


@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("RUN_INTEGRATION_TESTS"), reason="Integration tests disabled")
def test_real_azure_clients():
    """Test client creation with real Azure."""
    settings = get_settings()
    credential = get_azure_credential()

    compute_client = get_compute_client(settings.azure_subscription_id, credential)
    monitor_client = get_monitor_client(settings.azure_subscription_id, credential)

    assert compute_client is not None
    assert monitor_client is not None
```

Run integration tests with:
```bash
RUN_INTEGRATION_TESTS=1 pytest dfo/tests/test_azure_integration.py -v
```

---

## Success Metrics

- All 23 new tests pass (9 auth + 8 client + 4 provider stubs + 2 CLI)
- Total test count: ~75 (52 from M1 + 23 from M2)
- Test coverage remains >80%
- Can successfully authenticate to Azure with real credentials
- Can instantiate Compute and Monitor clients
- `./dfo.sh azure test-auth` provides clear success/failure feedback
- All error messages are actionable and user-friendly
- Code review shows no CODE_STYLE.md violations

---

## Notes

- Keep all Azure SDK calls in the `providers/` layer
- Never put Azure SDK calls in `core/`, `db/`, or `cli/` layers
- Use singleton pattern for credentials and clients (expensive to create)
- Validate credentials early with clear error messages
- Stub implementations in Task 3 will be completed in later milestones
- The `azure test-auth` command is a development/debugging tool, not for production use

---

## Next Steps After Milestone 2

Once Milestone 2 is complete, you'll be ready for:
- **Milestone 3**: Discovery Layer - Implement actual VM discovery and metric collection
- Full implementation of `list_vms()` in compute.py
- Full implementation of `get_cpu_metrics()` in monitor.py
- Create `discover/vms.py` layer for orchestrating discovery
- Update `azure discover` CLI command with real functionality
