# Developer Onboarding Guide

**DFO (DevFinOps) - Rules-Driven Multi-Cloud FinOps Toolkit**

Version: 1.0
Last Updated: November 2024

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture Principles](#architecture-principles)
3. [Directory Structure](#directory-structure)
4. [Core Concepts](#core-concepts)
5. [Module Deep Dive](#module-deep-dive)
6. [Rules-Driven Architecture](#rules-driven-architecture)
7. [How to Extend the System](#how-to-extend-the-system)
8. [Development Workflow](#development-workflow)
9. [Testing Strategy](#testing-strategy)
10. [Common Patterns](#common-patterns)
11. [Troubleshooting](#troubleshooting)

---

## Project Overview

### What is DFO?

DFO is a CLI-based FinOps toolkit for multi-cloud cost optimization. It follows a modular pipeline architecture with DuckDB as the local storage backend.

**Key Features:**
- Rules-driven architecture (add analyses without code changes)
- Local-first (no external infrastructure required)
- Multi-cloud support (currently Azure, AWS/GCP planned)
- Self-documenting CLI
- Extensible optimization framework

### Pipeline Flow

```
┌──────┐    ┌──────────┐    ┌─────────┐    ┌────────┐    ┌─────────┐
│ Auth │───▶│ Discover │───▶│ Analyze │───▶│ Report │───▶│ Execute │
└──────┘    └──────────┘    └─────────┘    └────────┘    └─────────┘
                 │               │               │
                 ▼               ▼               ▼
            ┌──────────────────────────────────────┐
            │          DuckDB (Local DB)            │
            │  • vm_inventory                       │
            │  • vm_idle_analysis                   │
            │  • vm_actions                         │
            │  • vm_pricing_cache                   │
            └──────────────────────────────────────┘
```

**Important:** Stages never directly call each other. DuckDB is the shared state between stages.

---

## Architecture Principles

### 1. Modular Pipeline Design

Each stage is isolated, testable, and has a single responsibility:

| Stage | Responsibility | Writes To | Reads From |
|-------|---------------|-----------|------------|
| **auth** | Authenticate with cloud providers | Nothing | Config |
| **discover** | Collect raw inventory data | `vm_inventory` | Cloud APIs |
| **analyze** | Apply FinOps rules | `vm_idle_analysis` | `vm_inventory` |
| **report** | Generate outputs | Nothing | `vm_idle_analysis` |
| **execute** | Apply remediation actions | `vm_actions` | `vm_idle_analysis` |

### 2. Separation of Concerns

```python
# ❌ WRONG - Analysis calling cloud APIs directly
def analyze_idle_vms():
    vms = azure_client.list_vms()  # NO!

# ✅ RIGHT - Analysis reads from database
def analyze_idle_vms():
    db = get_db()
    vms = db.query("SELECT * FROM vm_inventory")  # YES!
```

### 3. Configuration-Driven

All behavior is controlled through:
- `optimization_rules.json` - Rules definitions
- `.env` / environment variables - Runtime config
- DuckDB tables - Persistent state

### 4. Type Safety

All data crossing layer boundaries uses Pydantic models:

```python
# Core models in src/dfo/core/models.py
class VMInventory(BaseModel):
    vm_id: str
    name: str
    size: str
    # ...

# Convert to dict for DuckDB
vm_record = vm_inventory.to_db_record()
```

---

## Directory Structure

```
dfo/
├── src/dfo/
│   ├── cli.py                    # Main CLI entry point (assembles commands)
│   │
│   ├── cmd/                      # CLI command modules (modular)
│   │   ├── version.py           # Version command
│   │   ├── config.py            # Config command
│   │   ├── db.py                # Database management
│   │   ├── azure.py             # Azure commands (discover, analyze, etc.)
│   │   └── rules.py             # Rules management commands
│   │
│   ├── core/                    # Foundation layer
│   │   ├── config.py           # Settings (Pydantic)
│   │   ├── auth.py             # Cloud authentication
│   │   └── models.py           # Shared data models
│   │
│   ├── providers/              # Cloud SDK integrations
│   │   └── azure/
│   │       ├── client.py      # Azure client factory
│   │       ├── compute.py     # VM operations
│   │       ├── monitor.py     # Metrics retrieval
│   │       ├── pricing.py     # Cost estimation
│   │       ├── advisor.py     # Advisor recommendations
│   │       └── resource_graph.py  # Multi-resource queries
│   │
│   ├── discover/               # Inventory building
│   │   └── vms.py             # VM discovery (writes to vm_inventory)
│   │
│   ├── analyze/                # FinOps analysis logic
│   │   ├── idle_vms.py        # Idle VM detection
│   │   └── compute_mapper.py  # SKU equivalence mapping
│   │
│   ├── report/                 # Output generation
│   │   ├── console.py         # Rich console output
│   │   └── json_report.py     # JSON export
│   │
│   ├── execute/                # Remediation actions
│   │   └── stop_vms.py        # Stop/deallocate VMs
│   │
│   ├── inventory/              # Inventory queries
│   │   ├── queries.py         # Advanced filtering
│   │   └── formatters.py      # Export formatters
│   │
│   ├── db/                     # DuckDB layer
│   │   ├── duck.py            # DuckDB manager
│   │   ├── schema.sql         # Table definitions
│   │   └── init_data.sql      # Initial data
│   │
│   ├── rules/                  # Rules engine
│   │   ├── __init__.py        # RuleEngine class
│   │   ├── optimization_rules.json  # 29 optimization rules
│   │   └── vm_rules.json      # Legacy (deprecated)
│   │
│   ├── common/                 # Shared utilities
│   │   └── visualizations.py  # Rich visualizations
│   │
│   └── tests/                  # Test suite
│       ├── conftest.py        # Shared fixtures
│       └── test_*.py          # Test files (1 per module)
│
├── docs/                       # Documentation
│   ├── MVP.md                 # MVP milestones
│   ├── CODE_STYLE.md          # Coding standards
│   ├── rules_driven_cli.md    # Rules architecture
│   └── DEVELOPER_ONBOARDING.md  # This file
│
├── .env.example               # Environment template
├── environment.yml            # Conda environment
└── pyproject.toml            # Project metadata
```

---

## Core Concepts

### 1. Rules-Driven Architecture

**The rules file is the single source of truth for CLI commands.**

Every analysis type available in the CLI corresponds to a rule in `optimization_rules.json`.

**Example Rule:**

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

**How it works:**

1. User runs: `./dfo azure analyze idle-vms`
2. CLI looks up rule by key: `rule = rule_engine.get_rule_by_key("idle-vms")`
3. Validates rule is enabled and has module
4. Dynamically imports: `importlib.import_module("dfo.analyze.idle_vms")`
5. Calls analysis function: `module.analyze_idle_vms(...)`
6. Displays results

### 2. DuckDB as Central State

DuckDB is a lightweight, embedded SQL database. It serves as the communication layer between stages.

**Key Tables:**

```sql
-- Raw discovery data
CREATE TABLE vm_inventory (
    vm_id TEXT PRIMARY KEY,
    name TEXT,
    resource_group TEXT,
    location TEXT,
    size TEXT,
    power_state TEXT,
    os_type TEXT,
    priority TEXT,
    cpu_timeseries JSON,  -- Array of {timestamp, average}
    discovered_at TIMESTAMP,
    subscription_id TEXT,
    tags JSON
);

-- Analysis results
CREATE TABLE vm_idle_analysis (
    vm_id TEXT PRIMARY KEY,
    cpu_avg DOUBLE,
    days_under_threshold INTEGER,
    estimated_monthly_savings DOUBLE,
    severity TEXT,
    recommended_action TEXT,
    equivalent_sku TEXT,
    analyzed_at TIMESTAMP
);

-- Execution log
CREATE TABLE vm_actions (
    action_id INTEGER PRIMARY KEY,
    vm_id TEXT,
    action_type TEXT,
    status TEXT,
    dry_run BOOLEAN,
    executed_at TIMESTAMP,
    notes TEXT
);

-- Pricing cache
CREATE TABLE vm_pricing_cache (
    vm_size TEXT,
    region TEXT,
    os_type TEXT,
    hourly_price DOUBLE,
    currency TEXT,
    cached_at TIMESTAMP,
    PRIMARY KEY (vm_size, region, os_type)
);
```

### 3. Layer Responsibilities

**Never violate these boundaries:**

| Layer | Must Do | Must NOT Do |
|-------|---------|-------------|
| `core` | Config, auth, models | No provider calls, no DB writes |
| `providers` | Call cloud SDKs only | No analysis, no DB writes |
| `discover` | Collect raw data → DuckDB | No analysis logic |
| `analyze` | Pure FinOps logic | No cloud calls, no DB writes directly |
| `report` | Render outputs | No analysis, no cloud calls |
| `execute` | Apply actions → DuckDB | No discovery |
| `db` | Read/write DuckDB only | No cloud logic, no analysis |
| `cli/cmd` | Orchestrate commands | No business logic |

---

## Module Deep Dive

### 1. Core Layer (`src/dfo/core/`)

#### **config.py** - Configuration Management

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Azure credentials
    azure_tenant_id: str
    azure_client_id: str
    azure_client_secret: str
    azure_subscription_id: str

    # DFO settings
    dfo_idle_cpu_threshold: float = 5.0
    dfo_idle_days: int = 14
    dfo_duckdb_file: str = "./dfo.duckdb"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Singleton pattern
_settings_instance = None

def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
```

**Usage:**
```python
from dfo.core.config import get_settings

settings = get_settings()
threshold = settings.dfo_idle_cpu_threshold
```

#### **auth.py** - Cloud Authentication

```python
from azure.identity import DefaultAzureCredential, ClientSecretCredential

def get_cached_credential():
    """Get Azure credential with service principal fallback."""
    settings = get_settings()

    # Try service principal first
    if all([settings.azure_tenant_id, settings.azure_client_id,
            settings.azure_client_secret]):
        return ClientSecretCredential(
            tenant_id=settings.azure_tenant_id,
            client_id=settings.azure_client_id,
            client_secret=settings.azure_client_secret
        )

    # Fallback to DefaultAzureCredential (uses Azure CLI, managed identity, etc.)
    return DefaultAzureCredential()
```

#### **models.py** - Data Models

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, List

class VMInventory(BaseModel):
    vm_id: str
    name: str
    resource_group: str
    location: str
    size: str
    power_state: str
    os_type: str
    priority: str
    cpu_timeseries: Optional[List[Dict]] = None
    discovered_at: datetime
    subscription_id: str
    tags: Dict[str, str] = {}

    def to_db_record(self) -> tuple:
        """Convert to tuple for DuckDB insertion."""
        import json
        return (
            self.vm_id,
            self.name,
            self.resource_group,
            self.location,
            self.size,
            self.power_state,
            self.os_type,
            self.priority,
            json.dumps(self.cpu_timeseries) if self.cpu_timeseries else None,
            self.discovered_at,
            self.subscription_id,
            json.dumps(self.tags)
        )
```

### 2. Providers Layer (`src/dfo/providers/azure/`)

#### **client.py** - Client Factory

```python
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.monitor import MonitorManagementClient

# Singleton cache
_client_cache = {}

def get_compute_client(subscription_id: str = None) -> ComputeManagementClient:
    """Get cached compute client."""
    settings = get_settings()
    sub_id = subscription_id or settings.azure_subscription_id

    cache_key = f"compute_{sub_id}"
    if cache_key not in _client_cache:
        credential = get_cached_credential()
        _client_cache[cache_key] = ComputeManagementClient(credential, sub_id)

    return _client_cache[cache_key]
```

#### **compute.py** - VM Operations

```python
def list_vms(subscription_id: str = None) -> List[Dict]:
    """List all VMs in subscription."""
    client = get_compute_client(subscription_id)
    vms = []

    for vm in client.virtual_machines.list_all():
        # Get instance view for power state
        instance_view = client.virtual_machines.instance_view(
            resource_group_name=vm.id.split('/')[4],
            vm_name=vm.name
        )

        power_state = "unknown"
        if instance_view.statuses:
            for status in instance_view.statuses:
                if status.code.startswith('PowerState/'):
                    power_state = status.code.split('/')[-1]

        vms.append({
            "vm_id": vm.id,
            "name": vm.name,
            "resource_group": vm.id.split('/')[4],
            "location": vm.location,
            "size": vm.hardware_profile.vm_size,
            "power_state": power_state,
            "os_type": vm.storage_profile.os_disk.os_type,
            "priority": vm.priority or "Regular",
            "tags": vm.tags or {}
        })

    return vms
```

#### **monitor.py** - Metrics Retrieval

```python
def get_cpu_metrics(vm_id: str, days: int = 7) -> List[Dict]:
    """Get CPU metrics for a VM."""
    from datetime import datetime, timedelta, timezone

    client = get_monitor_client()

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=days)

    metrics = client.metrics.list(
        resource_uri=vm_id,
        timespan=f"{start_time.isoformat()}/{end_time.isoformat()}",
        interval='PT1H',
        metricnames='Percentage CPU',
        aggregation='Average'
    )

    cpu_data = []
    for item in metrics.value:
        for timeseries in item.timeseries:
            for data_point in timeseries.data:
                if data_point.average is not None:
                    cpu_data.append({
                        "timestamp": data_point.time_stamp.isoformat(),
                        "average": data_point.average
                    })

    return cpu_data
```

#### **pricing.py** - Cost Estimation

```python
def get_vm_monthly_cost_with_metadata(
    vm_size: str,
    region: str,
    os_type: str = "Linux",
    use_cache: bool = True
) -> dict:
    """Get VM monthly cost with metadata.

    Returns:
        {
            "monthly_cost": float,
            "equivalent_sku": str | None,
            "hourly_price": float
        }
    """
    # Check cache first
    if use_cache:
        hourly_price = _get_cached_price(vm_size, region, os_type)
        if hourly_price:
            return {
                "monthly_cost": hourly_price * 730,
                "equivalent_sku": None,
                "hourly_price": hourly_price
            }

    # Fetch from Azure Retail Prices API
    hourly_price = fetch_vm_price(vm_size, region, os_type)

    # Try equivalent SKU if not found
    equivalent_sku = None
    if not hourly_price:
        equivalent_sku = resolve_equivalent_sku(vm_size)
        if equivalent_sku:
            hourly_price = fetch_vm_price(equivalent_sku, region, os_type)

    # Cache result
    if hourly_price:
        _cache_price(vm_size, region, os_type, hourly_price)

    return {
        "monthly_cost": hourly_price * 730 if hourly_price else 0.0,
        "equivalent_sku": equivalent_sku,
        "hourly_price": hourly_price or 0.0
    }
```

### 3. Discover Layer (`src/dfo/discover/`)

#### **vms.py** - VM Discovery

```python
def discover_vms(
    subscription_id: str = None,
    refresh: bool = True,
    days: int = None
) -> int:
    """Discover VMs and store in database.

    Args:
        subscription_id: Azure subscription ID
        refresh: Clear existing data before discovery
        days: Days of CPU metrics to collect

    Returns:
        Number of VMs discovered
    """
    from dfo.providers.azure.compute import list_vms
    from dfo.providers.azure.monitor import get_cpu_metrics
    from dfo.db.duck import get_db
    from dfo.core.config import get_settings

    settings = get_settings()
    db = get_db()

    # Determine days from rule or config
    if days is None:
        rule_engine = get_rule_engine()
        idle_rule = rule_engine.get_rule_by_type("Idle VM Detection")
        days = int(idle_rule.period.replace('d', '')) if idle_rule else settings.dfo_idle_days

    # Clear existing data if refresh
    if refresh:
        db.execute_query("DELETE FROM vm_inventory")

    # Discover VMs
    vms = list_vms(subscription_id)

    for vm in vms:
        # Get CPU metrics
        cpu_metrics = get_cpu_metrics(vm["vm_id"], days=days)

        # Insert into database
        db.execute_query(
            """
            INSERT INTO vm_inventory
            (vm_id, name, resource_group, location, size, power_state,
             os_type, priority, cpu_timeseries, discovered_at, subscription_id, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                vm["vm_id"],
                vm["name"],
                vm["resource_group"],
                vm["location"],
                vm["size"],
                vm["power_state"],
                vm["os_type"],
                vm["priority"],
                json.dumps(cpu_metrics),
                datetime.now(timezone.utc),
                subscription_id or settings.azure_subscription_id,
                json.dumps(vm["tags"])
            )
        )

    return len(vms)
```

### 4. Analyze Layer (`src/dfo/analyze/`)

#### **idle_vms.py** - Idle VM Detection

```python
def analyze_idle_vms(threshold: float = None, min_days: int = None) -> int:
    """Analyze VMs for idle status.

    Algorithm:
        1. Read VMs from vm_inventory
        2. For each VM with CPU metrics:
           a. Calculate average CPU usage
           b. Count days below threshold
           c. Check if meets minimum days requirement
           d. Calculate estimated monthly savings
           e. Determine severity level
           f. Generate recommended action
        3. Store results in vm_idle_analysis
        4. Return count of idle VMs found

    Args:
        threshold: CPU threshold percentage (default: from config)
        min_days: Minimum days below threshold (default: from config)

    Returns:
        Number of idle VMs identified
    """
    from dfo.db.duck import get_db
    from dfo.core.config import get_settings
    from dfo.providers.azure.pricing import get_vm_monthly_cost_with_metadata

    settings = get_settings()
    db = get_db()

    # Use config defaults if not provided
    threshold = threshold if threshold is not None else settings.dfo_idle_cpu_threshold
    min_days = min_days if min_days is not None else settings.dfo_idle_days

    # Clear previous analysis
    db.execute_query("DELETE FROM vm_idle_analysis")

    # Get VMs with CPU metrics
    vms = db.query(
        """
        SELECT vm_id, name, resource_group, location, size, power_state,
               os_type, priority, cpu_timeseries
        FROM vm_inventory
        WHERE cpu_timeseries IS NOT NULL
          AND power_state = 'running'
        """
    )

    idle_count = 0

    for vm in vms:
        vm_id, name, rg, location, size, state, os_type, priority, cpu_json = vm

        # Parse CPU timeseries
        cpu_timeseries = json.loads(cpu_json) if cpu_json else []

        # Analyze CPU usage
        result = analyze_vm_cpu(cpu_timeseries, threshold, min_days)

        if result["is_idle"]:
            idle_count += 1

            # Get pricing info
            pricing_info = get_vm_monthly_cost_with_metadata(
                vm_size=size,
                region=location,
                os_type=os_type
            )

            # Calculate savings
            monthly_cost = pricing_info["monthly_cost"]
            action = determine_action(result["cpu_avg"], monthly_cost)
            savings = calculate_savings(monthly_cost, action)
            severity = determine_severity(result["cpu_avg"], result["days_under"])

            # Store result
            db.execute_query(
                """
                INSERT INTO vm_idle_analysis
                (vm_id, cpu_avg, days_under_threshold, estimated_monthly_savings,
                 severity, recommended_action, equivalent_sku, analyzed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    vm_id,
                    result["cpu_avg"],
                    result["days_under"],
                    savings,
                    severity,
                    action,
                    pricing_info["equivalent_sku"],
                    datetime.now(timezone.utc)
                )
            )

    return idle_count


def analyze_vm_cpu(
    cpu_timeseries: List[Dict],
    threshold: float,
    min_days: int
) -> Dict:
    """Analyze CPU timeseries for a single VM.

    Returns:
        {
            "is_idle": bool,
            "cpu_avg": float,
            "days_under": int
        }
    """
    if not cpu_timeseries:
        return {"is_idle": False, "cpu_avg": 0.0, "days_under": 0}

    # Calculate average CPU
    total_cpu = sum(point["average"] for point in cpu_timeseries)
    cpu_avg = total_cpu / len(cpu_timeseries)

    # Count days below threshold
    from datetime import datetime
    from collections import defaultdict

    days_below = defaultdict(bool)
    for point in cpu_timeseries:
        timestamp = datetime.fromisoformat(point["timestamp"].replace('Z', '+00:00'))
        day_key = timestamp.date()

        if point["average"] < threshold:
            days_below[day_key] = True

    days_under_threshold = len(days_below)

    is_idle = days_under_threshold >= min_days

    return {
        "is_idle": is_idle,
        "cpu_avg": cpu_avg,
        "days_under": days_under_threshold
    }


def determine_action(cpu_avg: float, monthly_cost: float) -> str:
    """Determine recommended action based on CPU and cost."""
    if cpu_avg < 1.0:
        return "Delete"
    elif cpu_avg < 3.0:
        return "Deallocate"
    else:
        return "Downsize"


def calculate_savings(monthly_cost: float, action: str) -> float:
    """Calculate estimated monthly savings."""
    if action == "Delete":
        return monthly_cost
    elif action == "Deallocate":
        return monthly_cost * 0.75  # Save 75% (storage costs remain)
    else:  # Downsize
        return monthly_cost * 0.50  # Save 50% (estimate)


def determine_severity(cpu_avg: float, days_under: int) -> str:
    """Determine severity level."""
    if cpu_avg < 1.0 and days_under >= 30:
        return "Critical"
    elif cpu_avg < 2.0 and days_under >= 21:
        return "High"
    elif cpu_avg < 3.0 and days_under >= 14:
        return "Medium"
    else:
        return "Low"


def get_idle_vms(
    severity: str = None,
    limit: int = None
) -> List[Dict]:
    """Get idle VMs from analysis results.

    Returns list of dicts with VM details and analysis results.
    """
    from dfo.db.duck import get_db

    db = get_db()

    query = """
        SELECT
            i.name,
            i.resource_group,
            i.location,
            i.size,
            i.power_state,
            a.cpu_avg,
            a.days_under_threshold,
            a.estimated_monthly_savings,
            a.severity,
            a.recommended_action,
            a.equivalent_sku,
            a.analyzed_at
        FROM vm_idle_analysis a
        JOIN vm_inventory i ON a.vm_id = i.vm_id
    """

    params = []

    if severity:
        query += " WHERE a.severity = ?"
        params.append(severity)

    query += " ORDER BY a.estimated_monthly_savings DESC"

    if limit:
        query += f" LIMIT {limit}"

    results = db.query(query, tuple(params) if params else None)

    # Convert to list of dicts
    return [
        {
            "name": row[0],
            "resource_group": row[1],
            "location": row[2],
            "size": row[3],
            "power_state": row[4],
            "cpu_avg": row[5],
            "days_under_threshold": row[6],
            "estimated_monthly_savings": row[7],
            "severity": row[8],
            "recommended_action": row[9],
            "equivalent_sku": row[10],
            "analyzed_at": row[11]
        }
        for row in results
    ]


def get_idle_vm_summary() -> Dict:
    """Get summary statistics for idle VMs."""
    from dfo.db.duck import get_db

    db = get_db()

    # Overall stats
    overall = db.query(
        """
        SELECT
            COUNT(*) as total_vms,
            COALESCE(SUM(estimated_monthly_savings), 0) as total_savings
        FROM vm_idle_analysis
        """
    )

    # By severity
    by_severity = {}
    severity_rows = db.query(
        """
        SELECT severity, COUNT(*), SUM(estimated_monthly_savings)
        FROM vm_idle_analysis
        GROUP BY severity
        ORDER BY
            CASE severity
                WHEN 'Critical' THEN 1
                WHEN 'High' THEN 2
                WHEN 'Medium' THEN 3
                WHEN 'Low' THEN 4
            END
        """
    )
    for row in severity_rows:
        by_severity[row[0]] = {
            "count": row[1],
            "savings": row[2]
        }

    # By action
    by_action = {}
    action_rows = db.query(
        """
        SELECT recommended_action, COUNT(*), SUM(estimated_monthly_savings)
        FROM vm_idle_analysis
        GROUP BY recommended_action
        ORDER BY SUM(estimated_monthly_savings) DESC
        """
    )
    for row in action_rows:
        by_action[row[0]] = {
            "count": row[1],
            "savings": row[2]
        }

    return {
        "total_idle_vms": overall[0][0] if overall else 0,
        "total_potential_savings": overall[0][1] if overall else 0.0,
        "by_severity": by_severity,
        "by_action": by_action
    }
```

### 5. Rules Layer (`src/dfo/rules/`)

#### **__init__.py** - RuleEngine

```python
class RuleEngine:
    """Engine for loading and managing optimization rules."""

    def __init__(self, rules_file: str = "optimization_rules.json"):
        """Initialize rule engine."""
        rules_path = Path(__file__).parent / rules_file
        self.rules_path = rules_path
        self._rules = []
        self._load_rules()
        self._apply_config_overrides()

    def _load_rules(self):
        """Load rules from JSON file."""
        with open(self.rules_path) as f:
            data = json.load(f)
            for rule_data in data.get("optimizations", []):
                self._rules.append(OptimizationRule(**rule_data))

    def _apply_config_overrides(self):
        """Apply environment-based rule overrides."""
        settings = get_settings()

        # Disable rules via DFO_DISABLE_RULES env var
        disabled_rules = settings.dfo_disable_rules.split(',')
        for rule in self._rules:
            if rule.type in disabled_rules:
                rule.enabled = False

    def get_all_rules(self) -> List[OptimizationRule]:
        """Get all rules."""
        return self._rules

    def get_rule_by_key(self, key: str) -> Optional[OptimizationRule]:
        """Look up a rule by CLI key."""
        for rule in self._rules:
            if rule.key == key:
                return rule
        return None

    def get_rule_by_type(self, type_name: str) -> Optional[OptimizationRule]:
        """Look up a rule by type name."""
        for rule in self._rules:
            if rule.type == type_name:
                return rule
        return None

    def get_available_analyses(self, provider: str = "azure") -> List[Dict]:
        """Get all available analysis modules with metadata."""
        analyses = []
        for rule in self._rules:
            if not rule.key or not rule.module:
                continue

            if provider and provider not in rule.providers:
                continue

            analyses.append({
                "key": rule.key,
                "type": rule.type,
                "category": rule.category,
                "description": rule.description,
                "enabled": rule.enabled,
                "module": rule.module,
                "actions": rule.actions,
                "export_formats": rule.export_formats
            })

        return analyses

    def get_categories(self) -> List[str]:
        """Get all unique categories."""
        categories = set()
        for rule in self._rules:
            if rule.category:
                categories.add(rule.category)
        return sorted(categories)


# Singleton pattern
_rule_engine = None

def get_rule_engine() -> RuleEngine:
    """Get singleton RuleEngine instance."""
    global _rule_engine
    if _rule_engine is None:
        _rule_engine = RuleEngine()
    return _rule_engine
```

### 6. CLI Layer (`src/dfo/cmd/`)

#### **azure.py** - Analyze Command (Rules-Driven)

```python
@app.command("analyze")
def analyze(
    analysis_type: str = typer.Argument(
        None,
        help="Analysis type (e.g., 'idle-vms'). Use --list to see all."
    ),
    list_analyses: bool = typer.Option(
        False,
        "--list",
        help="List all available analysis types"
    ),
    threshold: float = typer.Option(
        None,
        "--threshold",
        help="CPU threshold percentage"
    ),
    min_days: int = typer.Option(
        None,
        "--min-days",
        help="Minimum days of data required"
    )
):
    """Analyze Azure resources for optimization opportunities.

    Reads inventory data from the database and applies FinOps
    analysis to identify cost optimization opportunities.

    Analysis types are defined in optimization_rules.json.
    """
    from dfo.rules import get_rule_engine

    rule_engine = get_rule_engine()

    # Handle --list flag
    if list_analyses:
        _show_available_analyses(rule_engine)
        return

    # Validate analysis_type provided
    if not analysis_type:
        console.print("[red]Error:[/red] Analysis type is required")
        console.print("Use [cyan]dfo azure analyze --list[/cyan] to see available analyses")
        raise typer.Exit(1)

    # Look up the rule by key
    rule = rule_engine.get_rule_by_key(analysis_type)
    if not rule:
        console.print(f"[red]Error:[/red] Unknown analysis type: {analysis_type}")
        console.print("Use [cyan]dfo azure analyze --list[/cyan] to see available analyses")
        raise typer.Exit(1)

    # Check if rule is enabled
    if not rule.enabled:
        console.print(f"[yellow]Warning:[/yellow] Analysis type '{analysis_type}' is disabled")
        console.print("Enable it in optimization_rules.json or via environment config")
        raise typer.Exit(1)

    # Check if module is specified
    if not rule.module:
        console.print(f"[red]Error:[/red] No module specified for: {analysis_type}")
        raise typer.Exit(1)

    # Dynamically import the analysis module
    try:
        import importlib

        module_name = f"dfo.analyze.{rule.module}"
        analysis_module = importlib.import_module(module_name)

    except ImportError:
        console.print(f"[red]Error:[/red] Cannot import module: {module_name}")
        console.print(f"Module file should be: src/dfo/analyze/{rule.module}.py")
        raise typer.Exit(1)

    # Get settings for defaults
    settings = get_settings()
    cpu_threshold = threshold if threshold is not None else settings.dfo_idle_cpu_threshold
    required_days = min_days if min_days is not None else settings.dfo_idle_days

    # Display configuration
    console.print(f"\n[cyan]Starting {rule.type}...[/cyan]")
    console.print(f"[dim]CPU threshold:[/dim] {cpu_threshold}%")
    console.print(f"[dim]Minimum days:[/dim] {required_days}\n")

    # Run analysis
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task(f"Running {rule.type}...", total=None)

        # Call the analyze function from the dynamically imported module
        idle_count = analysis_module.analyze_idle_vms(
            threshold=cpu_threshold,
            min_days=required_days
        )

        progress.update(task, description="✓ Analysis complete")

    # Display results
    if idle_count == 0:
        console.print(f"\n[green]✓[/green] No issues detected by {rule.type}")
        console.print("[dim]All resources are being utilized efficiently.[/dim]\n")
        return

    # Get summary and display details
    summary = analysis_module.get_idle_vm_summary()

    # ... display logic ...
```

---

## Rules-Driven Architecture

### How Analysis Commands Work

```
User Command
     │
     ▼
./dfo azure analyze idle-vms
     │
     ▼
┌─────────────────────────────────────┐
│  CLI (cmd/azure.py)                 │
│  1. Parse command                   │
│  2. rule_engine.get_rule_by_key()   │
└──────────────┬──────────────────────┘
               ▼
┌─────────────────────────────────────┐
│  RuleEngine (rules/__init__.py)     │
│  1. Find rule in JSON               │
│  2. Validate enabled status         │
│  3. Return rule object              │
└──────────────┬──────────────────────┘
               ▼
┌─────────────────────────────────────┐
│  Dynamic Import                      │
│  importlib.import_module(           │
│    f"dfo.analyze.{rule.module}"     │
│  )                                   │
└──────────────┬──────────────────────┘
               ▼
┌─────────────────────────────────────┐
│  Analysis Module                     │
│  (analyze/idle_vms.py)              │
│  1. Read from vm_inventory          │
│  2. Apply analysis logic            │
│  3. Write to vm_idle_analysis       │
│  4. Return count                    │
└──────────────┬──────────────────────┘
               ▼
┌─────────────────────────────────────┐
│  Display Results                     │
│  1. Get summary statistics          │
│  2. Format with Rich                │
│  3. Show to user                    │
└─────────────────────────────────────┘
```

### Adding a New Analysis

**You only need to do 3 things:**

#### Step 1: Create Analysis Module

Create `src/dfo/analyze/rightsize_memory.py`:

```python
"""Memory-based rightsizing analysis."""
import logging
from typing import Dict, List
from datetime import datetime, timezone
from dfo.db.duck import get_db
from dfo.core.config import get_settings

logger = logging.getLogger(__name__)


def analyze_rightsize_memory(threshold: float = None, min_days: int = None) -> int:
    """Identify VMs with low memory utilization.

    Args:
        threshold: Memory threshold percentage
        min_days: Minimum days below threshold

    Returns:
        Number of VMs identified for rightsizing
    """
    settings = get_settings()
    db = get_db()

    threshold = threshold if threshold is not None else 30.0  # Default 30%
    min_days = min_days if min_days is not None else settings.dfo_idle_days

    # Clear previous analysis
    db.execute_query("DELETE FROM vm_memory_analysis")

    # Get VMs with memory metrics
    vms = db.query(
        """
        SELECT vm_id, name, size, memory_timeseries
        FROM vm_inventory
        WHERE memory_timeseries IS NOT NULL
        """
    )

    rightsize_count = 0

    for vm in vms:
        # Analyze memory usage
        # Calculate recommendations
        # Store results
        # ...
        rightsize_count += 1

    return rightsize_count


def get_rightsize_memory_summary() -> Dict:
    """Get summary statistics."""
    db = get_db()

    results = db.query(
        "SELECT COUNT(*), SUM(estimated_savings) FROM vm_memory_analysis"
    )

    return {
        "total_vms": results[0][0] if results else 0,
        "total_savings": results[0][1] if results else 0.0
    }
```

#### Step 2: Add Rule to JSON

Add to `src/dfo/rules/optimization_rules.json`:

```json
{
  "service_type": "vm",
  "layer": 1,
  "sub_layer": "Self-Contained VM",
  "type": "Right-Sizing (Memory)",
  "key": "rightsize-memory",
  "category": "compute",
  "description": "Identify VMs with consistently low memory utilization for downsizing",
  "module": "rightsize_memory",
  "metric": "Memory utilization",
  "threshold": "<30%",
  "period": "14d",
  "unit": "percent",
  "enabled": true,
  "actions": ["resize", "report"],
  "export_formats": ["csv", "json"],
  "providers": {
    "azure": "Azure Monitor: Memory Percent Used",
    "aws": "AWS: mem_used_percent",
    "gcp": "GCP: memory/percent_used"
  }
}
```

#### Step 3: Test

```bash
# Verify it appears in the list
./dfo azure analyze --list

# Run the analysis
./dfo azure analyze rightsize-memory

# With custom parameters
./dfo azure analyze rightsize-memory --threshold 20.0 --min-days 7
```

**That's it!** No CLI code changes needed.

---

## How to Extend the System

### 1. Add a New Cloud Provider (AWS)

#### Create Provider Module

```bash
mkdir -p src/dfo/providers/aws
```

Create `src/dfo/providers/aws/compute.py`:

```python
"""AWS EC2 compute operations."""
import boto3
from typing import List, Dict

def get_ec2_client(region: str = "us-east-1"):
    """Get EC2 client."""
    return boto3.client('ec2', region_name=region)


def list_instances(region: str = None) -> List[Dict]:
    """List all EC2 instances."""
    client = get_ec2_client(region)

    response = client.describe_instances()

    instances = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instances.append({
                "instance_id": instance['InstanceId'],
                "name": _get_tag(instance, 'Name'),
                "instance_type": instance['InstanceType'],
                "state": instance['State']['Name'],
                "availability_zone": instance['Placement']['AvailabilityZone'],
                # ... more fields
            })

    return instances


def _get_tag(instance: dict, key: str) -> str:
    """Extract tag value from instance."""
    tags = instance.get('Tags', [])
    for tag in tags:
        if tag['Key'] == key:
            return tag['Value']
    return ""
```

#### Update Discovery

Create `src/dfo/discover/aws_vms.py`:

```python
"""AWS EC2 instance discovery."""
from dfo.providers.aws.compute import list_instances
from dfo.db.duck import get_db


def discover_aws_instances(region: str = None) -> int:
    """Discover AWS EC2 instances."""
    instances = list_instances(region)

    db = get_db()

    for instance in instances:
        # Insert into vm_inventory (same table, multi-cloud)
        db.execute_query(
            """
            INSERT INTO vm_inventory
            (vm_id, name, resource_group, location, size, power_state, ...)
            VALUES (?, ?, ?, ?, ?, ?, ...)
            """,
            (
                instance["instance_id"],
                instance["name"],
                "",  # No resource group in AWS
                instance["availability_zone"],
                instance["instance_type"],
                instance["state"],
                # ...
            )
        )

    return len(instances)
```

#### Add CLI Command

In `src/dfo/cmd/aws.py`:

```python
"""AWS CLI commands."""
import typer

app = typer.Typer(help="AWS cloud operations")


@app.command("discover")
def discover(region: str = "us-east-1"):
    """Discover AWS EC2 instances."""
    from dfo.discover.aws_vms import discover_aws_instances

    count = discover_aws_instances(region)
    console.print(f"[green]✓[/green] Discovered {count} EC2 instances")
```

Register in `src/dfo/cli.py`:

```python
from dfo.cmd import aws

app.add_typer(aws.app, name="aws")
```

### 2. Add a New Analysis Type

See "Adding a New Analysis" section above.

### 3. Add a New Export Format

#### Update Rule

Add to `export_formats` in rule:

```json
"export_formats": ["csv", "json", "excel", "parquet"]
```

#### Implement Exporter

In `src/dfo/inventory/formatters.py`:

```python
def export_to_excel(data: List[Dict], output_file: str):
    """Export data to Excel format."""
    import pandas as pd

    df = pd.DataFrame(data)
    df.to_excel(output_file, index=False)
```

#### Wire Up in CLI

In `src/dfo/cmd/azure.py`:

```python
if export_format == "excel":
    from dfo.inventory.formatters import export_to_excel
    export_to_excel(data, export_file)
```

### 4. Add a New Database Table

#### Update Schema

In `src/dfo/db/schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS vm_network_analysis (
    vm_id TEXT PRIMARY KEY,
    bandwidth_utilization DOUBLE,
    recommended_tier TEXT,
    estimated_savings DOUBLE,
    analyzed_at TIMESTAMP
);
```

#### Create Model

In `src/dfo/core/models.py`:

```python
class VMNetworkAnalysis(BaseModel):
    vm_id: str
    bandwidth_utilization: float
    recommended_tier: str
    estimated_savings: float
    analyzed_at: datetime
```

#### Refresh Database

```bash
./dfo db refresh --yes
```

---

## Development Workflow

### Setup Development Environment

```bash
# 1. Clone repository
git clone https://github.com/vedanta/dfo.git
cd dfo

# 2. Create conda environment
conda env create -f environment.yml
conda activate dfo

# 3. Install in editable mode
pip install -e .

# 4. Copy environment template
cp .env.example .env

# 5. Configure Azure credentials in .env
# Edit .env with your Azure credentials

# 6. Initialize database
./dfo db init
```

### Development Cycle

```bash
# 1. Create feature branch
git checkout -b feature/new-analysis

# 2. Make changes
# - Create analysis module
# - Add rule to JSON
# - Update tests

# 3. Run tests
pytest src/dfo/tests/ -v

# 4. Test CLI
./dfo azure analyze --list
./dfo azure analyze new-analysis

# 5. Commit changes
git add .
git commit -m "feat: Add new-analysis module"

# 6. Push and create PR
git push origin feature/new-analysis
gh pr create
```

### Code Style Guidelines

Follow `docs/CODE_STYLE.md`:

- **Files:** `snake_case.py`
- **Classes:** `CamelCase`
- **Functions:** `snake_case_verbs`
- **Constants:** `ALL_CAPS`
- **Max file size:** 250 lines
- **Max function size:** 40 lines
- **Type hints:** Required on all functions
- **Docstrings:** Required on all public functions

Example:

```python
def analyze_vm_cpu(
    cpu_timeseries: List[Dict],
    threshold: float,
    min_days: int
) -> Dict[str, Any]:
    """Analyze CPU timeseries for a single VM.

    Calculates average CPU usage and counts days below threshold
    to determine if VM is idle.

    Args:
        cpu_timeseries: List of {timestamp, average} dicts
        threshold: CPU percentage threshold
        min_days: Minimum days below threshold

    Returns:
        Dict with keys: is_idle, cpu_avg, days_under

    Example:
        >>> result = analyze_vm_cpu(
        ...     [{"timestamp": "2024-01-01T00:00:00Z", "average": 2.5}],
        ...     threshold=5.0,
        ...     min_days=7
        ... )
        >>> result["is_idle"]
        True
    """
    # Implementation...
```

---

## Testing Strategy

### Test Organization

```
src/dfo/tests/
├── conftest.py              # Shared fixtures
├── test_analysis_idle_vms.py   # Tests for analyze/idle_vms.py
├── test_cmd_azure.py           # Tests for cmd/azure.py
├── test_config.py              # Tests for core/config.py
└── ...                         # One test file per module
```

### Writing Tests

#### Unit Test Example

```python
"""Tests for idle VM analysis."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from dfo.analyze.idle_vms import analyze_vm_cpu


def test_analyze_vm_cpu_idle():
    """Test VM is detected as idle when below threshold."""
    # Generate low CPU data
    cpu_data = []
    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    for day in range(14):
        for hour in range(24):
            timestamp = base_time + timedelta(days=day, hours=hour)
            cpu_data.append({
                "timestamp": timestamp.isoformat(),
                "average": 2.5  # Below 5% threshold
            })

    # Analyze
    result = analyze_vm_cpu(cpu_data, threshold=5.0, min_days=7)

    # Assert
    assert result["is_idle"] is True
    assert result["cpu_avg"] == 2.5
    assert result["days_under"] >= 7


def test_analyze_vm_cpu_not_idle():
    """Test VM is not detected as idle when above threshold."""
    cpu_data = [
        {"timestamp": "2024-01-01T00:00:00Z", "average": 50.0}
    ]

    result = analyze_vm_cpu(cpu_data, threshold=5.0, min_days=7)

    assert result["is_idle"] is False
```

#### Integration Test Example

```python
def test_full_analysis_flow(test_db):
    """Test complete discover -> analyze -> report flow."""
    from dfo.db.duck import DuckDBManager
    from dfo.analyze.idle_vms import analyze_idle_vms

    db = DuckDBManager()

    # 1. Insert mock data (simulate discovery)
    db.execute_query(
        """
        INSERT INTO vm_inventory
        (vm_id, name, size, cpu_timeseries, ...)
        VALUES (?, ?, ?, ?, ...)
        """,
        ("vm-123", "test-vm", "Standard_B1s", '[]', ...)
    )

    # 2. Run analysis
    with patch('dfo.analyze.idle_vms.get_vm_monthly_cost_with_metadata',
               return_value={"monthly_cost": 30.0, ...}):
        count = analyze_idle_vms(threshold=5.0, min_days=7)

    # 3. Verify results stored
    results = db.query("SELECT * FROM vm_idle_analysis")
    assert len(results) > 0
```

#### CLI Test Example

```python
from typer.testing import CliRunner
from dfo.cli import app

runner = CliRunner()


def test_analyze_list_command():
    """Test analyze --list shows all analyses."""
    result = runner.invoke(app, ["azure", "analyze", "--list"])

    assert result.exit_code == 0
    assert "Available Analyses" in result.stdout
    assert "idle-vms" in result.stdout
```

### Test Fixtures

In `conftest.py`:

```python
@pytest.fixture
def test_db(monkeypatch, tmp_path):
    """Setup test database."""
    test_db_path = tmp_path / "test.duckdb"
    monkeypatch.setenv("DFO_DUCKDB_FILE", str(test_db_path))

    from dfo.db.duck import reset_db, DuckDBManager
    from dfo.core.config import reset_settings

    reset_settings()
    reset_db()

    db = DuckDBManager()
    db.initialize_schema()

    yield db

    reset_settings()
    reset_db()
```

### Running Tests

```bash
# All tests
pytest src/dfo/tests/

# Specific file
pytest src/dfo/tests/test_analyze.py

# Specific test
pytest src/dfo/tests/test_analyze.py::test_analyze_vm_cpu_idle

# With coverage
pytest --cov=dfo --cov-report=html

# Verbose
pytest -vv

# Stop on first failure
pytest -x
```

---

## Common Patterns

### 1. Singleton Pattern (for caching)

```python
# Global instance
_instance = None

def get_instance():
    """Get or create singleton instance."""
    global _instance
    if _instance is None:
        _instance = MyClass()
    return _instance

def reset_instance():
    """Reset singleton (useful for testing)."""
    global _instance
    _instance = None
```

### 2. Database Access Pattern

```python
from dfo.db.duck import get_db

def my_function():
    db = get_db()

    # Query
    results = db.query("SELECT * FROM table WHERE field = ?", (value,))

    # Execute
    db.execute_query("INSERT INTO table VALUES (?)", (data,))
```

### 3. Configuration Access Pattern

```python
from dfo.core.config import get_settings

def my_function():
    settings = get_settings()
    threshold = settings.dfo_idle_cpu_threshold
```

### 4. Cloud Client Pattern

```python
from dfo.providers.azure.client import get_compute_client

def my_function():
    client = get_compute_client()  # Uses cached instance
    vms = client.virtual_machines.list_all()
```

### 5. Progress Display Pattern

```python
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.console import Console

console = Console()

with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    console=console
) as progress:
    task = progress.add_task("Running analysis...", total=None)

    # Do work
    result = do_work()

    progress.update(task, description="✓ Complete")
```

### 6. Error Handling Pattern

```python
import logging
import typer

logger = logging.getLogger(__name__)

def my_command():
    try:
        # Do work
        result = do_work()

    except SomeSpecificError as e:
        logger.error(f"Failed to do work: {e}")
        console.print(f"[red]Error:[/red] {e}")
        console.print("[dim]Try running: dfo db init[/dim]")
        raise typer.Exit(1)

    except Exception as e:
        logger.exception("Unexpected error")
        console.print(f"[red]Unexpected error:[/red] {e}")
        raise typer.Exit(1)
```

---

## Troubleshooting

### Common Issues

#### 1. Module Import Errors

**Error:** `ModuleNotFoundError: No module named 'dfo.analyze'`

**Cause:** Wrong import path (should be `dfo.analyze` not `dfo.analysis`)

**Fix:** Check import statements and test patches

#### 2. Database Not Found

**Error:** `Catalog Error: Table with name vm_inventory does not exist!`

**Fix:**
```bash
./dfo db init
```

#### 3. Rule Not Found

**Error:** `Unknown analysis type: idle-vms`

**Cause:** Rule key doesn't match or rule is missing from JSON

**Fix:** Check `optimization_rules.json` and verify rule has `"key": "idle-vms"`

#### 4. Mock Errors in Tests

**Error:** `'float' object is not subscriptable`

**Cause:** Mock return value doesn't match function signature

**Fix:** Update mock to return correct type:
```python
# Wrong
return_value=30.37

# Right
return_value={"monthly_cost": 30.37, "equivalent_sku": None, "hourly_price": 0.0416}
```

### Debug Mode

Enable debug logging:

```bash
export DFO_LOG_LEVEL=DEBUG
./dfo azure analyze idle-vms
```

Or in code:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Inspecting Database

```bash
# Connect to DuckDB CLI
duckdb dfo.duckdb

# Show tables
SHOW TABLES;

# Query data
SELECT * FROM vm_inventory LIMIT 10;
SELECT * FROM vm_idle_analysis;

# Check schema
DESCRIBE vm_inventory;
```

---

## Next Steps

1. **Read the Code Style Guide:** `docs/CODE_STYLE.md`
2. **Review the MVP Plan:** `docs/MVP.md`
3. **Explore the Rules Architecture:** `docs/rules_driven_cli.md`
4. **Run the Test Suite:** `pytest src/dfo/tests/`
5. **Try Adding a Simple Analysis:** Follow the "How to Extend" section
6. **Join the Team:** Ask questions, review PRs, contribute!

---

## Resources

- **GitHub Repository:** https://github.com/vedanta/dfo
- **Documentation:** `docs/`
- **Code Style Guide:** `docs/CODE_STYLE.md`
- **Architecture Guide:** `docs/rules_driven_cli.md`
- **Azure SDK Docs:** https://docs.microsoft.com/en-us/python/api/
- **DuckDB Docs:** https://duckdb.org/docs/
- **Typer Docs:** https://typer.tiangolo.com/
- **Rich Docs:** https://rich.readthedocs.io/

---

**Welcome to the DFO team! Happy coding! 🚀**
