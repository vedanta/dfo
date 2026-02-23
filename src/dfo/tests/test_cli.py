"""Integration tests for main CLI."""

# Third-party
import pytest
from typer.testing import CliRunner

# Internal
from dfo.cli import app
from dfo.core.config import reset_settings
from dfo.db.duck import reset_db

runner = CliRunner()


@pytest.fixture
def setup_env(tmp_path, monkeypatch):
    """Setup test environment."""
    db_file = tmp_path / "test.duckdb"
    monkeypatch.setenv("DFO_DUCKDB_FILE", str(db_file))
    monkeypatch.setenv("AZURE_TENANT_ID", "test")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test")

    reset_settings()
    reset_db()

    yield

    reset_db()
    reset_settings()


def test_help_command(setup_env):
    """Test that help is shown."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "DevFinOps CLI" in result.stdout
    assert "version" in result.stdout
    assert "config" in result.stdout
    assert "db" in result.stdout
    assert "azure" in result.stdout


def test_no_args_shows_help(setup_env):
    """Test that running with no args shows help."""
    result = runner.invoke(app, [])
    # no_args_is_help=True returns exit code 0
    assert result.exit_code == 0
    assert "DevFinOps CLI" in result.stdout


def test_db_help(setup_env):
    """Test db subcommand help."""
    result = runner.invoke(app, ["db", "--help"])
    assert result.exit_code == 0
    assert "init" in result.stdout
    assert "refresh" in result.stdout
    assert "info" in result.stdout


def test_azure_help(setup_env):
    """Test azure subcommand help."""
    result = runner.invoke(app, ["azure", "--help"])
    assert result.exit_code == 0
    assert "discover" in result.stdout
    assert "analyze" in result.stdout
    assert "report" in result.stdout
    assert "execute" in result.stdout


def test_command_help_flags(setup_env):
    """Test that each command has --help."""
    commands = [
        ["version", "--help"],
        ["config", "--help"],
        ["db", "init", "--help"],
        ["db", "refresh", "--help"],
        ["db", "info", "--help"],
        ["azure", "discover", "--help"],
        ["azure", "analyze", "--help"],
        ["azure", "report", "--help"],
        ["azure", "execute", "--help"]
    ]

    for cmd in commands:
        result = runner.invoke(app, cmd)
        assert result.exit_code == 0
        # Check that help text is present (either explicitly or via usage)
        assert len(result.stdout) > 0
