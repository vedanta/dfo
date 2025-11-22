# Rules-Driven CLI Architecture

## Overview

The DFO CLI now uses a **rules-driven architecture** where optimization rules defined in `src/dfo/rules/optimization_rules.json` automatically drive CLI command functionality. This eliminates hardcoded command logic and makes the system self-documenting and extensible.

## Key Principle

**The rules file is the single source of truth for CLI commands.** Every analysis type available in the CLI corresponds to a rule in the JSON file.

## Architecture Components

### 1. Enhanced Rules Schema

Each rule in `optimization_rules.json` now includes CLI-specific fields:

```json
{
  "service_type": "vm",
  "layer": 1,
  "sub_layer": "Self-Contained VM",
  "type": "Idle VM Detection",
  "key": "idle-vms",
  "category": "compute",
  "description": "Detect underutilized VMs based on CPU and RAM metrics over time",
  "module": "idle_vms",
  "metric": "CPU/RAM <5%",
  "threshold": "<5%",
  "period": "7d",
  "unit": "percent",
  "enabled": true,
  "actions": ["stop", "deallocate", "delete"],
  "export_formats": ["csv", "json"],
  "providers": {
    "azure": "CPU% + RAM% time series",
    "aws": "AWS: CPUUtilization + mem_used_percent",
    "gcp": "GCP: low CPU+RAM"
  }
}
```

### 2. New Rule Fields

| Field | Type | Purpose | Example |
|-------|------|---------|---------|
| `key` | string | CLI command key | `"idle-vms"` |
| `category` | string | Grouping category | `"compute"` |
| `description` | string | Human-readable description | `"Detect underutilized VMs..."` |
| `module` | string | Python module name in `analyze/` | `"idle_vms"` |
| `actions` | list | Available actions | `["stop", "deallocate", "delete"]` |
| `export_formats` | list | Supported export formats | `["csv", "json"]` |

### 3. RuleEngine Enhancements

New methods added to `RuleEngine` class in `src/dfo/rules/__init__.py`:

#### `get_rule_by_key(key: str) -> OptimizationRule`
Look up a rule by its CLI key.

```python
rule = rule_engine.get_rule_by_key("idle-vms")
```

#### `get_available_analyses(provider: str) -> List[Dict]`
Get all available analysis modules with metadata.

```python
analyses = rule_engine.get_available_analyses(provider="azure")
# Returns: [{"key": "idle-vms", "type": "Idle VM Detection", ...}, ...]
```

#### `get_categories() -> List[str]`
Get all unique categories from rules.

```python
categories = rule_engine.get_categories()
# Returns: ["compute", "storage", "networking", ...]
```

### 4. Dynamic CLI Commands

The `./dfo azure analyze` command is now completely dynamic:

```bash
# List all available analyses
./dfo azure analyze --list

# Run any analysis by key
./dfo azure analyze idle-vms
./dfo azure analyze rightsize-cpu
./dfo azure analyze shutdown-vms
```

## How It Works

### Command Execution Flow

1. **User runs**: `./dfo azure analyze idle-vms`
2. **CLI looks up rule**: `rule = rule_engine.get_rule_by_key("idle-vms")`
3. **Validates rule**:
   - Check if rule exists
   - Check if rule is enabled
   - Check if module is specified
4. **Dynamic import**: `module = importlib.import_module(f"dfo.analysis.{rule.module}")`
5. **Execute analysis**: `module.analyze_idle_vms(...)`
6. **Display results**: Using data from `module.get_idle_vm_summary()`

### List Command Flow

1. **User runs**: `./dfo azure analyze --list`
2. **CLI queries rules**: `analyses = rule_engine.get_available_analyses(provider="azure")`
3. **Display table**: Shows key, category, description, and status for each analysis

## Adding New Analyses

To add a new analysis type, follow these 3 steps:

### Step 1: Create Analysis Module

Create `src/dfo/analysis/new_analysis.py`:

```python
"""New analysis module."""
from dfo.db.duck import get_db

def analyze_new_thing(threshold: float, min_days: int) -> int:
    """Run the analysis."""
    # Analysis logic here
    return count

def get_new_thing_summary() -> dict:
    """Get summary statistics."""
    # Summary logic here
    return {"total": 0, "savings": 0.0}
```

### Step 2: Add Rule to JSON

Add entry to `src/dfo/rules/optimization_rules.json`:

```json
{
  "service_type": "vm",
  "layer": 1,
  "sub_layer": "Self-Contained VM",
  "type": "New Thing Detection",
  "key": "new-thing",
  "category": "compute",
  "description": "Detect new things that need optimization",
  "module": "new_analysis",
  "metric": "Thing usage",
  "threshold": "<10%",
  "period": "7d",
  "unit": "percent",
  "enabled": true,
  "actions": ["fix", "report"],
  "export_formats": ["csv", "json"],
  "providers": {
    "azure": "Azure thing metrics"
  }
}
```

### Step 3: Test

```bash
# Verify it appears in the list
./dfo azure analyze --list

# Run the analysis
./dfo azure analyze new-thing
```

**That's it!** No CLI code changes needed.

## Benefits

### 1. Self-Documenting
The `--list` command automatically shows all available analyses from the rules file.

### 2. Zero CLI Code Changes
Add new analyses by:
- Creating a module in `src/dfo/analysis/`
- Adding a rule entry to `optimization_rules.json`

No modifications to `src/dfo/cmd/azure.py` required.

### 3. Consistent Interface
All analyses use the same CLI pattern:
```bash
./dfo azure analyze <key> [--threshold X] [--min-days Y]
```

### 4. Configuration-Driven
Enable/disable analyses via:
- JSON file: `"enabled": true/false`
- Environment: `DFO_DISABLE_RULES="Idle VM Detection,Right-Sizing (CPU)"`

### 5. Provider-Agnostic
Rules specify provider-specific details, making multi-cloud support straightforward:
```json
"providers": {
  "azure": "Azure Monitor: Percentage CPU",
  "aws": "AWS: CPUUtilization",
  "gcp": "GCP: cpu/utilization"
}
```

## Migration Path

### Before (Hardcoded)

```python
@app.command()
def analyze(analysis_type: str):
    if analysis_type == "idle-vms":
        from dfo.analysis.idle_vms import analyze_idle_vms
        analyze_idle_vms()
    elif analysis_type == "rightsize":
        from dfo.analysis.rightsize import analyze_rightsize
        analyze_rightsize()
    # ... more elif blocks
```

### After (Rules-Driven)

```python
@app.command()
def analyze(analysis_type: str):
    rule = rule_engine.get_rule_by_key(analysis_type)
    module = importlib.import_module(f"dfo.analysis.{rule.module}")
    module.analyze_idle_vms()  # Generic call based on rule
```

## Future Enhancements

### 1. Module Interface Contract

Define a standard interface for all analysis modules:

```python
class AnalysisModule(Protocol):
    def analyze(self, **kwargs) -> int:
        """Run analysis, return count."""
        ...

    def get_summary(self) -> dict:
        """Get summary statistics."""
        ...

    def export(self, format: str, file: str) -> None:
        """Export results."""
        ...
```

### 2. Dynamic Options

Generate CLI options from rule metadata:

```python
# From rule: "actions": ["stop", "deallocate", "delete"]
# Auto-generate: --action [stop|deallocate|delete]

# From rule: "export_formats": ["csv", "json"]
# Auto-generate: --export-format [csv|json]
```

### 3. Category-Based Commands

```bash
# Run all analyses in a category
./dfo azure analyze --category compute

# Run all enabled analyses
./dfo azure analyze --all
```

### 4. Rule Validation

Add JSON schema validation for `optimization_rules.json`:

```bash
./dfo rules validate
```

## Testing

### Unit Tests

Test the RuleEngine methods:

```python
def test_get_rule_by_key():
    engine = RuleEngine()
    rule = engine.get_rule_by_key("idle-vms")
    assert rule is not None
    assert rule.module == "idle_vms"

def test_get_available_analyses():
    engine = RuleEngine()
    analyses = engine.get_available_analyses(provider="azure")
    assert len(analyses) > 0
    assert all("key" in a for a in analyses)
```

### Integration Tests

Test the CLI commands:

```bash
# Test list command
./dfo azure analyze --list

# Test analysis execution
./dfo azure analyze idle-vms
```

## Backward Compatibility

The new system maintains backward compatibility:
- Existing `./dfo azure analyze idle-vms` commands work unchanged
- Rules without `key` field are skipped by `get_available_analyses()`
- Gradual migration: Add fields to rules as you implement new analyses

## Summary

The rules-driven CLI architecture makes DFO:
- **Extensible**: Add analyses without changing CLI code
- **Self-documenting**: `--list` shows all available analyses
- **Consistent**: Same interface for all analyses
- **Maintainable**: Rules file is single source of truth
- **Scalable**: Easy to add dozens of analyses across multiple categories
