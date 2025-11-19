"""Tests for database commands."""
from pathlib import Path

# Third-party
import pytest
from typer.testing import CliRunner

# Internal
from dfo.cli import app
from dfo.db.duck import reset_db
from dfo.core.config import reset_settings

runner = CliRunner()


@pytest.fixture
def setup_env(tmp_path, monkeypatch):
    """Setup test environment."""
    db_file = tmp_path / "test.duckdb"
    monkeypatch.setenv("DFO_DUCKDB_FILE", str(db_file))
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-sub")

    reset_settings()
    reset_db()

    yield db_file

    reset_db()
    reset_settings()


def test_db_init_command(setup_env):
    """Test db init command."""
    result = runner.invoke(app, ["db", "init"])
    assert result.exit_code == 0
    assert "initialized" in result.stdout.lower()
    assert Path(setup_env).exists()


def test_db_init_already_exists(setup_env):
    """Test db init when database already exists."""
    # First init
    runner.invoke(app, ["db", "init"])

    # Second init should fail
    result = runner.invoke(app, ["db", "init"])
    assert result.exit_code == 1
    assert "already exist" in result.stdout.lower()


def test_db_info_command(setup_env):
    """Test db info command."""
    # Initialize first
    runner.invoke(app, ["db", "init"])

    result = runner.invoke(app, ["db", "info"])
    assert result.exit_code == 0
    assert "vm_inventory" in result.stdout
    assert "vm_idle_analysis" in result.stdout
    assert "vm_actions" in result.stdout


def test_db_refresh_with_yes_flag(setup_env):
    """Test db refresh with --yes flag."""
    # Initialize first
    runner.invoke(app, ["db", "init"])

    # Refresh
    result = runner.invoke(app, ["db", "refresh", "--yes"])
    assert result.exit_code == 0
    assert "refreshed" in result.stdout.lower()


def test_db_refresh_cancel(setup_env):
    """Test db refresh with cancelled confirmation."""
    # Initialize first
    runner.invoke(app, ["db", "init"])

    # Refresh but cancel
    result = runner.invoke(app, ["db", "refresh"], input="n\n")
    assert result.exit_code == 0
    assert "Cancelled" in result.stdout


def test_db_help():
    """Test db command help."""
    result = runner.invoke(app, ["db", "--help"])
    assert result.exit_code == 0
    assert "init" in result.stdout
    assert "refresh" in result.stdout
    assert "info" in result.stdout
