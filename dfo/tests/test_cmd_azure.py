"""Tests for Azure commands."""

# Third-party
import pytest
from typer.testing import CliRunner

# Internal
from dfo.cli import app
from dfo.core.config import reset_settings

runner = CliRunner()


@pytest.fixture
def setup_env(monkeypatch):
    """Setup test environment."""
    monkeypatch.setenv("DFO_DUCKDB_FILE", "test.duckdb")
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-sub")

    reset_settings()
    yield
    reset_settings()


def test_azure_discover_vms_success(setup_env):
    """Test successful VM discovery."""
    from unittest.mock import Mock, patch
    from dfo.core.models import VMInventory
    from datetime import datetime

    # Mock inventory data
    mock_inventory = [
        VMInventory(
            vm_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            name="vm1",
            resource_group="rg1",
            location="eastus",
            size="Standard_D2s_v3",
            power_state="running",
            tags={"env": "prod"},
            cpu_timeseries=[{"timestamp": "2025-01-01T00:00:00Z", "average": 2.5}],
            discovered_at=datetime.utcnow()
        ),
        VMInventory(
            vm_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm2",
            name="vm2",
            resource_group="rg1",
            location="eastus",
            size="Standard_B2s",
            power_state="stopped",
            tags={},
            cpu_timeseries=[],
            discovered_at=datetime.utcnow()
        )
    ]

    with patch('dfo.discovery.vms.discover_vms') as mock_discover, \
         patch('dfo.rules.get_rule_engine') as mock_engine:

        mock_discover.return_value = mock_inventory

        # Mock rule engine
        mock_rule = Mock()
        mock_rule.type = "Idle VM Detection"
        mock_rule.period_days = 7
        mock_rule.providers = {"azure": "Percentage CPU"}
        mock_engine.return_value.get_rule_by_type.return_value = mock_rule

        result = runner.invoke(app, ["azure", "discover", "vms"])

        assert result.exit_code == 0
        assert "Starting VM discovery" in result.stdout
        assert "Discovery complete" in result.stdout
        assert "VMs discovered" in result.stdout and "2" in result.stdout
        assert "VMs with metrics" in result.stdout and "1" in result.stdout
        assert "VMs without metrics" in result.stdout
        assert "Lookback period" in result.stdout and "7 days" in result.stdout
        assert "VM inventory updated" in result.stdout

        # Verify discover_vms was called with correct args
        mock_discover.assert_called_once()
        call_kwargs = mock_discover.call_args[1]
        assert call_kwargs['subscription_id'] is None
        assert call_kwargs['refresh'] is True


def test_azure_discover_unsupported_resource(setup_env):
    """Test discover with unsupported resource type."""
    result = runner.invoke(app, ["azure", "discover", "databases"])

    assert result.exit_code == 1
    assert "Unsupported resource type: databases" in result.stdout
    assert "Supported types: vms" in result.stdout


def test_azure_discover_failure(setup_env):
    """Test discover command when discovery fails."""
    from unittest.mock import patch, Mock

    with patch('dfo.discovery.vms.discover_vms') as mock_discover, \
         patch('dfo.rules.get_rule_engine') as mock_engine:

        # Mock rule engine
        mock_rule = Mock()
        mock_rule.type = "Idle VM Detection"
        mock_rule.period_days = 7
        mock_rule.providers = {"azure": "Percentage CPU"}
        mock_engine.return_value.get_rule_by_type.return_value = mock_rule

        # Simulate discovery failure
        mock_discover.side_effect = Exception("Azure API error")

        result = runner.invoke(app, ["azure", "discover", "vms"])

        assert result.exit_code == 1
        assert "Discovery failed" in result.stdout
        assert "Azure API error" in result.stdout


def test_azure_discover_authorization_error(setup_env):
    """Test discover command with Azure authorization error."""
    from unittest.mock import patch, Mock
    from azure.core.exceptions import HttpResponseError

    with patch('dfo.discovery.vms.discover_vms') as mock_discover, \
         patch('dfo.rules.get_rule_engine') as mock_engine:

        # Mock rule engine
        mock_rule = Mock()
        mock_rule.type = "Idle VM Detection"
        mock_rule.period_days = 7
        mock_rule.providers = {"azure": "Percentage CPU"}
        mock_engine.return_value.get_rule_by_type.return_value = mock_rule

        # Simulate authorization error
        error = HttpResponseError("AuthorizationFailed")
        mock_discover.side_effect = error

        result = runner.invoke(app, ["azure", "discover", "vms"])

        assert result.exit_code == 1
        assert "Discovery failed" in result.stdout
        assert "Permission Denied" in result.stdout
        assert "Reader" in result.stdout


def test_azure_discover_authentication_error(setup_env):
    """Test discover command with authentication error."""
    from unittest.mock import patch, Mock
    from azure.core.exceptions import ClientAuthenticationError

    with patch('dfo.discovery.vms.discover_vms') as mock_discover, \
         patch('dfo.rules.get_rule_engine') as mock_engine:

        # Mock rule engine
        mock_rule = Mock()
        mock_rule.type = "Idle VM Detection"
        mock_rule.period_days = 7
        mock_rule.providers = {"azure": "Percentage CPU"}
        mock_engine.return_value.get_rule_by_type.return_value = mock_rule

        # Simulate authentication error
        error = ClientAuthenticationError("Invalid credentials")
        mock_discover.side_effect = error

        result = runner.invoke(app, ["azure", "discover", "vms"])

        assert result.exit_code == 1
        assert "Discovery failed" in result.stdout
        assert "Authentication Failed" in result.stdout
        assert "test-auth" in result.stdout


def test_azure_discover_no_refresh(setup_env):
    """Test discover with --no-refresh flag."""
    from unittest.mock import Mock, patch
    from dfo.core.models import VMInventory
    from datetime import datetime

    mock_inventory = [
        VMInventory(
            vm_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            name="vm1",
            resource_group="rg1",
            location="eastus",
            size="Standard_D2s_v3",
            power_state="running",
            tags={},
            cpu_timeseries=[],
            discovered_at=datetime.utcnow()
        )
    ]

    with patch('dfo.discovery.vms.discover_vms') as mock_discover, \
         patch('dfo.rules.get_rule_engine') as mock_engine:

        mock_discover.return_value = mock_inventory

        mock_rule = Mock()
        mock_rule.type = "Idle VM Detection"
        mock_rule.period_days = 7
        mock_rule.providers = {"azure": "Percentage CPU"}
        mock_engine.return_value.get_rule_by_type.return_value = mock_rule

        result = runner.invoke(app, ["azure", "discover", "vms", "--no-refresh"])

        assert result.exit_code == 0

        # Verify refresh=False was passed
        call_kwargs = mock_discover.call_args[1]
        assert call_kwargs['refresh'] is False


def test_azure_discover_custom_subscription(setup_env):
    """Test discover with custom subscription ID."""
    from unittest.mock import Mock, patch
    from dfo.core.models import VMInventory
    from datetime import datetime

    mock_inventory = [
        VMInventory(
            vm_id="/subscriptions/custom-sub/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            name="vm1",
            resource_group="rg1",
            location="westus",
            size="Standard_B1s",
            power_state="running",
            tags={},
            cpu_timeseries=[],
            discovered_at=datetime.utcnow()
        )
    ]

    with patch('dfo.discovery.vms.discover_vms') as mock_discover, \
         patch('dfo.rules.get_rule_engine') as mock_engine:

        mock_discover.return_value = mock_inventory

        mock_rule = Mock()
        mock_rule.type = "Idle VM Detection"
        mock_rule.period_days = 7
        mock_rule.providers = {"azure": "Percentage CPU"}
        mock_engine.return_value.get_rule_by_type.return_value = mock_rule

        result = runner.invoke(app, ["azure", "discover", "vms", "--subscription", "custom-sub-123"])

        assert result.exit_code == 0

        # Verify custom subscription was passed
        call_kwargs = mock_discover.call_args[1]
        assert call_kwargs['subscription_id'] == "custom-sub-123"


def test_azure_discover_empty_inventory(setup_env):
    """Test discover with no VMs found."""
    from unittest.mock import Mock, patch

    with patch('dfo.discovery.vms.discover_vms') as mock_discover, \
         patch('dfo.rules.get_rule_engine') as mock_engine:

        mock_discover.return_value = []  # No VMs

        mock_rule = Mock()
        mock_rule.type = "Idle VM Detection"
        mock_rule.period_days = 7
        mock_rule.providers = {"azure": "Percentage CPU"}
        mock_engine.return_value.get_rule_by_type.return_value = mock_rule

        result = runner.invoke(app, ["azure", "discover", "vms"])

        assert result.exit_code == 0
        assert "VMs discovered" in result.stdout and "0" in result.stdout
        assert "VMs with metrics" in result.stdout


def test_azure_analyze_stub(setup_env):
    """Test azure analyze stub command."""
    result = runner.invoke(app, ["azure", "analyze", "idle-vms"])
    assert result.exit_code == 0
    assert "TODO" in result.stdout
    assert "Milestone 4" in result.stdout


def test_azure_report_stub(setup_env):
    """Test azure report stub command."""
    result = runner.invoke(app, ["azure", "report", "idle-vms"])
    assert result.exit_code == 0
    assert "TODO" in result.stdout


def test_azure_report_with_format(setup_env):
    """Test azure report with format option."""
    result = runner.invoke(app, ["azure", "report", "idle-vms", "--format", "json"])
    assert result.exit_code == 0
    assert "json" in result.stdout.lower()


def test_azure_execute_stub(setup_env):
    """Test azure execute stub command."""
    result = runner.invoke(app, ["azure", "execute", "stop-idle-vms"])
    assert result.exit_code == 0
    assert "TODO" in result.stdout
    assert "DRY RUN" in result.stdout  # default dry run


def test_azure_execute_live_mode(setup_env):
    """Test azure execute with live mode."""
    result = runner.invoke(app, ["azure", "execute", "stop-idle-vms", "--no-dry-run"])
    assert result.exit_code == 0
    assert "LIVE" in result.stdout


def test_azure_help():
    """Test azure command help."""
    result = runner.invoke(app, ["azure", "--help"])
    assert result.exit_code == 0
    assert "discover" in result.stdout
    assert "analyze" in result.stdout
    assert "report" in result.stdout
    assert "execute" in result.stdout


def test_azure_test_auth_success(setup_env):
    """Test azure test-auth command with valid credentials."""
    from unittest.mock import Mock, patch

    with patch('dfo.core.auth.get_azure_credential') as mock_cred, \
         patch('dfo.providers.azure.client.get_compute_client') as mock_compute, \
         patch('dfo.providers.azure.client.get_monitor_client') as mock_monitor:

        mock_cred.return_value = Mock()
        mock_compute.return_value = Mock()
        mock_monitor.return_value = Mock()

        result = runner.invoke(app, ["azure", "test-auth"])

        assert result.exit_code == 0
        assert "Authentication successful" in result.stdout
        assert "Compute client created" in result.stdout
        assert "Monitor client created" in result.stdout
        assert "Authentication test passed" in result.stdout


def test_azure_test_auth_failure(setup_env):
    """Test azure test-auth command with invalid credentials."""
    from unittest.mock import patch
    from dfo.core.auth import AzureAuthError

    with patch('dfo.core.auth.get_azure_credential') as mock_cred:
        mock_cred.side_effect = AzureAuthError("Invalid credentials")

        result = runner.invoke(app, ["azure", "test-auth"])

        assert result.exit_code == 1
        assert "Authentication failed" in result.stdout
