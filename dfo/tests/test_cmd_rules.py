"""Tests for rules management commands."""

# Third-party
import pytest
from typer.testing import CliRunner

# Internal
from dfo.cli import app
from dfo.rules import reset_rule_engine
from dfo.core.config import reset_settings

runner = CliRunner()


@pytest.fixture
def setup_env(monkeypatch):
    """Setup test environment."""
    # Set minimal required config
    monkeypatch.setenv("DFO_DUCKDB_FILE", "test.duckdb")
    monkeypatch.setenv("DFO_IDLE_CPU_THRESHOLD", "5.0")
    monkeypatch.setenv("DFO_IDLE_DAYS", "7")

    reset_settings()
    reset_rule_engine()
    yield
    reset_settings()
    reset_rule_engine()


def test_rules_list_all(setup_env):
    """Test listing all rules."""
    result = runner.invoke(app, ["rules", "list"])

    assert result.exit_code == 0
    assert "Optimization Rules" in result.stdout
    assert "total)" in result.stdout
    assert "Layer" in result.stdout
    assert "Type" in result.stdout
    assert "Metric" in result.stdout
    assert "Threshold" in result.stdout
    assert "Period" in result.stdout
    assert "Status" in result.stdout
    assert "Enabled:" in result.stdout
    assert "Disabled:" in result.stdout


def test_rules_list_by_layer(setup_env):
    """Test listing rules filtered by layer."""
    result = runner.invoke(app, ["rules", "list", "--layer", "1"])

    assert result.exit_code == 0
    assert "Optimization Rules" in result.stdout
    # Should only show Layer 1 rules
    assert "L1" in result.stdout


def test_rules_list_enabled_only(setup_env):
    """Test listing only enabled rules."""
    result = runner.invoke(app, ["rules", "list", "--enabled-only"])

    assert result.exit_code == 0
    assert "Optimization Rules" in result.stdout
    # Should show enabled rules
    assert "Enabled" in result.stdout


def test_rules_show_idle_detection(setup_env):
    """Test showing detailed rule information."""
    result = runner.invoke(app, ["rules", "show", "Idle VM Detection"])

    assert result.exit_code == 0
    assert "Idle VM Detection" in result.stdout
    assert "Layer:" in result.stdout
    assert "Type:" in result.stdout
    assert "Metric:" in result.stdout
    assert "Threshold Configuration:" in result.stdout
    assert "Period Configuration:" in result.stdout
    assert "Provider Mappings:" in result.stdout
    assert "Status:" in result.stdout
    assert "Enabled" in result.stdout


def test_rules_show_nonexistent_rule(setup_env):
    """Test showing a rule that doesn't exist."""
    result = runner.invoke(app, ["rules", "show", "Nonexistent Rule"])

    assert result.exit_code == 1
    assert "not found" in result.stdout
    assert "dfo rules list" in result.stdout


def test_rules_show_displays_source_attribution(setup_env):
    """Test that show command displays configuration source."""
    result = runner.invoke(app, ["rules", "show", "Idle VM Detection"])

    assert result.exit_code == 0
    assert "Source:" in result.stdout
    # Should show either "rules file" or ".env override"
    assert ("rules file" in result.stdout or ".env override" in result.stdout)


def test_rules_show_displays_provider_mappings(setup_env):
    """Test that show command displays provider-specific metrics."""
    result = runner.invoke(app, ["rules", "show", "Idle VM Detection"])

    assert result.exit_code == 0
    assert "Provider Mappings:" in result.stdout
    assert "AZURE:" in result.stdout


def test_rules_show_displays_usage_tip(setup_env):
    """Test that show command displays usage tips for configurable rules."""
    result = runner.invoke(app, ["rules", "show", "Idle VM Detection"])

    assert result.exit_code == 0
    assert "Tip:" in result.stdout
    assert "DFO_IDLE_CPU_THRESHOLD" in result.stdout
    assert "DFO_IDLE_DAYS" in result.stdout


def test_rules_layers_command(setup_env):
    """Test layers command shows layer descriptions."""
    result = runner.invoke(app, ["rules", "layers"])

    assert result.exit_code == 0
    assert "FinOps Optimization Layers" in result.stdout
    assert "Layer 1: Self-Contained VM Optimizations" in result.stdout
    assert "Layer 2: VM-to-VM Relationship Optimizations" in result.stdout
    assert "Layer 3: Infrastructure & Architecture Optimizations" in result.stdout
    assert "Rules per layer:" in result.stdout
    assert "Layer 1:" in result.stdout
    assert "Layer 2:" in result.stdout
    assert "Layer 3:" in result.stdout
    assert "Total:" in result.stdout


def test_rules_mvp_command(setup_env):
    """Test mvp command shows MVP scope."""
    result = runner.invoke(app, ["rules", "mvp"])

    assert result.exit_code == 0
    assert "MVP Scope" in result.stdout
    assert "MVP (Phase 1) - Current Implementation" in result.stdout
    assert "Idle VM Detection" in result.stdout
    assert "Phase 2 - Planned" in result.stdout
    assert "Current MVP Rule:" in result.stdout
    assert "Active" in result.stdout


def test_rules_help(setup_env):
    """Test rules command help."""
    result = runner.invoke(app, ["rules", "--help"])

    assert result.exit_code == 0
    assert "Manage and inspect optimization rules" in result.stdout
    assert "list" in result.stdout
    assert "show" in result.stdout
    assert "layers" in result.stdout
    assert "mvp" in result.stdout


def test_rules_list_help(setup_env):
    """Test rules list command help."""
    result = runner.invoke(app, ["rules", "list", "--help"])

    assert result.exit_code == 0
    assert "List all optimization rules" in result.stdout
    assert "--layer" in result.stdout
    assert "--enabled-only" in result.stdout


def test_rules_show_help(setup_env):
    """Test rules show command help."""
    result = runner.invoke(app, ["rules", "show", "--help"])

    assert result.exit_code == 0
    assert "Show detailed information about a specific rule" in result.stdout


def test_rules_with_env_override(setup_env, monkeypatch):
    """Test that rules show displays .env overrides correctly."""
    # Override default values
    monkeypatch.setenv("DFO_IDLE_CPU_THRESHOLD", "10.0")
    monkeypatch.setenv("DFO_IDLE_DAYS", "30")
    reset_settings()
    reset_rule_engine()

    result = runner.invoke(app, ["rules", "show", "Idle VM Detection"])

    assert result.exit_code == 0
    assert "10.0" in result.stdout  # Should show overridden threshold
    assert "30" in result.stdout    # Should show overridden period


def test_rules_list_empty_filter(setup_env):
    """Test listing rules with filter that matches nothing."""
    # There shouldn't be a layer 99
    result = runner.invoke(app, ["rules", "list", "--layer", "99"])

    assert result.exit_code == 0
    assert "No rules found matching your criteria" in result.stdout
