# DFO Testing Guide

> **Version:** 1.0
> **Last Updated:** 2025-01-26
> **Status:** ✅ Current

This guide explains how to write, run, and maintain tests for the dfo (DevFinOps) project.

---

## Table of Contents

1. [Overview](#overview)
2. [Running Tests](#running-tests)
3. [Test Organization](#test-organization)
4. [Writing New Tests](#writing-new-tests)
5. [Test Patterns & Best Practices](#test-patterns--best-practices)
6. [Fixtures & Test Data](#fixtures--test-data)
7. [Mocking Strategies](#mocking-strategies)
8. [Coverage Requirements](#coverage-requirements)
9. [Continuous Integration](#continuous-integration)
10. [Troubleshooting](#troubleshooting)

---

## Overview

### Test Framework

**dfo uses pytest for all testing:**
- **Framework:** pytest 7.x
- **Coverage Tool:** pytest-cov
- **Mocking:** unittest.mock (standard library)
- **Current Status:** 589 tests passing, 70%+ overall coverage

### Test Philosophy

1. **Unit tests first** - Test individual functions and classes in isolation
2. **Integration tests second** - Test interactions between modules
3. **Mock external services** - Never make real Azure API calls in tests
4. **Fast feedback** - All tests should complete in < 10 seconds
5. **Maintainable** - Tests should be as readable as production code

### Coverage Targets

| Layer | Target Coverage | Rationale |
|-------|----------------|-----------|
| **Execution System** | 90%+ | Production-critical, high-risk operations |
| **Report Formatters** | 90%+ | Customer-facing output |
| **Analysis Modules** | 80%+ | Core business logic |
| **Provider Layer** | 70%+ | Thin wrappers around Azure SDK |
| **CLI Commands** | 70%+ | User-facing but integration-tested |
| **Overall Project** | 80%+ | Balanced coverage across all layers |

**Current Achievement:**
- Execution system: **92% coverage** ✅
- Report formatters: **98% coverage** ✅
- Overall: **70%+ coverage** ✅

---

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest src/dfo/tests/ tests/

# Run specific test file
pytest src/dfo/tests/test_analysis_idle_vms.py

# Run specific test
pytest src/dfo/tests/test_analysis_idle_vms.py::test_analyze_idle_vms_success

# Run with verbose output
pytest -v

# Run tests matching a pattern
pytest -k "idle_vms"
```

### Coverage Reports

```bash
# Run with coverage report (terminal)
pytest src/dfo/tests/ tests/ --cov=src/dfo --cov-report=term-missing

# Generate HTML coverage report
pytest src/dfo/tests/ tests/ --cov=src/dfo --cov-report=html

# View HTML report
open htmlcov/index.html
```

### Development Workflow

```bash
# Watch mode (requires pytest-watch)
ptw src/dfo/tests/

# Run only failed tests from last run
pytest --lf

# Run failed tests first, then all
pytest --ff

# Stop on first failure
pytest -x
```

### Performance

```bash
# Show slowest 10 tests
pytest --durations=10

# Run tests in parallel (requires pytest-xdist)
pytest -n auto
```

---

## Test Organization

### Directory Structure

```
dfo/
├── src/dfo/
│   ├── tests/          # Unit tests (internal to package)
│   │   ├── conftest.py
│   │   ├── test_core_*.py
│   │   ├── test_providers_*.py
│   │   ├── test_discover_*.py
│   │   ├── test_analyze_*.py
│   │   ├── test_report_*.py
│   │   ├── test_execute_*.py
│   │   ├── test_inventory_*.py
│   │   └── test_cmd_*.py
│   └── ...
└── tests/              # Integration tests (external)
    └── test_integration.py
```

### Naming Conventions

**Test Files:**
- Pattern: `test_<module_path>.py`
- Examples:
  - `test_analysis_idle_vms.py` (tests `analyze/idle_vms.py`)
  - `test_execute_plan_manager.py` (tests `execute/plan_manager.py`)
  - `test_report_formatters_console.py` (tests `report/formatters/console.py`)

**Test Functions:**
- Pattern: `test_<function_name>_<scenario>`
- Examples:
  - `test_analyze_idle_vms_success()`
  - `test_create_plan_invalid_analysis_id()`
  - `test_format_console_empty_data()`

**Test Classes (optional):**
- Use when grouping related tests
- Pattern: `TestClassName`
- Example:
  ```python
  class TestPlanManager:
      def test_create_plan_success(self):
          ...
      def test_create_plan_duplicate_name(self):
          ...
  ```

### File-to-Test Mapping

**One test file per module:**

| Module | Test File |
|--------|-----------|
| `src/dfo/analyze/idle_vms.py` | `src/dfo/tests/test_analysis_idle_vms.py` |
| `src/dfo/execute/plan_manager.py` | `src/dfo/tests/test_execute_plan_manager.py` |
| `src/dfo/report/formatters/console.py` | `src/dfo/tests/test_report_formatters_console.py` |
| `src/dfo/cmd/azure.py` | `src/dfo/tests/test_cmd_azure.py` |

---

## Writing New Tests

### Step-by-Step Process

**1. Create Test File**
```bash
touch src/dfo/tests/test_<module_name>.py
```

**2. Import Dependencies**
```python
"""Tests for <module description>."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from dfo.<module_path> import <function_or_class>
from dfo.core.models import VMInventory, VMAnalysis
```

**3. Define Fixtures (if needed)**
```python
@pytest.fixture
def sample_vm():
    """Sample VM for testing."""
    return VMInventory(
        id="vm1",
        name="test-vm",
        resource_group="test-rg",
        location="eastus",
        size="Standard_D2s_v3",
        power_state="running",
        os_type="Linux",
        priority="Regular",
        subscription_id="sub-123",
        discovered_at=datetime.now(),
        cpu_metrics_json='[{"timestamp": "2024-01-01T00:00:00Z", "value": 3.2}]'
    )
```

**4. Write Test Cases**
```python
def test_analyze_idle_vms_success(sample_vm, test_db):
    """Test successful idle VM analysis."""
    # Arrange
    db = test_db
    db.execute("INSERT INTO vm_inventory VALUES (...)")

    # Act
    result = analyze_idle_vms(db, cpu_threshold=5.0, idle_days=14)

    # Assert
    assert len(result) == 1
    assert result[0].severity == "high"
    assert result[0].recommended_action == "deallocate"
```

### Test Structure (AAA Pattern)

**Arrange-Act-Assert:**
```python
def test_create_plan_success(test_db):
    """Test successful plan creation."""
    # Arrange - Set up test data
    db = test_db
    analysis_id = "idle-vms-2024-01-01"

    # Act - Execute the function
    plan = create_plan(db, name="Test Plan", from_analysis=analysis_id)

    # Assert - Verify the results
    assert plan.name == "Test Plan"
    assert plan.status == "draft"
    assert plan.total_actions > 0
```

### Common Test Scenarios

**1. Success Case**
```python
def test_function_success():
    """Test successful execution with valid input."""
    result = my_function(valid_input)
    assert result == expected_output
```

**2. Error Handling**
```python
def test_function_invalid_input():
    """Test function raises error for invalid input."""
    with pytest.raises(ValueError, match="Invalid input"):
        my_function(invalid_input)
```

**3. Edge Cases**
```python
def test_function_empty_data():
    """Test function handles empty data gracefully."""
    result = my_function([])
    assert result == []

def test_function_boundary_values():
    """Test function with boundary values."""
    assert my_function(0) == expected_min
    assert my_function(100) == expected_max
```

**4. State Transitions**
```python
def test_plan_status_transitions(test_db):
    """Test all valid plan status transitions."""
    plan = create_plan(test_db, "Test")
    assert plan.status == "draft"

    plan = validate_plan(test_db, plan.id)
    assert plan.status == "validated"

    plan = approve_plan(test_db, plan.id)
    assert plan.status == "approved"
```

---

## Test Patterns & Best Practices

### 1. Use Real Pydantic Models, Not Mocks

**❌ Bad:**
```python
# Don't use Mock for Pydantic models
vm = Mock(spec=VMInventory)
vm.name = "test-vm"  # Will fail Pydantic validation!
```

**✅ Good:**
```python
# Use real Pydantic instances
vm = VMInventory(
    id="vm1",
    name="test-vm",
    resource_group="test-rg",
    location="eastus",
    size="Standard_D2s_v3",
    power_state="running",
    os_type="Linux",
    priority="Regular",
    subscription_id="sub-123",
    discovered_at=datetime.now()
)
```

### 2. Mock External Services Only

**Mock Azure SDK calls, not internal functions:**

```python
@patch('dfo.providers.azure.compute.ComputeManagementClient')
def test_list_vms(mock_compute_client):
    """Test VM listing with mocked Azure SDK."""
    # Mock the Azure SDK response
    mock_vm = MagicMock()
    mock_vm.name = "test-vm"
    mock_vm.location = "eastus"
    mock_compute_client.return_value.virtual_machines.list.return_value = [mock_vm]

    # Test our wrapper
    vms = list_vms(subscription_id="sub-123")
    assert len(vms) == 1
```

### 3. Use Database Fixtures, Not Raw SQL

**❌ Bad:**
```python
def test_get_plan(test_db):
    # Don't write raw SQL in tests
    test_db.execute("""
        INSERT INTO execution_plans (id, name, status, created_at)
        VALUES ('plan-1', 'Test', 'draft', '2024-01-01')
    """)
```

**✅ Good:**
```python
def test_get_plan(test_db):
    # Use manager classes
    plan_manager = PlanManager(test_db)
    plan = plan_manager.create_plan(
        name="Test",
        from_analysis="idle-vms-2024-01-01"
    )
    assert plan.status == "draft"
```

### 4. Test One Thing Per Test

**❌ Bad:**
```python
def test_plan_workflow():
    """Test everything at once."""
    plan = create_plan(...)
    plan = validate_plan(...)
    plan = approve_plan(...)
    plan = execute_plan(...)
    # Too much! Hard to debug failures
```

**✅ Good:**
```python
def test_create_plan():
    """Test plan creation only."""
    plan = create_plan(...)
    assert plan.status == "draft"

def test_validate_plan():
    """Test plan validation only."""
    plan = validate_plan(...)
    assert plan.status == "validated"
```

### 5. Use Descriptive Test Names

**❌ Bad:**
```python
def test_plan():
    ...

def test_plan2():
    ...
```

**✅ Good:**
```python
def test_create_plan_with_valid_analysis_id():
    ...

def test_create_plan_fails_with_invalid_analysis_id():
    ...

def test_create_plan_prevents_duplicate_names():
    ...
```

### 6. Avoid Test Interdependence

**❌ Bad:**
```python
# Test order matters - fragile!
def test_a():
    global shared_state
    shared_state = "setup"

def test_b():
    # Depends on test_a running first
    assert shared_state == "setup"
```

**✅ Good:**
```python
# Tests are independent
def test_a(setup_fixture):
    assert setup_fixture == "ready"

def test_b(setup_fixture):
    assert setup_fixture == "ready"
```

---

## Fixtures & Test Data

### Using conftest.py

**src/dfo/tests/conftest.py** - Shared fixtures for all tests:

```python
import pytest
import tempfile
from pathlib import Path
from dfo.db.duck import DuckDBManager

@pytest.fixture
def test_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as tmp:
        db_path = Path(tmp.name)

    # Initialize database
    db = DuckDBManager(db_path)
    db.initialize()

    yield db

    # Cleanup
    db.close()
    db_path.unlink(missing_ok=True)

@pytest.fixture
def sample_vm_data():
    """Sample VM data for testing."""
    return {
        "id": "vm-1",
        "name": "test-vm",
        "resource_group": "test-rg",
        "location": "eastus",
        "size": "Standard_D2s_v3",
        "power_state": "running",
        "os_type": "Linux",
        "priority": "Regular",
        "subscription_id": "sub-123"
    }
```

### Per-File Fixtures

**Local fixtures in test files:**

```python
# src/dfo/tests/test_execute_plan_manager.py

@pytest.fixture
def plan_manager(test_db):
    """Create PlanManager instance with test DB."""
    from dfo.execute.plan_manager import PlanManager
    return PlanManager(test_db)

@pytest.fixture
def sample_plan(plan_manager):
    """Create a sample plan for testing."""
    return plan_manager.create_plan(
        name="Test Plan",
        from_analysis="idle-vms-2024-01-01"
    )
```

### Fixture Scopes

```python
# Function scope (default) - fresh fixture per test
@pytest.fixture
def test_db():
    ...

# Module scope - shared across test file
@pytest.fixture(scope="module")
def expensive_setup():
    ...

# Session scope - shared across entire test run
@pytest.fixture(scope="session")
def global_config():
    ...
```

---

## Mocking Strategies

### Mocking Azure SDK Calls

**Pattern: Mock at the provider boundary**

```python
from unittest.mock import patch, MagicMock

@patch('dfo.providers.azure.compute.ComputeManagementClient')
def test_discover_vms(mock_compute_client):
    """Test VM discovery with mocked Azure SDK."""
    # Setup mock
    mock_client = mock_compute_client.return_value
    mock_vm = MagicMock()
    mock_vm.name = "test-vm"
    mock_vm.location = "eastus"
    mock_vm.hardware_profile.vm_size = "Standard_D2s_v3"

    mock_client.virtual_machines.list.return_value = [mock_vm]

    # Test
    vms = discover_vms(subscription_id="sub-123")

    # Verify
    assert len(vms) == 1
    assert vms[0].name == "test-vm"
    mock_client.virtual_machines.list.assert_called_once()
```

### Mocking Time/Dates

```python
from unittest.mock import patch
from datetime import datetime

@patch('dfo.analyze.idle_vms.datetime')
def test_idle_detection_time_window(mock_datetime):
    """Test idle detection uses correct time window."""
    # Fix current time
    mock_datetime.now.return_value = datetime(2024, 1, 15, 12, 0, 0)

    # Test
    result = analyze_idle_vms(idle_days=14)

    # Verify time window is 14 days back
    expected_start = datetime(2024, 1, 1, 12, 0, 0)
    # ... assertions
```

### Mocking File I/O

```python
from unittest.mock import mock_open, patch

@patch('builtins.open', new_callable=mock_open, read_data='{"key": "value"}')
def test_load_config_from_file(mock_file):
    """Test loading configuration from JSON file."""
    config = load_config("config.json")

    assert config["key"] == "value"
    mock_file.assert_called_once_with("config.json", "r")
```

### Mocking Environment Variables

```python
@patch.dict('os.environ', {'DFO_IDLE_CPU_THRESHOLD': '10.0'})
def test_config_from_env():
    """Test configuration loads from environment."""
    config = get_settings()
    assert config.idle_cpu_threshold == 10.0
```

---

## Coverage Requirements

### Measuring Coverage

```bash
# Generate coverage report
pytest --cov=src/dfo --cov-report=term-missing

# Show lines NOT covered
pytest --cov=src/dfo --cov-report=term-missing | grep "MISS"

# Generate detailed HTML report
pytest --cov=src/dfo --cov-report=html
open htmlcov/index.html
```

### Coverage by Layer

**Priority order for test coverage:**

1. **Execution System (90%+)** - Production-critical
   - Plan management
   - Validation logic
   - Approval workflow
   - Execution engine
   - Rollback capability

2. **Report Formatters (90%+)** - Customer-facing
   - Console output
   - JSON export
   - CSV export
   - Data collectors

3. **Analysis Modules (80%+)** - Core business logic
   - Idle VM detection
   - Rightsizing analysis
   - Cost calculations

4. **Provider Layer (70%+)** - Thin wrappers
   - Azure SDK integration
   - API calls

### What NOT to Test

**Skip testing:**
- Third-party libraries (trust pytest, Azure SDK, etc.)
- Trivial getters/setters
- Pydantic model definitions (Pydantic tests itself)
- Auto-generated code

---

## Continuous Integration

### GitHub Actions (Future)

**Planned CI workflow:**

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest pytest-cov
      - name: Run tests
        run: pytest --cov=src/dfo --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Pre-commit Hooks (Future)

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
```

---

## Troubleshooting

### Common Issues

**1. Tests fail with database errors**
```
Error: database is locked
```
**Solution:** Ensure `test_db` fixture is used and properly cleaned up.

**2. Pydantic validation errors in tests**
```
ValidationError: 1 validation error for VMInventory
```
**Solution:** Use real Pydantic models, not Mock objects. Provide all required fields.

**3. Import errors**
```
ModuleNotFoundError: No module named 'dfo'
```
**Solution:** Install package in editable mode: `pip install -e .`

**4. Fixture not found**
```
fixture 'test_db' not found
```
**Solution:** Ensure `conftest.py` exists in `src/dfo/tests/` directory.

**5. Tests pass locally but fail in CI**
**Solution:** Check for:
- Hard-coded paths (use `Path` from pathlib)
- Timezone assumptions (use UTC)
- Environment variable dependencies
- Test order dependencies

### Debugging Tests

```bash
# Print output (pytest captures by default)
pytest -s

# Drop into debugger on failure
pytest --pdb

# Increase verbosity
pytest -vv

# Show local variables on failure
pytest -l
```

---

## Quick Reference

### Test Checklist

- [ ] Test file named `test_<module>.py`
- [ ] Test functions named `test_<function>_<scenario>`
- [ ] Uses AAA pattern (Arrange-Act-Assert)
- [ ] Uses real Pydantic models (not Mocks)
- [ ] Mocks external services only
- [ ] Independent (doesn't rely on other tests)
- [ ] Has clear assertions
- [ ] Handles edge cases
- [ ] Descriptive docstrings

### Running Tests Checklist

```bash
# Before committing
pytest src/dfo/tests/ tests/              # All tests pass
pytest --cov=src/dfo --cov-report=term    # Coverage meets targets
pytest -k "my_new_tests" -v               # New tests pass

# Before pushing
pytest --cov=src/dfo --cov-report=html    # Generate coverage report
open htmlcov/index.html                   # Review coverage gaps
```

---

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [CODE_STYLE.md](CODE_STYLE.md) - Code style standards
- [DEVELOPER_ONBOARDING.md](DEVELOPER_ONBOARDING.md) - Developer setup
- [TEST_COVERAGE_ANALYSIS.md](TEST_COVERAGE_ANALYSIS.md) - Current coverage status
- [E2E_TEST_WORKFLOW.md](E2E_TEST_WORKFLOW.md) - End-to-end testing

---

**Last Updated:** 2025-01-26
**Maintained By:** DFO Development Team
