"""Tests for version command."""

# Third-party
from typer.testing import CliRunner

# Internal
from dfo.cli import app

runner = CliRunner()


def test_version_command():
    """Test version command."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "dfo" in result.stdout
    assert "0.0.2" in result.stdout
    assert "DevFinOps" in result.stdout


def test_version_help():
    """Test version command help."""
    result = runner.invoke(app, ["version", "--help"])
    assert result.exit_code == 0
    assert "version" in result.stdout.lower()
