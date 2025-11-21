# Milestone 1: Foundation & Infrastructure - Implementation Plan

## Overview
**Goal:** Establish core infrastructure, configuration, and data layer.
**Duration:** Week 1 (5 days)
**Exit Criteria:**
- Can run `dfo --version` and `dfo azure` shows subcommands
- Can run `dfo db init` and `dfo db refresh` to manage database
- DuckDB file is created and schema is initialized
- All tests pass with >80% coverage
- All code follows CODE_STYLE.md standards

---

## Code Style & Standards

**All code in Milestone 1 MUST follow the standards defined in CODE_STYLE.md.**

### Key Standards Summary

#### 1. Core Principles
- **Explicit > Implicit**: No hidden magic, no side effects
- **Small Modules**: Max 200-250 lines per file
- **Small Functions**: Max 30-40 lines per function
- **Rule of One**: One file = one responsibility
- **No Circular Imports**: Follow dependency direction (core → providers → discover → analyze → report → execute → cli)

#### 2. Naming Conventions
- **Files/Modules**: `snake_case.py` (e.g., `idle_vms.py`, `json_report.py`)
- **Classes**: `CamelCase` (e.g., `VMInventory`, `DuckDBManager`)
- **Functions**: `snake_case` verbs (e.g., `list_vms()`, `get_cpu_metrics()`)
- **Environment Variables**: `ALL_CAPS` with `DFO_` prefix (e.g., `DFO_IDLE_CPU_THRESHOLD`)

#### 3. Import Organization
```python
# Standard library
import os
from pathlib import Path

# Third-party
import typer
from pydantic import BaseModel

# Internal (dfo modules)
from dfo.core.config import get_settings
from dfo.db.duck import get_db
```
- **No wildcard imports** (`from x import *`)
- **Explicit imports only**

#### 4. Type Hints & Pydantic
- **All function parameters and returns must have type hints**
- **All cross-layer data uses Pydantic models** (no raw dicts)
- **Use `model_dump()` for serialization** (not manual JSON)

#### 5. Error Handling
- **Fail fast**: Auth failures stop immediately
- **Never swallow exceptions**: Always surface errors
- **Actionable messages**: Tell users what to do

Example:
```python
# Good
raise ValueError("Database file not found. Run 'dfo db init' to create it.")

# Bad
raise Exception("Error")
```

#### 6. Logging
- **Use Python `logging` module** (not `print()` in modules)
- **Default to INFO level**
- **CLI presentation uses Rich console** (not logging)

#### 7. Layer Responsibilities (for Milestone 1)

| Layer | Responsibility | Must NOT Do |
|-------|---------------|-------------|
| `core` | Config, auth, models | No provider calls, no DB writes |
| `db` | DuckDB read/write only | No cloud logic, no analysis |
| `cli/cmd` | Orchestrate commands only | No business logic, no analysis |

### Code Review Checklist

Before considering any task complete, verify:

- [ ] All files ≤ 250 lines
- [ ] All functions ≤ 40 lines
- [ ] All imports follow standard library → third-party → internal order
- [ ] No wildcard imports
- [ ] All functions have type hints
- [ ] All cross-layer data uses Pydantic models
- [ ] Error messages are actionable
- [ ] No `print()` statements in modules (use logging or Rich console)
- [ ] Docstrings follow Google or NumPy style
- [ ] Code follows separation of concerns (Rule of One)

---

## Task Breakdown

### Task 1: Configuration Management (`core/config.py`)
**Priority:** HIGH (foundation for everything else)
**Dependencies:** None
**Estimated Time:** 2-3 hours

#### Implementation Details

Create a Pydantic Settings class that loads configuration from environment variables.

**Code Style Requirements:**
- Follow import order: stdlib → third-party → internal
- All functions must have type hints (including return types)
- Module docstring required
- Function docstrings using Google/NumPy style
- File must be ≤ 250 lines
- Functions must be ≤ 40 lines
- Use `logging` module (not `print()`)
- Actionable error messages

**File:** `dfo/core/config.py`

```python
"""Configuration management using Pydantic Settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False
    )

    # Azure Authentication
    azure_tenant_id: str
    azure_client_id: str
    azure_client_secret: str
    azure_subscription_id: str

    # Analysis Configuration
    dfo_idle_cpu_threshold: float = 5.0
    dfo_idle_days: int = 14
    dfo_dry_run_default: bool = True

    # DuckDB Configuration (uses DFO_ prefix per CODE_STYLE.md)
    dfo_duckdb_file: str = "./dfo.duckdb"

    # Logging Configuration (uses DFO_ prefix per CODE_STYLE.md)
    dfo_log_level: str = "INFO"

# Singleton instance
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    """Get or create the settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

def reset_settings():
    """Reset settings singleton (useful for testing)."""
    global _settings
    _settings = None
```

#### Test File: `dfo/tests/test_config.py`

```python
"""Tests for configuration management."""
import pytest
from pydantic import ValidationError
from dfo.core.config import Settings, get_settings, reset_settings

def test_settings_defaults():
    """Test default values are set correctly."""
    # Need to provide required fields
    settings = Settings(
        azure_tenant_id="test-tenant",
        azure_client_id="test-client",
        azure_client_secret="test-secret",
        azure_subscription_id="test-sub"
    )
    assert settings.dfo_idle_cpu_threshold == 5.0
    assert settings.dfo_idle_days == 14
    assert settings.dfo_dry_run_default is True
    assert settings.dfo_duckdb_file == "./dfo.duckdb"
    assert settings.dfo_log_level == "INFO"

def test_settings_validation():
    """Test that missing required fields raise errors."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(dfo_duckdb_file="test.db")

    # Should complain about missing azure_* fields
    assert "azure_tenant_id" in str(exc_info.value)

def test_settings_from_env(monkeypatch):
    """Test loading settings from environment."""
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-subscription")
    monkeypatch.setenv("DFO_DUCKDB_FILE", "test.duckdb")
    monkeypatch.setenv("DFO_IDLE_CPU_THRESHOLD", "10.0")

    reset_settings()
    settings = get_settings()

    assert settings.azure_tenant_id == "test-tenant"
    assert settings.dfo_duckdb_file == "test.duckdb"
    assert settings.dfo_idle_cpu_threshold == 10.0

def test_settings_singleton(monkeypatch):
    """Test that get_settings returns the same instance."""
    monkeypatch.setenv("AZURE_TENANT_ID", "test")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test")

    reset_settings()
    settings1 = get_settings()
    settings2 = get_settings()

    assert settings1 is settings2
```

#### Acceptance Criteria
- [x] Settings class loads all variables from .env
- [x] Required fields raise validation error if missing
- [x] Default values work correctly
- [x] `get_settings()` returns singleton instance
- [x] All tests pass

---

### Task 2: Core Data Models (`core/models.py`)
**Priority:** HIGH (needed for type safety throughout)
**Dependencies:** None
**Estimated Time:** 3-4 hours

#### Implementation Details

Create Pydantic models representing VMs, analysis results, and actions.

**Code Style Requirements:**
- All models use Pydantic BaseModel
- All fields have type hints (e.g., `cpu_avg: float`, `tags: Dict[str, str]`)
- Keep models small (< 12-15 fields); break into submodels if needed
- Use `to_db_record()` methods for DuckDB serialization (not manual JSON)
- Enums for constrained values (e.g., PowerState, Severity)
- Use `CamelCase` for class names (e.g., `VMInventory`, `VMAnalysis`)
- Module docstring required
- Follow import order: stdlib → third-party → internal

**File:** `dfo/core/models.py`

```python
"""Core data models for dfo."""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

class PowerState(str, Enum):
    """VM power states."""
    RUNNING = "running"
    STOPPED = "stopped"
    DEALLOCATED = "deallocated"
    UNKNOWN = "unknown"

class Severity(str, Enum):
    """Analysis severity levels."""
    CRITICAL = "critical"  # >$500/month savings
    HIGH = "high"          # $200-500/month
    MEDIUM = "medium"      # $50-200/month
    LOW = "low"            # <$50/month

class RecommendedAction(str, Enum):
    """Recommended remediation actions."""
    STOP = "stop"
    DEALLOCATE = "deallocate"
    RESIZE = "resize"
    NONE = "none"

class CPUMetric(BaseModel):
    """CPU metric data point."""
    timestamp: datetime
    average: float
    minimum: Optional[float] = None
    maximum: Optional[float] = None

class VM(BaseModel):
    """Basic VM information."""
    vm_id: str = Field(..., description="Azure resource ID")
    name: str
    resource_group: str
    location: str
    size: str
    power_state: PowerState
    tags: Dict[str, str] = Field(default_factory=dict)

class VMInventory(BaseModel):
    """VM inventory with metrics for storage in DuckDB."""
    vm_id: str
    name: str
    resource_group: str
    location: str
    size: str
    power_state: str
    tags: Dict[str, Any] = Field(default_factory=dict)
    cpu_timeseries: List[Dict[str, Any]] = Field(default_factory=list)
    discovered_at: datetime = Field(default_factory=datetime.utcnow)

    def to_db_record(self) -> Dict[str, Any]:
        """Convert to DuckDB-compatible record."""
        import json
        return {
            "vm_id": self.vm_id,
            "name": self.name,
            "resource_group": self.resource_group,
            "location": self.location,
            "size": self.size,
            "power_state": self.power_state,
            "tags": json.dumps(self.tags),
            "cpu_timeseries": json.dumps(self.cpu_timeseries),
            "discovered_at": self.discovered_at
        }

class VMAnalysis(BaseModel):
    """VM idle analysis results."""
    vm_id: str
    cpu_avg: float
    days_under_threshold: int
    estimated_monthly_savings: float
    severity: Severity
    recommended_action: RecommendedAction
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)

    def to_db_record(self) -> Dict[str, Any]:
        """Convert to DuckDB-compatible record."""
        return {
            "vm_id": self.vm_id,
            "cpu_avg": self.cpu_avg,
            "days_under_threshold": self.days_under_threshold,
            "estimated_monthly_savings": self.estimated_monthly_savings,
            "severity": self.severity.value,
            "recommended_action": self.recommended_action.value,
            "analyzed_at": self.analyzed_at
        }

class VMAction(BaseModel):
    """VM action execution log."""
    vm_id: str
    action: str
    status: str  # "success", "failed", "skipped"
    dry_run: bool
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None

    def to_db_record(self) -> Dict[str, Any]:
        """Convert to DuckDB-compatible record."""
        return {
            "vm_id": self.vm_id,
            "action": self.action,
            "status": self.status,
            "dry_run": self.dry_run,
            "executed_at": self.executed_at,
            "notes": self.notes
        }
```

#### Test File: `dfo/tests/test_models.py`

```python
"""Tests for core data models."""
import pytest
from datetime import datetime
from dfo.core.models import (
    VM, VMInventory, VMAnalysis, VMAction,
    PowerState, Severity, RecommendedAction
)

def test_vm_model():
    """Test VM model validation."""
    vm = VM(
        vm_id="/subscriptions/test/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1",
        name="test-vm",
        resource_group="test-rg",
        location="eastus",
        size="Standard_D2s_v3",
        power_state=PowerState.RUNNING
    )
    assert vm.name == "test-vm"
    assert vm.power_state == PowerState.RUNNING
    assert vm.tags == {}

def test_vm_with_tags():
    """Test VM model with tags."""
    vm = VM(
        vm_id="test-id",
        name="test-vm",
        resource_group="test-rg",
        location="eastus",
        size="Standard_D2s_v3",
        power_state=PowerState.RUNNING,
        tags={"env": "dev", "owner": "team-a"}
    )
    assert vm.tags["env"] == "dev"
    assert vm.tags["owner"] == "team-a"

def test_vm_inventory_to_db_record():
    """Test VMInventory serialization to DB record."""
    inventory = VMInventory(
        vm_id="test-id",
        name="test-vm",
        resource_group="test-rg",
        location="eastus",
        size="Standard_D2s_v3",
        power_state="running",
        tags={"env": "dev"},
        cpu_timeseries=[{"timestamp": "2024-01-01T00:00:00Z", "average": 5.0}]
    )

    record = inventory.to_db_record()
    assert record["vm_id"] == "test-id"
    assert record["name"] == "test-vm"
    assert "tags" in record
    assert "cpu_timeseries" in record
    # JSON strings for DuckDB
    assert isinstance(record["tags"], str)
    assert isinstance(record["cpu_timeseries"], str)
    assert '"env": "dev"' in record["tags"]

def test_vm_analysis_severity_enum():
    """Test severity enum values."""
    analysis = VMAnalysis(
        vm_id="test-id",
        cpu_avg=2.5,
        days_under_threshold=14,
        estimated_monthly_savings=600.0,
        severity=Severity.CRITICAL,
        recommended_action=RecommendedAction.DEALLOCATE
    )
    assert analysis.severity == Severity.CRITICAL
    assert analysis.severity.value == "critical"
    assert analysis.recommended_action == RecommendedAction.DEALLOCATE

def test_vm_analysis_to_db_record():
    """Test VMAnalysis serialization."""
    analysis = VMAnalysis(
        vm_id="test-id",
        cpu_avg=3.2,
        days_under_threshold=10,
        estimated_monthly_savings=150.0,
        severity=Severity.MEDIUM,
        recommended_action=RecommendedAction.STOP
    )

    record = analysis.to_db_record()
    assert record["vm_id"] == "test-id"
    assert record["cpu_avg"] == 3.2
    assert record["severity"] == "medium"
    assert record["recommended_action"] == "stop"

def test_vm_action_model():
    """Test VMAction model."""
    action = VMAction(
        vm_id="test-id",
        action="stop",
        status="success",
        dry_run=True,
        notes="Test dry run"
    )

    assert action.dry_run is True
    assert action.notes == "Test dry run"

    record = action.to_db_record()
    assert record["action"] == "stop"
    assert record["status"] == "success"
    assert record["dry_run"] is True

def test_power_state_enum():
    """Test PowerState enum values."""
    assert PowerState.RUNNING.value == "running"
    assert PowerState.STOPPED.value == "stopped"
    assert PowerState.DEALLOCATED.value == "deallocated"
    assert PowerState.UNKNOWN.value == "unknown"

def test_severity_enum_order():
    """Test Severity enum values."""
    assert Severity.CRITICAL.value == "critical"
    assert Severity.HIGH.value == "high"
    assert Severity.MEDIUM.value == "medium"
    assert Severity.LOW.value == "low"
```

#### Acceptance Criteria
- [x] All models validate correctly
- [x] Enums enforce valid values
- [x] `to_db_record()` methods produce JSON-serializable dicts
- [x] DateTime fields auto-populate with UTC timestamps
- [x] All tests pass

---

### Task 3: DuckDB Integration Layer (`db/duck.py`)
**Priority:** HIGH (critical infrastructure)
**Dependencies:** Task 1 (config)
**Estimated Time:** 4-5 hours

#### Implementation Details

Create DuckDB connection manager with schema initialization and helper functions.

**Code Style Requirements:**
- Centralized DB layer: all DB operations through this module
- SQL in separate files (schema.sql), not inline strings where possible
- Writes must be explicit (define columns in INSERT statements)
- Helper methods must have type hints
- Class uses `CamelCase`: `DuckDBManager`
- Functions use `snake_case` verbs: `get_connection()`, `insert_records()`, `fetch_all()`
- Stateless except for singleton connection
- Module docstring required
- Follow import order: stdlib → third-party → internal
- Actionable error messages (e.g., "Schema file not found at X. Ensure...")
- File must be ≤ 250 lines

**File:** `dfo/db/duck.py`

```python
"""DuckDB integration layer."""
import duckdb
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
from dfo.core.config import get_settings

class DuckDBManager:
    """DuckDB connection and query manager."""

    _instance: Optional['DuckDBManager'] = None
    _connection: Optional[duckdb.DuckDBPyConnection] = None

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize manager (only once due to singleton)."""
        if self._connection is None:
            settings = get_settings()
            self.db_path = settings.dfo_duckdb_file
            self._connection = self._create_connection()

    def _create_connection(self) -> duckdb.DuckDBPyConnection:
        """Create DuckDB connection."""
        # Ensure parent directory exists
        db_path = Path(self.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Connect to database
        conn = duckdb.connect(str(db_path))
        return conn

    def initialize_schema(self, drop_existing: bool = False):
        """Initialize database schema from schema.sql.

        Args:
            drop_existing: If True, drop existing tables before creating
        """
        schema_path = Path(__file__).parent / "schema.sql"
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        if drop_existing:
            tables = ["vm_actions", "vm_idle_analysis", "vm_inventory"]
            for table in tables:
                self._connection.execute(f"DROP TABLE IF EXISTS {table}")
            self._connection.commit()

        schema_sql = schema_path.read_text()
        self._connection.execute(schema_sql)
        self._connection.commit()

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        """Get the database connection."""
        return self._connection

    def execute_query(self, query: str, params: Optional[tuple] = None) -> duckdb.DuckDBPyRelation:
        """Execute a SQL query."""
        if params:
            return self._connection.execute(query, params)
        return self._connection.execute(query)

    def insert_records(self, table: str, records: List[Dict[str, Any]]):
        """Insert multiple records into a table."""
        if not records:
            return

        # Get column names from first record
        columns = list(records[0].keys())
        placeholders = ", ".join(["?" for _ in columns])
        column_names = ", ".join(columns)

        query = f"INSERT INTO {table} ({column_names}) VALUES ({placeholders})"

        # Convert records to tuples
        values = [tuple(record[col] for col in columns) for record in records]

        # Execute batch insert
        self._connection.executemany(query, values)
        self._connection.commit()

    def fetch_all(self, query: str, params: Optional[tuple] = None) -> List[tuple]:
        """Execute query and fetch all results."""
        result = self.execute_query(query, params)
        return result.fetchall()

    def fetch_df(self, query: str, params: Optional[tuple] = None):
        """Execute query and return as pandas DataFrame."""
        result = self.execute_query(query, params)
        return result.df()

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        query = """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name = ?
        """
        result = self.fetch_all(query, (table_name,))
        return result[0][0] > 0

    def count_records(self, table: str) -> int:
        """Count records in a table."""
        result = self.fetch_all(f"SELECT COUNT(*) FROM {table}")
        return result[0][0]

    def clear_table(self, table: str):
        """Delete all records from a table."""
        self.execute_query(f"DELETE FROM {table}")
        self._connection.commit()

    def close(self):
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

# Convenience functions
def get_db() -> DuckDBManager:
    """Get the DuckDB manager singleton."""
    return DuckDBManager()

@contextmanager
def db_connection():
    """Context manager for database operations."""
    db = get_db()
    try:
        yield db
    finally:
        # Connection persists (singleton), just ensures proper usage
        pass

def reset_db():
    """Reset database singleton (useful for testing)."""
    DuckDBManager._instance = None
    DuckDBManager._connection = None
```

#### Test File: `dfo/tests/test_db.py`

```python
"""Tests for DuckDB layer."""
import pytest
from pathlib import Path
from dfo.db.duck import DuckDBManager, get_db, reset_db
from dfo.core.config import reset_settings

@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Create a test database."""
    db_file = tmp_path / "test.duckdb"
    monkeypatch.setenv("DFO_DUCKDB_FILE", str(db_file))
    monkeypatch.setenv("AZURE_TENANT_ID", "test")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test")

    # Reset singletons
    reset_settings()
    reset_db()

    db = get_db()
    db.initialize_schema()

    yield db

    db.close()
    reset_db()
    reset_settings()

def test_db_initialization(test_db):
    """Test database is initialized with schema."""
    assert test_db.table_exists("vm_inventory")
    assert test_db.table_exists("vm_idle_analysis")
    assert test_db.table_exists("vm_actions")

def test_db_file_creation(tmp_path, monkeypatch):
    """Test that database file is created."""
    db_file = tmp_path / "new_test.duckdb"
    monkeypatch.setenv("DFO_DUCKDB_FILE", str(db_file))
    monkeypatch.setenv("AZURE_TENANT_ID", "test")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test")

    reset_settings()
    reset_db()

    db = get_db()
    assert Path(db_file).exists()

    db.close()
    reset_db()

def test_insert_and_fetch(test_db):
    """Test inserting and fetching records."""
    records = [
        {
            "vm_id": "vm1",
            "name": "test-vm-1",
            "resource_group": "rg1",
            "location": "eastus",
            "size": "Standard_D2s_v3",
            "power_state": "running",
            "tags": "{}",
            "cpu_timeseries": "[]",
            "discovered_at": "2024-01-01 00:00:00"
        },
        {
            "vm_id": "vm2",
            "name": "test-vm-2",
            "resource_group": "rg1",
            "location": "westus",
            "size": "Standard_B2s",
            "power_state": "stopped",
            "tags": "{}",
            "cpu_timeseries": "[]",
            "discovered_at": "2024-01-01 00:00:00"
        }
    ]

    test_db.insert_records("vm_inventory", records)
    count = test_db.count_records("vm_inventory")
    assert count == 2

    results = test_db.fetch_all("SELECT * FROM vm_inventory ORDER BY name")
    assert len(results) == 2
    assert results[0][1] == "test-vm-1"  # name column

def test_clear_table(test_db):
    """Test clearing a table."""
    records = [
        {
            "vm_id": "vm1",
            "name": "test-vm",
            "resource_group": "rg1",
            "location": "eastus",
            "size": "Standard_D2s_v3",
            "power_state": "running",
            "tags": "{}",
            "cpu_timeseries": "[]",
            "discovered_at": "2024-01-01 00:00:00"
        }
    ]

    test_db.insert_records("vm_inventory", records)
    assert test_db.count_records("vm_inventory") == 1

    test_db.clear_table("vm_inventory")
    assert test_db.count_records("vm_inventory") == 0

def test_schema_refresh(test_db):
    """Test schema refresh with drop_existing."""
    # Insert some data
    records = [{
        "vm_id": "vm1",
        "name": "test-vm",
        "resource_group": "rg1",
        "location": "eastus",
        "size": "Standard_D2s_v3",
        "power_state": "running",
        "tags": "{}",
        "cpu_timeseries": "[]",
        "discovered_at": "2024-01-01 00:00:00"
    }]
    test_db.insert_records("vm_inventory", records)
    assert test_db.count_records("vm_inventory") == 1

    # Refresh schema (drop and recreate)
    test_db.initialize_schema(drop_existing=True)

    # Tables should exist but be empty
    assert test_db.table_exists("vm_inventory")
    assert test_db.count_records("vm_inventory") == 0

def test_singleton_pattern(test_db):
    """Test that DuckDBManager is a singleton."""
    db1 = get_db()
    db2 = get_db()
    assert db1 is db2

def test_empty_insert(test_db):
    """Test inserting empty list does nothing."""
    test_db.insert_records("vm_inventory", [])
    assert test_db.count_records("vm_inventory") == 0
```

#### Acceptance Criteria
- [x] DuckDB file is created at configured path
- [x] Schema can be initialized and refreshed
- [x] All three tables exist after init
- [x] Can insert and retrieve records
- [x] Singleton pattern works
- [x] All tests pass

---

### Task 4: Modular CLI Structure
**Priority:** MEDIUM (needed for testing)
**Dependencies:** Task 1 (config), Task 3 (db)
**Estimated Time:** 4-5 hours

#### Implementation Details

Create a modular CLI organization where each subcommand has its own file in `cmd/` directory, and the main CLI pulls them all together. All commands include comprehensive inline help.

**Code Style Requirements:**
- **NO business logic in CLI**: CLI only orchestrates (calls other layers)
- **One file per command group**: version.py, config.py, db.py, azure.py
- Each command function has comprehensive docstring with examples
- Use Rich console for output (not print() or logging)
- Functions use `snake_case` verbs: `version_command()`, `config_command()`
- All parameters have type hints and help text
- Module docstrings required for all cmd/*.py files
- Follow import order: stdlib → third-party → internal
- Fail fast with actionable errors
- Each file must be ≤ 250 lines
- Each function must be ≤ 40 lines

#### Directory Structure

```
dfo/
  cli.py                 # Main CLI entry point (pulls all commands together)
  cmd/                   # Subcommand modules
    __init__.py
    version.py          # Version command
    config.py           # Config command
    db.py               # Database commands (init, refresh, info)
    azure.py            # Azure commands (discover, analyze, report, execute)
  tests/
    test_cmd_version.py
    test_cmd_config.py
    test_cmd_db.py
    test_cmd_azure.py
    test_cli.py         # Main CLI integration tests
```

**File:** `dfo/cmd/__init__.py`

```python
"""CLI command modules."""
```

**File:** `dfo/cmd/version.py`

```python
"""Version command."""
import typer
from rich.console import Console

console = Console()

def version_command():
    """Show dfo version information."""
    from dfo import __version__
    console.print(f"[bold blue]dfo[/bold blue] version [green]{__version__}[/green]")
    console.print("DevFinOps - Multi-cloud FinOps optimization toolkit")
```

**File:** `dfo/cmd/config.py`

```python
"""Configuration command."""
import typer
from rich.console import Console
from rich.table import Table
from dfo.core.config import get_settings

console = Console()

def config_command(
    show_secrets: bool = typer.Option(
        False,
        "--show-secrets",
        help="Show secret values (credentials will be visible)"
    )
):
    """Display current configuration.

    Shows all configuration settings loaded from environment variables.
    By default, sensitive values (credentials) are masked with ***.
    Use --show-secrets to reveal actual values.

    Example:
        dfo config
        dfo config --show-secrets
    """
    try:
        settings = get_settings()

        table = Table(title="Configuration")
        table.add_column("Setting", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")

        # Azure settings (mask secrets by default)
        table.add_row("Azure Tenant ID", settings.azure_tenant_id if show_secrets else "***")
        table.add_row("Azure Client ID", settings.azure_client_id if show_secrets else "***")
        table.add_row("Azure Client Secret", settings.azure_client_secret if show_secrets else "***")
        table.add_row("Azure Subscription ID", settings.azure_subscription_id)

        # Analysis settings
        table.add_row("Idle CPU Threshold", f"{settings.dfo_idle_cpu_threshold}%")
        table.add_row("Idle Days", str(settings.dfo_idle_days))
        table.add_row("Dry Run Default", str(settings.dfo_dry_run_default))

        # Database settings
        table.add_row("DuckDB File", settings.dfo_duckdb_file)
        table.add_row("Log Level", settings.dfo_log_level)

        console.print(table)
        console.print("\n[green]✓[/green] Configuration loaded successfully")

    except Exception as e:
        console.print(f"[red]✗[/red] Error loading configuration: {e}")
        raise typer.Exit(1)
```

**File:** `dfo/cmd/db.py`

```python
"""Database management commands."""
import typer
from rich.console import Console
from rich.table import Table
from pathlib import Path
from dfo.db.duck import get_db

app = typer.Typer(help="Database management commands")
console = Console()

@app.command()
def init():
    """Initialize the database schema.

    Creates a new DuckDB database file and initializes all required tables:
    - vm_inventory: Stores discovered VM metadata and metrics
    - vm_idle_analysis: Stores analysis results for idle VMs
    - vm_actions: Logs all executed actions

    This command will fail if the database file already exists.
    Use 'dfo db refresh' to recreate existing tables.

    Example:
        dfo db init
    """
    try:
        db = get_db()
        db_path = Path(db.db_path)

        if db_path.exists():
            console.print(f"[yellow]![/yellow] Database already exists at {db.db_path}")
            console.print("[yellow]![/yellow] Use 'dfo db refresh' to recreate tables")
            raise typer.Exit(1)

        db.initialize_schema()
        console.print(f"[green]✓[/green] Database initialized at {db.db_path}")
        console.print("[green]✓[/green] Created tables: vm_inventory, vm_idle_analysis, vm_actions")

    except Exception as e:
        console.print(f"[red]✗[/red] Error initializing database: {e}")
        raise typer.Exit(1)

@app.command()
def refresh(
    yes: bool = typer.Option(
        False,
        "--yes", "-y",
        help="Skip confirmation prompt"
    )
):
    """Refresh database schema (drops and recreates all tables).

    WARNING: This will DELETE all existing data in the database.
    All tables will be dropped and recreated from schema.sql.

    This is useful for:
    - Resetting the database to a clean state
    - Applying schema changes during development
    - Clearing all data before a fresh discovery

    By default, this command requires confirmation.
    Use --yes to skip the confirmation prompt.

    Example:
        dfo db refresh
        dfo db refresh --yes
    """
    try:
        db = get_db()

        if not yes:
            confirm = typer.confirm(
                "⚠️  This will DROP all existing tables and data. Continue?",
                default=False
            )
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                raise typer.Exit(0)

        db.initialize_schema(drop_existing=True)
        console.print(f"[green]✓[/green] Database schema refreshed at {db.db_path}")
        console.print("[green]✓[/green] All tables recreated (data cleared)")

    except Exception as e:
        console.print(f"[red]✗[/red] Error refreshing database: {e}")
        raise typer.Exit(1)

@app.command()
def info():
    """Show database information and statistics.

    Displays:
    - Database file path and size
    - All tables with record counts
    - Overall database statistics

    This is useful for:
    - Verifying database initialization
    - Checking data volume
    - Monitoring database growth

    Example:
        dfo db info
    """
    try:
        db = get_db()
        db_path = Path(db.db_path)

        table = Table(title="Database Information")
        table.add_column("Table", style="cyan", no_wrap=True)
        table.add_column("Record Count", style="green", justify="right")

        tables = ["vm_inventory", "vm_idle_analysis", "vm_actions"]
        total_records = 0

        for table_name in tables:
            if db.table_exists(table_name):
                count = db.count_records(table_name)
                table.add_row(table_name, str(count))
                total_records += count
            else:
                table.add_row(table_name, "[red]Not found[/red]")

        console.print(table)
        console.print(f"\n[cyan]Database Path:[/cyan] {db.db_path}")

        if db_path.exists():
            size_mb = db_path.stat().st_size / (1024 * 1024)
            console.print(f"[cyan]Database Size:[/cyan] {size_mb:.2f} MB")
            console.print(f"[cyan]Total Records:[/cyan] {total_records:,}")
        else:
            console.print("[yellow]Database file not found - run 'dfo db init'[/yellow]")

    except Exception as e:
        console.print(f"[red]✗[/red] Error accessing database: {e}")
        raise typer.Exit(1)
```

**File:** `dfo/cmd/azure.py`

```python
"""Azure cloud provider commands."""
import typer
from rich.console import Console

app = typer.Typer(help="Azure cloud provider commands")
console = Console()

@app.command()
def discover(
    resource: str = typer.Argument(
        ...,
        help="Resource type to discover (e.g., 'vms')"
    )
):
    """Discover Azure resources and store in database.

    Connects to Azure and discovers resources, storing metadata and
    metrics in the local DuckDB database.

    Supported resource types:
    - vms: Virtual machines with CPU metrics

    This command will be implemented in Milestone 3.

    Example:
        dfo azure discover vms
    """
    console.print(f"[yellow]TODO:[/yellow] Discover Azure {resource}")
    console.print("This command will be implemented in Milestone 3")

@app.command()
def analyze(
    analysis_type: str = typer.Argument(
        ...,
        help="Analysis type (e.g., 'idle-vms')"
    )
):
    """Analyze Azure resources for optimization opportunities.

    Reads inventory data from the database and applies FinOps
    analysis to identify cost optimization opportunities.

    Supported analysis types:
    - idle-vms: Detect underutilized virtual machines

    This command will be implemented in Milestone 4.

    Example:
        dfo azure analyze idle-vms
    """
    console.print(f"[yellow]TODO:[/yellow] Analyze {analysis_type}")
    console.print("This command will be implemented in Milestone 4")

@app.command()
def report(
    report_type: str = typer.Argument(
        ...,
        help="Report type (e.g., 'idle-vms')"
    ),
    format: str = typer.Option(
        "console",
        "--format", "-f",
        help="Output format: console, json"
    ),
    output: str = typer.Option(
        None,
        "--output", "-o",
        help="Output file path (stdout if not specified)"
    )
):
    """Generate reports from analysis results.

    Reads analysis results from the database and generates
    formatted reports.

    Output formats:
    - console: Rich formatted table (default)
    - json: JSON output for integration

    This command will be implemented in Milestone 5.

    Example:
        dfo azure report idle-vms
        dfo azure report idle-vms --format json
        dfo azure report idle-vms --format json --output results.json
    """
    console.print(f"[yellow]TODO:[/yellow] Generate {report_type} report in {format} format")
    if output:
        console.print(f"[yellow]Output:[/yellow] {output}")
    console.print("This command will be implemented in Milestone 5")

@app.command()
def execute(
    action: str = typer.Argument(
        ...,
        help="Action to execute (e.g., 'stop-idle-vms')"
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="Dry run mode (no actual changes)"
    ),
    yes: bool = typer.Option(
        False,
        "--yes", "-y",
        help="Skip confirmation prompt"
    ),
    min_severity: str = typer.Option(
        "low",
        "--min-severity",
        help="Minimum severity level: low, medium, high, critical"
    )
):
    """Execute remediation actions on Azure resources.

    Executes optimization actions based on analysis results.

    Safety features:
    - Dry run mode enabled by default (use --no-dry-run for real execution)
    - Confirmation prompt required (use --yes to skip)
    - Severity filtering to control scope
    - All actions logged to vm_actions table

    Supported actions:
    - stop-idle-vms: Stop or deallocate idle virtual machines

    This command will be implemented in Milestone 6.

    Example:
        dfo azure execute stop-idle-vms
        dfo azure execute stop-idle-vms --dry-run=false --yes
        dfo azure execute stop-idle-vms --min-severity high
    """
    console.print(f"[yellow]TODO:[/yellow] Execute {action}")
    console.print(f"[yellow]Mode:[/yellow] {'DRY RUN' if dry_run else 'LIVE'}")
    console.print(f"[yellow]Min Severity:[/yellow] {min_severity}")
    console.print("This command will be implemented in Milestone 6")
```

**File:** `dfo/cli.py`

```python
"""Main CLI entry point - assembles all subcommands."""
import typer
from dfo.cmd import version, config, db, azure

# Create main app
app = typer.Typer(
    name="dfo",
    help="DevFinOps CLI - Multi-cloud FinOps optimization toolkit",
    add_completion=False,
    no_args_is_help=True
)

# Register top-level commands
app.command(name="version", help="Show version information")(version.version_command)
app.command(name="config", help="Display configuration")(config.config_command)

# Register subcommand groups
app.add_typer(db.app, name="db")
app.add_typer(azure.app, name="azure")

def run():
    """Entry point for the CLI."""
    app()

if __name__ == '__main__':
    run()
```

**Update:** `pyproject.toml`

```toml
[project.scripts]
dfo="dfo.cli:run"
```

#### Test Files

**File:** `dfo/tests/test_cmd_version.py`

```python
"""Tests for version command."""
from typer.testing import CliRunner
from dfo.cli import app

runner = CliRunner()

def test_version_command():
    """Test version command."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "dfo" in result.stdout
    assert "0.0.2" in result.stdout
    assert "DevFinOps" in result.stdout
```

**File:** `dfo/tests/test_cmd_config.py`

```python
"""Tests for config command."""
import pytest
from typer.testing import CliRunner
from dfo.cli import app
from dfo.core.config import reset_settings

runner = CliRunner()

@pytest.fixture
def setup_env(monkeypatch):
    """Setup test environment."""
    monkeypatch.setenv("DFO_DUCKDB_FILE", "test.duckdb")
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-sub")

    reset_settings()
    yield
    reset_settings()

def test_config_command(setup_env):
    """Test config command."""
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "Configuration" in result.stdout
    assert "***" in result.stdout  # secrets masked
    assert "test-sub" in result.stdout  # subscription visible

def test_config_show_secrets(setup_env):
    """Test config command with --show-secrets."""
    result = runner.invoke(app, ["config", "--show-secrets"])
    assert result.exit_code == 0
    assert "test-tenant" in result.stdout
    assert "test-client" in result.stdout
    assert "test-secret" in result.stdout
```

**File:** `dfo/tests/test_cmd_db.py`

```python
"""Tests for database commands."""
import pytest
from typer.testing import CliRunner
from pathlib import Path
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
    assert "already exists" in result.stdout.lower()

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
```

**File:** `dfo/tests/test_cmd_azure.py`

```python
"""Tests for Azure commands."""
import pytest
from typer.testing import CliRunner
from dfo.cli import app
from dfo.core.config import reset_settings

runner = CliRunner()

@pytest.fixture
def setup_env(monkeypatch):
    """Setup test environment."""
    monkeypatch.setenv("DFO_DUCKDB_FILE", "test.duckdb")
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-sub")

    reset_settings()
    yield
    reset_settings()

def test_azure_discover_stub(setup_env):
    """Test azure discover stub command."""
    result = runner.invoke(app, ["azure", "discover", "vms"])
    assert result.exit_code == 0
    assert "TODO" in result.stdout
    assert "Milestone 3" in result.stdout

def test_azure_analyze_stub(setup_env):
    """Test azure analyze stub command."""
    result = runner.invoke(app, ["azure", "analyze", "idle-vms"])
    assert result.exit_code == 0
    assert "TODO" in result.stdout
    assert "Milestone 4" in result.stdout

def test_azure_report_stub(setup_env):
    """Test azure report stub command."""
    result = runner.invoke(app, ["azure", "report", "idle-vms"])
    assert result.exit_code == 0
    assert "TODO" in result.stdout

def test_azure_report_with_format(setup_env):
    """Test azure report with format option."""
    result = runner.invoke(app, ["azure", "report", "idle-vms", "--format", "json"])
    assert result.exit_code == 0
    assert "json" in result.stdout.lower()

def test_azure_execute_stub(setup_env):
    """Test azure execute stub command."""
    result = runner.invoke(app, ["azure", "execute", "stop-idle-vms"])
    assert result.exit_code == 0
    assert "TODO" in result.stdout
    assert "DRY RUN" in result.stdout  # default dry run

def test_azure_execute_live_mode(setup_env):
    """Test azure execute with live mode."""
    result = runner.invoke(app, ["azure", "execute", "stop-idle-vms", "--no-dry-run"])
    assert result.exit_code == 0
    assert "LIVE" in result.stdout
```

**File:** `dfo/tests/test_cli.py`

```python
"""Integration tests for main CLI."""
import pytest
from typer.testing import CliRunner
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
        assert "help" in result.stdout.lower() or "usage" in result.stdout.lower()
```

#### Acceptance Criteria
- [x] Modular CLI structure with commands in separate files
- [x] `dfo --version` works
- [x] `dfo config` displays configuration (secrets masked)
- [x] `dfo db init` initializes database
- [x] `dfo db refresh` recreates schema with confirmation
- [x] `dfo db info` shows table counts
- [x] `dfo azure` shows discover/analyze/report/execute subcommands
- [x] All commands have comprehensive inline help
- [x] All commands have --help flag
- [x] All tests pass (one test file per command module)

---

## Task 5-8: Integration & Verification
**Priority:** HIGH
**Dependencies:** All previous tasks
**Estimated Time:** 2-3 hours

**Code Style Requirements for All Tasks:**
- All test files follow naming: `test_<module>.py` or `test_cmd_<command>.py`
- Test functions use descriptive names: `test_<what>_<scenario>()`
- Use fixtures for common setup
- Follow AAA pattern: Arrange, Act, Assert
- Each test file has module docstring
- Follow import order in tests too

### Task 5: Integration Testing

Create integration tests that test the full flow.

**File:** `dfo/tests/test_integration.py`

```python
"""Integration tests for Milestone 1."""
import pytest
from pathlib import Path
from dfo.core.config import get_settings, reset_settings
from dfo.db.duck import get_db, reset_db
from dfo.core.models import VMInventory

@pytest.fixture
def integration_env(tmp_path, monkeypatch):
    """Setup integration test environment."""
    db_file = tmp_path / "integration.duckdb"
    monkeypatch.setenv("DFO_DUCKDB_FILE", str(db_file))
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-sub")
    monkeypatch.setenv("DFO_IDLE_CPU_THRESHOLD", "10.0")

    reset_settings()
    reset_db()

    yield

    reset_db()
    reset_settings()

def test_full_setup_flow(integration_env):
    """Test full setup: config -> db init -> data insert."""
    # 1. Load configuration
    settings = get_settings()
    assert settings.azure_tenant_id == "test-tenant"
    assert settings.dfo_idle_cpu_threshold == 10.0

    # 2. Initialize database
    db = get_db()
    db.initialize_schema()

    # 3. Verify tables exist
    assert db.table_exists("vm_inventory")
    assert db.table_exists("vm_idle_analysis")
    assert db.table_exists("vm_actions")

    # 4. Insert test data using models
    inventory = VMInventory(
        vm_id="test-vm-1",
        name="integration-test-vm",
        resource_group="test-rg",
        location="eastus",
        size="Standard_D2s_v3",
        power_state="running",
        tags={"env": "test"},
        cpu_timeseries=[{"timestamp": "2024-01-01T00:00:00Z", "average": 5.0}]
    )

    db.insert_records("vm_inventory", [inventory.to_db_record()])

    # 5. Verify data inserted
    count = db.count_records("vm_inventory")
    assert count == 1

    results = db.fetch_all("SELECT name FROM vm_inventory")
    assert results[0][0] == "integration-test-vm"
```

### Task 6: Verify Exit Criteria

#### Verification Checklist

```bash
# 1. CLI Commands
dfo --version
# Expected: dfo version 0.0.2

dfo --help
# Expected: Shows all commands (version, config, db, azure)

dfo config
# Expected: Configuration table displayed

dfo db init
# Expected: Database initialized successfully

dfo db info
# Expected: Shows 3 tables with 0 records each

dfo db refresh --yes
# Expected: Schema refreshed

dfo azure
# Expected: Shows subcommands (discover, analyze, report, execute)

# 2. Test Suite
pytest dfo/tests/ -v
# Expected: All tests pass

pytest --cov=dfo dfo/tests/
# Expected: >80% coverage

# 3. Database Verification
ls -la dfo.duckdb
# Expected: File exists

# 4. Configuration
cat .env
# Expected: All required variables present
```

#### Acceptance Criteria
- [x] All CLI commands execute without errors
- [x] DuckDB file created with proper schema
- [x] All tests pass (config, models, db, cli, integration)
- [x] Test coverage >80%
- [x] Configuration loads from .env
- [x] Ready to begin Milestone 2

---

## Implementation Schedule

**Day 1 (Monday):**
- Task 1: Configuration management (2-3 hours)
- Task 2: Core data models (3-4 hours)
- Start tests for config and models

**Day 2 (Tuesday):**
- Task 3: DuckDB integration layer (4-5 hours)
- Complete tests for config and models
- Start tests for DuckDB

**Day 3 (Wednesday):**
- Task 4: CLI structure with db commands (3-4 hours)
- Complete tests for DuckDB
- Start tests for CLI

**Day 4 (Thursday):**
- Complete tests for CLI
- Task 5: Integration testing (2-3 hours)
- Address any test failures

**Day 5 (Friday):**
- Task 6: Verify all exit criteria
- Documentation review
- Buffer for any issues
- Prepare for Milestone 2

---

## Dependencies Graph

```
Task 1 (Config) ──┬──> Task 3 (DuckDB) ──┬──> Task 4 (CLI)
                  │                       │
Task 2 (Models) ──┴─────────────────────┴──> Tests

All Tasks ──────────────────────────────> Integration Tests

All Tests ──────────────────────────────> Verification
```

---

## Risk Mitigation

1. **DuckDB schema path issues:**
   - Use `Path(__file__).parent / "schema.sql"` for reliable path resolution
   - Test schema initialization thoroughly

2. **Pydantic v2 API changes:**
   - Use `pydantic-settings` package (separate from pydantic)
   - Use `model_config` instead of old `Config` class

3. **Environment variable loading:**
   - Test with both `.env` file and direct env vars
   - Ensure `.env` is in `.gitignore`

4. **Singleton reset for testing:**
   - Implement `reset_settings()` and `reset_db()` functions
   - Use in pytest fixtures

5. **CLI testing complexity:**
   - Use Typer's CliRunner for testing
   - Mock file I/O operations

---

## Success Metrics

- [x] All 4 main modules implemented (config, models, db, cli)
- [x] >80% test coverage across all modules
- [x] All CLI commands functional
- [x] Database can be initialized and refreshed
- [x] Zero errors in test suite
- [x] Configuration loads successfully from .env
- [x] Documentation is clear and complete
- [x] **All code passes CODE_STYLE.md review checklist**
- [x] **All files ≤ 250 lines**
- [x] **All functions ≤ 40 lines**
- [x] **No print() statements in modules**
- [x] **All functions have type hints**
- [x] **All error messages are actionable**
- [x] Ready for Milestone 2 implementation

---

## Deliverables Checklist

### Core Code Files
- [ ] `dfo/core/config.py` - Configuration management with Pydantic Settings
- [ ] `dfo/core/models.py` - Pydantic data models with enums
- [ ] `dfo/db/duck.py` - DuckDB integration layer
- [ ] `dfo/__init__.py` - Package version

### CLI Code Files
- [ ] `dfo/cli.py` - Main CLI entry point (pulls all commands together)
- [ ] `dfo/cmd/__init__.py` - Command modules package
- [ ] `dfo/cmd/version.py` - Version command
- [ ] `dfo/cmd/config.py` - Config command
- [ ] `dfo/cmd/db.py` - Database commands (init, refresh, info)
- [ ] `dfo/cmd/azure.py` - Azure commands (discover, analyze, report, execute stubs)

### Test Files
- [ ] `dfo/tests/test_config.py` - Config tests
- [ ] `dfo/tests/test_models.py` - Model tests
- [ ] `dfo/tests/test_db.py` - DuckDB tests
- [ ] `dfo/tests/test_cmd_version.py` - Version command tests
- [ ] `dfo/tests/test_cmd_config.py` - Config command tests
- [ ] `dfo/tests/test_cmd_db.py` - Database command tests
- [ ] `dfo/tests/test_cmd_azure.py` - Azure command tests
- [ ] `dfo/tests/test_cli.py` - Main CLI integration tests
- [ ] `dfo/tests/test_integration.py` - Integration tests

### CLI Commands
- [ ] `dfo --version` - Version info
- [ ] `dfo --help` - Help text
- [ ] `dfo config` - Show configuration
- [ ] `dfo db init` - Initialize database
- [ ] `dfo db refresh` - Refresh schema
- [ ] `dfo db info` - Show database info
- [ ] `dfo azure discover` - Stub
- [ ] `dfo azure analyze` - Stub
- [ ] `dfo azure report` - Stub
- [ ] `dfo azure execute` - Stub

### Documentation
- [ ] This plan document (MILESTONE_1_PLAN.md)
- [ ] Updated CLAUDE.md with Milestone 1 status
- [ ] CODE_STYLE.md compliance verified
- [ ] All module docstrings complete
- [ ] All function docstrings complete (Google/NumPy style)
- [ ] .env.example uses DFO_ prefix for custom variables

### Additional Deliverables
- [ ] All code reviewed against CODE_STYLE.md checklist
- [ ] No files exceed 250 lines
- [ ] No functions exceed 40 lines
- [ ] All imports follow stdlib → third-party → internal order
- [ ] No wildcard imports anywhere
- [ ] All error messages are actionable
