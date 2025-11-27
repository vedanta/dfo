# Service-Based Rules Architecture Refactoring

## ✅ Status: COMPLETED (2025-01-24)

**Implementation:** Complete - service-based architecture is now live
**Old File:** `optimization_rules.json` has been removed
**Backward Compatibility:** Removed - all users must use service-specific files

## Overview

Refactored from single `optimization_rules.json` to service-specific rule files for better scalability and maintainability.

## Architecture (Implemented)

### Before (Single File)
```
src/dfo/rules/
├── __init__.py
└── optimization_rules.json  (all 29 rules)
```

### After (Service-Based - Current)
```
src/dfo/rules/
├── __init__.py              (RuleEngine loads from all *_rules.json)
├── vm_rules.json            (29 VM rules)
├── storage_rules.json       (future)
├── database_rules.json      (future)
├── networking_rules.json    (future)
├── container_rules.json     (future)
└── security_rules.json      (future)
```

## File Schema

Each service-specific file follows the same schema:

### `vm_rules.json`
```json
{
  "service": "vm",
  "version": "1.0",
  "description": "Virtual Machine optimization rules",
  "rules": [
    {
      "service_type": "vm",
      "layer": 1,
      "type": "Idle VM Detection",
      "key": "idle-vms",
      ...
    }
  ]
}
```

### `storage_rules.json` (future)
```json
{
  "service": "storage",
  "version": "1.0",
  "description": "Storage optimization rules",
  "rules": [
    {
      "service_type": "disk",
      "layer": 1,
      "type": "Orphaned Disk Detection",
      "key": "orphaned-disks",
      ...
    },
    {
      "service_type": "blob",
      "layer": 1,
      "type": "Cold Tier Migration",
      "key": "cold-tier-eligible",
      ...
    }
  ]
}
```

## RuleEngine Refactoring

### Current Implementation
```python
class RuleEngine:
    def __init__(self):
        rules_file = Path(__file__).parent / "optimization_rules.json"
        with open(rules_file) as f:
            data = json.load(f)
            self.rules = [OptimizationRule(**r) for r in data["optimizations"]]
```

### Proposed Implementation
```python
class RuleEngine:
    def __init__(self, service_filter: Optional[str] = None):
        """Load rules from all service-specific files.

        Args:
            service_filter: Optional service name to load only specific rules
                          (e.g., "vm", "storage"). If None, loads all.
        """
        self.rules = []
        rules_dir = Path(__file__).parent

        # Find all *_rules.json files
        rule_files = sorted(rules_dir.glob("*_rules.json"))

        for rule_file in rule_files:
            # Extract service name from filename (e.g., "vm" from "vm_rules.json")
            service_name = rule_file.stem.replace("_rules", "")

            # Skip if filtering for specific service
            if service_filter and service_name != service_filter:
                continue

            # Load and validate
            with open(rule_file) as f:
                data = json.load(f)

                # Validate schema
                if "service" not in data or "rules" not in data:
                    raise ValueError(f"Invalid schema in {rule_file}")

                # Load rules
                for rule_dict in data["rules"]:
                    rule = OptimizationRule(**rule_dict)
                    self.rules.append(rule)

        if not self.rules:
            raise ValueError("No rules loaded. Check rules directory.")
```

### Backward Compatibility Helper
```python
def _migrate_from_legacy_file(self):
    """Temporary: Support loading from old optimization_rules.json."""
    legacy_file = Path(__file__).parent / "optimization_rules.json"

    if legacy_file.exists() and not self.rules:
        import warnings
        warnings.warn(
            "optimization_rules.json is deprecated. "
            "Use service-specific files (vm_rules.json, etc.)",
            DeprecationWarning
        )
        with open(legacy_file) as f:
            data = json.load(f)
            self.rules = [OptimizationRule(**r) for r in data["optimizations"]]
```

## Migration Steps

### Phase 1: Create Service Files (No Breaking Changes)
1. Create `vm_rules.json` from current `optimization_rules.json`
2. Update RuleEngine to load from both old and new files
3. Add deprecation warning for old file
4. Update tests to use new structure
5. Update documentation

### Phase 2: Deprecate Old File
1. Mark `optimization_rules.json` as deprecated
2. Add migration guide
3. Update all examples to use new structure

### Phase 3: Remove Old File (Breaking Change)
1. Delete `optimization_rules.json`
2. Remove backward compatibility code
3. Release major version

## Implementation Code

### 1. Create `vm_rules.json`

```python
# Migration script
import json
from pathlib import Path

# Read old file
old_file = Path("src/dfo/rules/optimization_rules.json")
with open(old_file) as f:
    old_data = json.load(f)

# Create new file
new_data = {
    "service": "vm",
    "version": "1.0",
    "description": "Virtual Machine optimization rules",
    "rules": old_data["optimizations"]
}

new_file = Path("src/dfo/rules/vm_rules.json")
with open(new_file, "w") as f:
    json.dump(new_data, f, indent=2)

print(f"Created {new_file} with {len(new_data['rules'])} rules")
```

### 2. Update RuleEngine

```python
# src/dfo/rules/__init__.py

class RuleEngine:
    def __init__(self, service_filter: Optional[str] = None):
        self.rules = []
        self._load_service_rules(service_filter)

        # Backward compatibility: load from old file if no rules loaded
        if not self.rules:
            self._load_legacy_rules()

    def _load_service_rules(self, service_filter: Optional[str] = None):
        """Load rules from service-specific files."""
        rules_dir = Path(__file__).parent
        rule_files = sorted(rules_dir.glob("*_rules.json"))

        for rule_file in rule_files:
            service_name = rule_file.stem.replace("_rules", "")

            if service_filter and service_name != service_filter:
                continue

            with open(rule_file) as f:
                data = json.load(f)
                for rule_dict in data.get("rules", []):
                    self.rules.append(OptimizationRule(**rule_dict))

    def _load_legacy_rules(self):
        """Load from deprecated optimization_rules.json."""
        legacy_file = Path(__file__).parent / "optimization_rules.json"

        if legacy_file.exists():
            import warnings
            warnings.warn(
                "optimization_rules.json is deprecated. "
                "Please migrate to service-specific files.",
                DeprecationWarning
            )
            with open(legacy_file) as f:
                data = json.load(f)
                for rule_dict in data.get("optimizations", []):
                    self.rules.append(OptimizationRule(**rule_dict))

    def get_services(self) -> List[str]:
        """Get list of all services with rules."""
        return sorted(set(rule.service_type for rule in self.rules))

    def get_rules_by_service(self, service: str) -> List[OptimizationRule]:
        """Get all rules for a specific service."""
        return [r for r in self.rules if r.service_type == service]
```

### 3. Update Tests

```python
# tests/test_rules_engine.py

def test_load_vm_rules():
    """Test loading VM rules from vm_rules.json."""
    engine = RuleEngine(service_filter="vm")
    assert len(engine.rules) == 29
    assert all(r.service_type == "vm" for r in engine.rules)

def test_load_all_rules():
    """Test loading all rules from all service files."""
    engine = RuleEngine()
    assert len(engine.rules) > 0

def test_get_services():
    """Test getting list of services."""
    engine = RuleEngine()
    services = engine.get_services()
    assert "vm" in services

def test_get_rules_by_service():
    """Test filtering rules by service."""
    engine = RuleEngine()
    vm_rules = engine.get_rules_by_service("vm")
    assert len(vm_rules) == 29
    assert all(r.service_type == "vm" for r in vm_rules)

def test_legacy_file_loads_with_warning():
    """Test backward compatibility with old file."""
    # If only legacy file exists, should load with warning
    with pytest.warns(DeprecationWarning):
        engine = RuleEngine()
        assert len(engine.rules) > 0
```

## CLI Impact (None - Backward Compatible)

### Before (Current)
```bash
./dfo rules list          # Shows all rules
./dfo azure analyze idle-vms
```

### After (Same API)
```bash
./dfo rules list          # Shows all rules (from all service files)
./dfo rules list --service vm      # NEW: Filter by service
./dfo azure analyze idle-vms       # Works the same
```

### New Commands (Optional Future Enhancement)
```bash
./dfo rules services      # List all services
./dfo rules list --service storage  # List storage rules
```

## Validation Schema

Add JSON schema validation for each service file:

```python
SERVICE_RULE_SCHEMA = {
    "type": "object",
    "required": ["service", "version", "rules"],
    "properties": {
        "service": {"type": "string"},
        "version": {"type": "string"},
        "description": {"type": "string"},
        "rules": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["service_type", "layer", "type", "key", "module"]
            }
        }
    }
}
```

## Benefits Summary

1. **Scalability**: Can grow to hundreds of rules across dozens of services
2. **Maintainability**: Each file is ~30-50 rules (manageable size)
3. **Organization**: Clear service boundaries
4. **Performance**: Can lazy-load only needed services (future)
5. **Ownership**: Teams can own their service rule files
6. **Versioning**: Each service can version independently
7. **Testing**: Can test service rules in isolation
8. **Deployment**: Can deploy service rules independently

## Migration Timeline

**Week 1 (Phase 1):**
- Create vm_rules.json
- Update RuleEngine with backward compatibility
- Update tests
- Test thoroughly

**Week 2 (Phase 2):**
- Add deprecation warnings
- Update all documentation
- Announce migration to users

**Week 3+ (Phase 3 - Future):**
- Remove optimization_rules.json (major version bump)
- Remove backward compatibility code

## Example: Adding Storage Rules

```json
// src/dfo/rules/storage_rules.json
{
  "service": "storage",
  "version": "1.0",
  "description": "Azure Storage optimization rules",
  "rules": [
    {
      "service_type": "disk",
      "layer": 1,
      "sub_layer": "Self-Contained",
      "type": "Orphaned Disk Detection",
      "key": "orphaned-disks",
      "category": "storage",
      "description": "Detect unattached managed disks incurring costs",
      "module": "orphaned_disks",
      "enabled": true,
      "actions": ["delete", "snapshot"],
      "export_formats": ["csv", "json"]
    },
    {
      "service_type": "blob",
      "layer": 1,
      "sub_layer": "Self-Contained",
      "type": "Cold Tier Migration",
      "key": "cold-tier-eligible",
      "category": "storage",
      "description": "Identify blobs that should be moved to cold tier",
      "module": "cold_tier_eligible",
      "enabled": false,
      "actions": ["tier-change", "report"],
      "export_formats": ["csv", "json"]
    }
  ]
}
```

Then create:
- `src/dfo/analyze/orphaned_disks.py`
- `src/dfo/analyze/cold_tier_eligible.py`

And the CLI automatically works:
```bash
./dfo azure analyze orphaned-disks
./dfo azure analyze cold-tier-eligible
```

## Conclusion

This refactoring sets up the project for long-term scalability without breaking existing functionality. It's a clean architectural improvement that can be done incrementally.
