"""Rules engine for VM optimization detection.

Loads rules from vm_rules.json and applies user configuration overrides.
Supports structured rule format with threshold/period/unit separation.
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from enum import Enum

# Third-party
from pydantic import BaseModel, Field

# Internal
from dfo.core.config import get_settings


class ThresholdOperator(str, Enum):
    """Threshold comparison operators."""
    LESS_THAN = "<"
    GREATER_THAN = ">"
    EQUAL = "="
    LESS_EQUAL = "<="
    GREATER_EQUAL = ">="


class ServiceType(str, Enum):
    """Supported service types for optimization rules."""
    VM = "vm"
    DATABASE = "database"
    STORAGE = "storage"
    NETWORKING = "networking"
    APP_SERVICE = "app-service"
    AKS = "aks"


class OptimizationRule(BaseModel):
    """Single optimization rule with structured thresholds."""
    service_type: str  # Service type: vm, database, storage, networking, etc.
    layer: int
    sub_layer: str
    type: str
    metric: str
    threshold: str  # Raw threshold string (e.g., "<20%", ">0")
    period: str     # Time period (e.g., "14d", "7d", "na")
    unit: str
    providers: Dict[str, str]

    # Parsed threshold components (computed at runtime)
    threshold_operator: Optional[ThresholdOperator] = None
    threshold_value: Optional[float] = None
    period_days: Optional[int] = None
    enabled: bool = True

    def model_post_init(self, __context: Any) -> None:
        """Parse threshold and period after initialization."""
        self._parse_threshold()
        self._parse_period()

    def _parse_threshold(self) -> None:
        """Parse threshold string into operator and value.

        Examples:
            "<20%" → operator: <, value: 20.0
            ">0"   → operator: >, value: 0.0
            "0"    → operator: =, value: 0.0
        """
        threshold = self.threshold.strip()

        # Try to match operator + number patterns
        patterns = [
            (r'^([<>]=?)\s*(\d+(?:\.\d+)?)%?$', lambda m: (m.group(1), float(m.group(2)))),
            (r'^(\d+(?:\.\d+)?)%?$', lambda m: ('=', float(m.group(1)))),
        ]

        for pattern, parser in patterns:
            match = re.match(pattern, threshold)
            if match:
                operator_str, value = parser(match)
                self.threshold_operator = ThresholdOperator(operator_str)
                self.threshold_value = value
                return

        # If no numeric pattern matched, leave as None (qualitative threshold)
        # Examples: "high", "low", "improve", "faas_cheaper"
        self.threshold_operator = None
        self.threshold_value = None

    def _parse_period(self) -> None:
        """Parse period string into days.

        Examples:
            "7d"  → 7
            "14d" → 14
            "30d" → 30
            "na"  → None
        """
        period = self.period.strip().lower()

        if period == "na":
            self.period_days = None
            return

        # Match pattern like "7d", "14d", "30d"
        match = re.match(r'^(\d+)d$', period)
        if match:
            self.period_days = int(match.group(1))
        else:
            self.period_days = None

    def matches_threshold(self, value: float) -> bool:
        """Check if a value matches this rule's threshold.

        Args:
            value: Value to compare against threshold.

        Returns:
            True if value matches threshold condition, False otherwise.
            Returns False if threshold is qualitative (cannot compare).
        """
        if self.threshold_operator is None or self.threshold_value is None:
            return False  # Cannot evaluate qualitative thresholds

        if self.threshold_operator == ThresholdOperator.LESS_THAN:
            return value < self.threshold_value
        elif self.threshold_operator == ThresholdOperator.GREATER_THAN:
            return value > self.threshold_value
        elif self.threshold_operator == ThresholdOperator.EQUAL:
            return value == self.threshold_value
        elif self.threshold_operator == ThresholdOperator.LESS_EQUAL:
            return value <= self.threshold_value
        elif self.threshold_operator == ThresholdOperator.GREATER_EQUAL:
            return value >= self.threshold_value

        return False


class RuleEngine:
    """Load and manage optimization rules."""

    def __init__(self, rules_file: str = "optimization_rules.json"):
        """Initialize rule engine.

        Args:
            rules_file: Path to rules JSON file (relative to dfo/rules/)
        """
        self.rules_path = Path(__file__).parent / rules_file
        self._rules: List[OptimizationRule] = []
        self._load_rules()
        self._apply_config_overrides()

    def _load_rules(self) -> None:
        """Load rules from JSON file."""
        with open(self.rules_path) as f:
            data = json.load(f)

        for rule_data in data["optimizations"]:
            rule = OptimizationRule(**rule_data)
            self._rules.append(rule)

    def _apply_config_overrides(self) -> None:
        """Apply user configuration overrides to rules.

        Allows users to customize rule thresholds/periods via .env file.
        Also applies DFO_SERVICE_TYPES and DFO_DISABLE_RULES to filter rules.
        """
        settings = get_settings()

        # Parse enabled service types list (empty = all enabled)
        enabled_service_types = []
        if settings.dfo_service_types:
            enabled_service_types = [s.strip() for s in settings.dfo_service_types.split(",") if s.strip()]

        # Parse disabled rules list
        disabled_rules = []
        if settings.dfo_disable_rules:
            disabled_rules = [r.strip() for r in settings.dfo_disable_rules.split(",") if r.strip()]

        # Map config to specific rules
        for rule in self._rules:
            # Apply service type filter (if specified)
            if enabled_service_types and rule.service_type not in enabled_service_types:
                rule.enabled = False

            # Apply disable overrides
            if rule.type in disabled_rules:
                rule.enabled = False

            # Idle VM Detection: Override with DFO_IDLE_CPU_THRESHOLD and DFO_IDLE_DAYS
            if rule.type == "Idle VM Detection":
                rule.threshold_value = settings.dfo_idle_cpu_threshold
                rule.threshold_operator = ThresholdOperator.LESS_THAN
                rule.period_days = settings.dfo_idle_days

            # Right-Sizing (CPU): Could add DFO_RIGHTSIZING_CPU_THRESHOLD
            # elif rule.type == "Right-Sizing (CPU)":
            #     if hasattr(settings, 'dfo_rightsizing_cpu_threshold'):
            #         rule.threshold_value = settings.dfo_rightsizing_cpu_threshold

            # Add more overrides as needed...

    def get_all_rules(self) -> List[OptimizationRule]:
        """Get all rules (enabled and disabled).

        Returns:
            List of all rules.
        """
        return self._rules

    def get_rules_by_layer(self, layer: int) -> List[OptimizationRule]:
        """Get all rules for a specific layer.

        Args:
            layer: Layer number (1, 2, or 3).

        Returns:
            List of rules for that layer.
        """
        return [r for r in self._rules if r.layer == layer and r.enabled]

    def get_rules_by_service_type(self, service_type: str) -> List[OptimizationRule]:
        """Get all rules for a specific service type.

        Args:
            service_type: Service type to filter by (vm, database, etc.)

        Returns:
            List of rules matching the service type.
        """
        return [r for r in self._rules if r.service_type == service_type]

    def get_service_types(self) -> List[str]:
        """Get all unique service types from loaded rules.

        Returns:
            Sorted list of unique service types.
        """
        return sorted(set(r.service_type for r in self._rules))

    def get_enabled_service_types(self) -> List[str]:
        """Get service types that have at least one enabled rule.

        Returns:
            Sorted list of service types with enabled rules.
        """
        enabled_rules = [r for r in self._rules if r.enabled]
        return sorted(set(r.service_type for r in enabled_rules))

    def get_rule_by_type(self, rule_type: str) -> Optional[OptimizationRule]:
        """Get a specific rule by type.

        Args:
            rule_type: Rule type (e.g., "Idle VM Detection").

        Returns:
            Rule if found, None otherwise.
        """
        for rule in self._rules:
            if rule.type == rule_type:
                return rule
        return None

    def get_enabled_rules(self) -> List[OptimizationRule]:
        """Get all enabled rules.

        Returns:
            List of enabled rules.
        """
        return [r for r in self._rules if r.enabled]

    def get_layer1_rules(self) -> List[OptimizationRule]:
        """Get Layer 1 rules (Self-Contained VM optimizations).

        Returns:
            List of Layer 1 rules.
        """
        return self.get_rules_by_layer(1)

    def get_mvp_rules(self) -> List[OptimizationRule]:
        """Get MVP-relevant rules for Milestone 3-6.

        Returns:
            List of rules: Idle VM Detection, Right-Sizing, Shutdown Detection.
        """
        mvp_types = [
            "Idle VM Detection",
            "Right-Sizing (CPU)",
            "Shutdown Detection"
        ]
        return [r for r in self._rules if r.type in mvp_types and r.enabled]

    def enable_rule(self, rule_type: str) -> bool:
        """Enable a specific rule by type.

        Args:
            rule_type: Rule type to enable.

        Returns:
            True if rule was found and enabled, False otherwise.
        """
        for rule in self._rules:
            if rule.type == rule_type:
                rule.enabled = True
                return True
        return False

    def disable_rule(self, rule_type: str) -> bool:
        """Disable a specific rule by type.

        Args:
            rule_type: Rule type to disable.

        Returns:
            True if rule was found and disabled, False otherwise.
        """
        for rule in self._rules:
            if rule.type == rule_type:
                rule.enabled = False
                return True
        return False

    def save_rules(self) -> None:
        """Save current rules state back to JSON file.

        This persists any enable/disable changes made via enable_rule/disable_rule.
        """
        # Build output structure
        rules_data = []
        for rule in self._rules:
            rule_dict = {
                "service_type": rule.service_type,
                "layer": rule.layer,
                "sub_layer": rule.sub_layer,
                "type": rule.type,
                "metric": rule.metric,
                "threshold": rule.threshold,
                "period": rule.period,
                "unit": rule.unit,
                "enabled": rule.enabled,
                "providers": rule.providers
            }
            rules_data.append(rule_dict)

        output = {"optimizations": rules_data}

        # Write to file
        with open(self.rules_path, 'w') as f:
            json.dump(output, f, indent=2)
            f.write('\n')  # Add trailing newline


# Singleton instance
_rule_engine: Optional[RuleEngine] = None


def get_rule_engine() -> RuleEngine:
    """Get or create rule engine singleton.

    Returns:
        RuleEngine instance.
    """
    global _rule_engine
    if _rule_engine is None:
        _rule_engine = RuleEngine()
    return _rule_engine


def reset_rule_engine() -> None:
    """Reset rule engine (useful for testing)."""
    global _rule_engine
    _rule_engine = None
