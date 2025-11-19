"""Tests for config command."""

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


def test_config_command(setup_env):
    """Test config command."""
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "Configuration" in result.stdout
    assert "***" in result.stdout  # secrets masked
    assert "test-sub" in result.stdout  # subscription visible


def test_config_show_secrets(setup_env):
    """Test config command with --show-secrets."""
    result = runner.invoke(app, ["config", "--show-secrets"])
    assert result.exit_code == 0
    assert "test-tenant" in result.stdout
    assert "test-client" in result.stdout
    assert "test-secret" in result.stdout


def test_config_help():
    """Test config command help."""
    result = runner.invoke(app, ["config", "--help"])
    assert result.exit_code == 0
    assert "configuration" in result.stdout.lower()
