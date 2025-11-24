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
    assert "44 total" in result.stdout  # All rules: 29 VM + 15 storage
    assert "storage(15)" in result.stdout or "vm(29)" in result.stdout  # Service type counts
    assert "Enabled: 5" in result.stdout  # 5 enabled rules
    assert "Disabled: 39" in result.stdout  # 39 disabled rules


def test_rules_list_by_layer(setup_env):
    """Test listing rules filtered by layer."""
    result = runner.invoke(app, ["rules", "list", "--layer", "1"])

    assert result.exit_code == 0
    assert "Optimization Rules" in result.stdout
    # Should only show Layer 1 rules (10 VM + 5 storage = 15 total)
    assert "15 total" in result.stdout
    assert "storage(5)" in result.stdout or "vm(10)" in result.stdout


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


def test_rules_enable_command(setup_env, tmp_path, monkeypatch):
    """Test enable command updates rule status."""
    import json
    from pathlib import Path

    # Create a temporary rules file using new schema
    temp_rules_file = tmp_path / "vm_rules.json"
    rules_data = {
        "service": "vm",
        "version": "1.0",
        "description": "Test VM rules",
        "rules": [
            {
                "service_type": "vm",
                "layer": 1,
                "sub_layer": "Test",
                "type": "Test Rule",
                "metric": "test",
                "threshold": "0",
                "period": "7d",
                "unit": "percent",
                "enabled": False,
                "providers": {"azure": "test"}
            }
        ]
    }
    with open(temp_rules_file, 'w') as f:
        json.dump(rules_data, f)

    # Monkeypatch the rules directory to use tmp_path
    from dfo import rules
    original_file = rules.__file__

    def mock_file():
        return str(tmp_path / "__init__.py")

    monkeypatch.setattr(rules, "__file__", str(tmp_path / "__init__.py"))
    reset_rule_engine()

    result = runner.invoke(app, ["rules", "enable", "Test Rule"])

    assert result.exit_code == 0
    assert "Enabled rule: Test Rule" in result.stdout
    assert "Updated vm_rules.json" in result.stdout

    # Verify file was updated
    with open(temp_rules_file) as f:
        updated_data = json.load(f)
    assert updated_data["rules"][0]["enabled"] is True

    # Restore
    monkeypatch.setattr(rules, "__file__", original_file)
    reset_rule_engine()


def test_rules_disable_command(setup_env, tmp_path, monkeypatch):
    """Test disable command updates rule status."""
    import json
    from pathlib import Path

    # Create a temporary rules file using new schema
    temp_rules_file = tmp_path / "vm_rules.json"
    rules_data = {
        "service": "vm",
        "version": "1.0",
        "description": "Test VM rules",
        "rules": [
            {
                "service_type": "vm",
                "layer": 1,
                "sub_layer": "Test",
                "type": "Test Rule",
                "metric": "test",
                "threshold": "0",
                "period": "7d",
                "unit": "percent",
                "enabled": True,
                "providers": {"azure": "test"}
            }
        ]
    }
    with open(temp_rules_file, 'w') as f:
        json.dump(rules_data, f)

    # Monkeypatch the rules directory to use tmp_path
    from dfo import rules
    original_file = rules.__file__

    monkeypatch.setattr(rules, "__file__", str(tmp_path / "__init__.py"))
    reset_rule_engine()

    result = runner.invoke(app, ["rules", "disable", "Test Rule"])

    assert result.exit_code == 0
    assert "Disabled rule: Test Rule" in result.stdout
    assert "Updated vm_rules.json" in result.stdout

    # Verify file was updated
    with open(temp_rules_file) as f:
        updated_data = json.load(f)
    assert updated_data["rules"][0]["enabled"] is False

    # Restore
    monkeypatch.setattr(rules, "__file__", original_file)
    reset_rule_engine()


def test_rules_enable_already_enabled(setup_env):
    """Test enabling a rule that's already enabled."""
    result = runner.invoke(app, ["rules", "enable", "Idle VM Detection"])

    assert result.exit_code == 0
    assert "already enabled" in result.stdout


def test_rules_disable_already_disabled(setup_env):
    """Test disabling a rule that's already disabled."""
    # Family Optimization should be disabled by default
    result = runner.invoke(app, ["rules", "disable", "Family Optimization"])

    assert result.exit_code == 0
    assert "already disabled" in result.stdout


def test_rules_enable_nonexistent(setup_env):
    """Test enabling a rule that doesn't exist."""
    result = runner.invoke(app, ["rules", "enable", "Nonexistent Rule"])

    assert result.exit_code == 1
    assert "not found" in result.stdout


def test_rules_disable_nonexistent(setup_env):
    """Test disabling a rule that doesn't exist."""
    result = runner.invoke(app, ["rules", "disable", "Nonexistent Rule"])

    assert result.exit_code == 1
    assert "not found" in result.stdout


def test_dfo_disable_rules_env_var(setup_env, monkeypatch):
    """Test that DFO_DISABLE_RULES environment variable disables rules."""
    # Set env var to disable Idle VM Detection
    monkeypatch.setenv("DFO_DISABLE_RULES", "Idle VM Detection,Right-Sizing (CPU)")
    reset_settings()
    reset_rule_engine()

    result = runner.invoke(app, ["rules", "show", "Idle VM Detection"])

    assert result.exit_code == 0
    # The rule should show as disabled due to env override
    assert "Disabled" in result.stdout


def test_rules_validate_command(setup_env):
    """Test validate command with valid rules."""
    result = runner.invoke(app, ["rules", "validate"])

    assert result.exit_code == 0
    assert "Validation Summary" in result.stdout
    assert "Valid files:" in result.stdout
    assert "✓ All rules files are valid" in result.stdout or "Validation passed with warnings" in result.stdout


def test_rules_validate_verbose(setup_env):
    """Test validate command with verbose output."""
    result = runner.invoke(app, ["rules", "validate", "--verbose"])

    assert result.exit_code == 0
    assert "Validating vm_rules.json" in result.stdout
    assert "Validation Summary" in result.stdout


def test_rules_validate_help(setup_env):
    """Test validate command help."""
    result = runner.invoke(app, ["rules", "validate", "--help"])

    assert result.exit_code == 0
    assert "Validate all rules files" in result.stdout
    assert "--verbose" in result.stdout
    assert "File schema" in result.stdout
    assert "Duplicate keys" in result.stdout
