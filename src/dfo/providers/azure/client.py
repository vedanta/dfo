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
