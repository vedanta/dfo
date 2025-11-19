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


def test_azure_discover_stub(setup_env):
    """Test azure discover stub command."""
    result = runner.invoke(app, ["azure", "discover", "vms"])
    assert result.exit_code == 0
    assert "TODO" in result.stdout
    assert "Milestone 3" in result.stdout


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
