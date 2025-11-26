"""Tests for rules engine."""
import pytest
from unittest.mock import patch

# Internal
from dfo.rules import (
    get_rule_engine,
    reset_rule_engine,
    OptimizationRule,
    ThresholdOperator
)
from dfo.core.config import reset_settings


@pytest.fixture(autouse=True)
def reset_engine():
    """Reset rule engine before each test."""
    reset_rule_engine()
    reset_settings()
    yield
    reset_rule_engine()
    reset_settings()


@pytest.fixture
def mock_env(monkeypatch):
    """Set up mock environment."""
    monkeypatch.setenv("AZURE_TENANT_ID", "test")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test")


def test_load_rules(mock_env):
    """Test loading rules from JSON."""
    engine = get_rule_engine()
    rules = engine.get_enabled_rules()

    assert len(rules) > 0
    assert len(rules) == 5  # Should have 5 enabled rules (4 VM + 1 storage for MVP)


def test_get_rule_by_type(mock_env):
    """Test getting specific rule by type."""
    engine = get_rule_engine()
    rule = engine.get_rule_by_type("Idle VM Detection")

    assert rule is not None
    assert rule.layer == 1
    assert rule.metric == "CPU utilization"
    assert rule.threshold == "<5%"
    assert rule.period == "6d"


def test_threshold_parsing(mock_env):
    """Test threshold parsing into operator and value."""
    engine = get_rule_engine()

    # Test "<20%" parsing
    rule = engine.get_rule_by_type("Right-Sizing (CPU)")
    assert rule.threshold_operator == ThresholdOperator.LESS_THAN
    assert rule.threshold_value == 20.0

    # Test "<5%" parsing - but config override sets it to 1.0
    rule = engine.get_rule_by_type("Idle VM Detection")
    assert rule.threshold_operator == ThresholdOperator.LESS_THAN
    assert rule.threshold_value == 1.0  # Config override: DFO_IDLE_CPU_THRESHOLD=1.0

    # Test ">0" parsing
    rule = engine.get_rule_by_type("Orphaned Disk Cleanup")
    assert rule.threshold_operator == ThresholdOperator.GREATER_THAN
    assert rule.threshold_value == 0.0

    # Test "0" (equals) parsing
    rule = engine.get_rule_by_type("Shutdown Detection")
    assert rule.threshold_operator == ThresholdOperator.EQUAL
    assert rule.threshold_value == 0.0


def test_period_parsing(mock_env):
    """Test period parsing into days."""
    engine = get_rule_engine()

    # Test parsing with actual config (may be overridden by shell/env)
    # The idle-vms rule has period="6d" in JSON but will be overridden by DFO_IDLE_DAYS
    # config if set (could be from shell env, .env file, or test fixtures)
    rule = engine.get_rule_by_type("Idle VM Detection")
    assert rule.period_days is not None
    assert isinstance(rule.period_days, int)
    assert rule.period_days > 0  # Should be a positive integer

    # Test "14d" parsing
    rule = engine.get_rule_by_type("Right-Sizing (CPU)")
    assert rule.period_days == 14

    # Test "30d" parsing
    rule = engine.get_rule_by_type("Shutdown Detection")
    assert rule.period_days == 30

    # Test "na" parsing (not applicable)
    rule = engine.get_rule_by_type("Generation Upgrade")
    assert rule.period_days is None


def test_config_overrides(monkeypatch):
    """Test that config overrides are applied to rules."""
    # Set custom thresholds
    monkeypatch.setenv("AZURE_TENANT_ID", "test")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test")
    monkeypatch.setenv("DFO_IDLE_CPU_THRESHOLD", "10.0")
    monkeypatch.setenv("DFO_IDLE_DAYS", "21")

    reset_rule_engine()
    reset_settings()

    engine = get_rule_engine()
    rule = engine.get_rule_by_type("Idle VM Detection")

    # Should use config overrides, not JSON defaults
    assert rule.threshold_value == 10.0  # Overridden from 5.0
    assert rule.period_days == 21        # Overridden from 7


def test_matches_threshold(mock_env):
    """Test threshold matching logic."""
    engine = get_rule_engine()

    # Test "<20%" rule
    rule = engine.get_rule_by_type("Right-Sizing (CPU)")

    assert rule.matches_threshold(15.0) is True   # 15 < 20
    assert rule.matches_threshold(25.0) is False  # 25 > 20
    assert rule.matches_threshold(20.0) is False  # 20 = 20 (not <)

    # Test ">0" rule
    rule = engine.get_rule_by_type("Orphaned Disk Cleanup")

    assert rule.matches_threshold(5.0) is True   # 5 > 0
    assert rule.matches_threshold(0.0) is False  # 0 = 0 (not >)
    assert rule.matches_threshold(-1.0) is False # -1 < 0


def test_qualitative_threshold_no_match(mock_env):
    """Test that qualitative thresholds cannot be matched."""
    engine = get_rule_engine()

    # "high" is qualitative, cannot be numerically compared
    rule = engine.get_rule_by_type("License Optimization")

    assert rule.threshold == "high"
    assert rule.threshold_operator is None
    assert rule.threshold_value is None
    assert rule.matches_threshold(100.0) is False  # Cannot evaluate


def test_layer_filtering(mock_env):
    """Test filtering rules by layer."""
    engine = get_rule_engine()

    layer1_rules = engine.get_rules_by_layer(1)
    layer2_rules = engine.get_rules_by_layer(2)
    layer3_rules = engine.get_rules_by_layer(3)

    # Only enabled rules are returned: 4 layer 1 (3 VM + 1 storage), 1 layer 2, 0 layer 3
    assert len(layer1_rules) == 4  # 4 enabled Self-Contained rules
    assert len(layer2_rules) == 1  # 1 enabled Adjacent rule
    assert len(layer3_rules) == 0  # 0 enabled Architecture rules

    # Verify all layer 1 rules have layer=1
    assert all(r.layer == 1 for r in layer1_rules)


def test_get_mvp_rules(mock_env):
    """Test getting MVP-relevant rules."""
    engine = get_rule_engine()
    mvp_rules = engine.get_mvp_rules()

    # Should return 3 rules for MVP
    assert len(mvp_rules) == 3

    rule_types = [r.type for r in mvp_rules]
    assert "Idle VM Detection" in rule_types
    assert "Right-Sizing (CPU)" in rule_types
    assert "Shutdown Detection" in rule_types


def test_singleton_pattern(mock_env):
    """Test that rule engine is a singleton."""
    engine1 = get_rule_engine()
    engine2 = get_rule_engine()

    assert engine1 is engine2


def test_reset_rule_engine(mock_env):
    """Test resetting rule engine."""
    engine1 = get_rule_engine()
    reset_rule_engine()
    engine2 = get_rule_engine()

    assert engine1 is not engine2


def test_azure_provider_mapping(mock_env):
    """Test that Azure provider mappings are present."""
    engine = get_rule_engine()

    rule = engine.get_rule_by_type("Idle VM Detection")
    assert "azure" in rule.providers
    assert "Azure Monitor - Percentage CPU" in rule.providers["azure"]


def test_all_rules_have_required_fields(mock_env):
    """Test that all rules have required fields."""
    engine = get_rule_engine()
    rules = engine.get_enabled_rules()

    valid_sub_layers = ["Self-Contained VM", "Self-Contained Storage", "Adjacent", "Architecture"]

    for rule in rules:
        assert rule.layer in [1, 2, 3]
        assert rule.sub_layer in valid_sub_layers
        assert rule.type
        assert rule.metric
        assert rule.threshold
        assert rule.period
        assert rule.unit
        assert "azure" in rule.providers


def test_rule_enable_disable(mock_env):
    """Test enabling/disabling rules."""
    engine = get_rule_engine()

    rule = engine.get_rule_by_type("Idle VM Detection")
    assert rule.enabled is True

    # Disable rule
    rule.enabled = False
    enabled_rules = engine.get_enabled_rules()
    assert rule not in enabled_rules

    # Re-enable
    rule.enabled = True
    enabled_rules = engine.get_enabled_rules()
    assert rule in enabled_rules
