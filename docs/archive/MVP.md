# MVP.md — DevFinOps (dfo) Project Plan

## Phase 1 — MVP (Azure Idle VM Detection with DuckDB Storage)
**Status:** In Progress
**Goal:** End-to-end vertical slice: discover → analyze → report → execute, backed by a local DuckDB data store.

### 1. Scope
This phase delivers the smallest but valuable FinOps capability:
- Discover Azure VMs and CPU metrics
- Store raw inventory in DuckDB
- Analyze VMs for idle behavior
- Estimate monthly savings using static pricing
- Store analysis results in DuckDB
- Generate console and JSON reports
- Execute safe stop/deallocate actions (dry-run default)
- Fully CLI-driven using Typer

### 1.1 MVP Implementation Milestones

#### Milestone 1: Foundation & Infrastructure (Week 1)
**Goal:** Establish core infrastructure, configuration, and data layer.

**Deliverables:**
- Configuration management with Pydantic Settings (`core/config.py`)
  - Load from .env (Azure credentials, thresholds, DuckDB path)
  - Validate required fields
  - Export settings object for app-wide use
- DuckDB integration layer (`db/duck.py`)
  - Connection management (singleton pattern)
  - Schema initialization from `schema.sql`
  - Helper functions: `get_connection()`, `execute_query()`, `insert_records()`, `fetch_records()`
- Core data models (`core/models.py`)
  - Pydantic models for VM, VMInventory, VMAnalysis, VMAction
  - Serialization/deserialization helpers
- Basic CLI skeleton (`cli/main.py`)
  - Typer app with `azure` subcommand group
  - Version command
  - Config validation command

**Testing:**
- DuckDB connection and schema creation
- Config loading from .env
- Model validation

**Exit Criteria:** Can run `dfo --version` and `dfo azure` shows subcommands. DuckDB file is created and schema is initialized.

---

#### Milestone 2: Authentication & Azure Provider Setup (Week 1-2)
**Goal:** Establish Azure authentication and basic provider clients.

**Deliverables:**
- Authentication layer (`core/auth.py`)
  - `get_azure_credential()` using DefaultAzureCredential
  - Service principal support with env vars
  - Credential validation
- Azure client factory (`providers/azure/client.py`)
  - `get_compute_client(credential, subscription_id)`
  - `get_monitor_client(credential, subscription_id)`
  - Client caching/reuse
- Stub implementations for:
  - `providers/azure/compute.py`
  - `providers/azure/monitor.py`

**Testing:**
- Mock Azure auth (use fake credentials)
- Client instantiation
- Connection validation

**Exit Criteria:** Can authenticate to Azure (with real credentials) and instantiate compute/monitor clients.

---

#### Milestone 3: Discovery Layer (Week 2)
**Goal:** Discover Azure VMs and store in DuckDB.

**Deliverables:**
- VM discovery implementation (`discover/vms.py`)
  - `discover_vms(subscription_id)` function
  - List all VMs with metadata (name, resource_group, location, size, power_state, tags)
  - Retrieve 14-day CPU metrics per VM
  - Transform to VMInventory models
  - Batch insert into `vm_inventory` table
- Azure provider implementations:
  - `providers/azure/compute.py`: `list_vms(client)`
  - `providers/azure/monitor.py`: `get_cpu_metrics(client, vm_id, days=14)`
- CLI command (`cli/main.py`)
  - `dfo azure discover vms`
  - Progress indicators (Rich progress bar)
  - Summary output (VMs discovered, metrics collected)

**Testing:**
- Unit tests with mocked Azure SDK
- Integration test with test subscription (if available)
- Verify DuckDB insertion

**Exit Criteria:** Can run `dfo azure discover vms` and see populated `vm_inventory` table with CPU timeseries.

---

#### Milestone 4: Analysis Layer (Week 3)
**Goal:** Analyze idle VMs and calculate savings.

**Deliverables:**
- Idle VM analyzer (`analyze/idle_vms.py`)
  - `analyze_idle_vms()` function
  - Read from `vm_inventory`
  - Calculate CPU average over timeseries
  - Identify VMs below threshold for minimum days
  - Estimate monthly savings (static pricing lookup by size)
  - Assign severity (critical/high/medium based on savings)
  - Generate recommended action (stop/deallocate)
  - Write to `vm_idle_analysis` table
- Cost estimation helper (`providers/azure/cost.py`)
  - `get_vm_monthly_cost(vm_size, region)` using static pricing table
  - Support common VM sizes (D-series, B-series, F-series)
- CLI command
  - `dfo azure analyze idle-vms`
  - Show analysis summary (total idle VMs, potential savings)

**Testing:**
- Unit tests with mock inventory data
- Test various CPU patterns (all idle, partially idle, active)
- Verify savings calculations
- Edge cases (no metrics, missing data)

**Exit Criteria:** Can run `dfo azure analyze idle-vms` after discovery and see populated `vm_idle_analysis` table with accurate savings estimates.

---

#### Milestone 5: Reporting Layer (Week 3-4)
**Goal:** Generate human-readable and machine-readable reports.

**Deliverables:**
- Console reporter (`report/console.py`)
  - `report_idle_vms_console()` function
  - Rich table with columns: VM name, resource group, CPU avg, days idle, monthly savings, severity, action
  - Color coding by severity
  - Summary footer (total VMs, total potential savings)
- JSON reporter (`report/json_report.py`)
  - `report_idle_vms_json()` function
  - Export vm_idle_analysis to JSON
  - Support output to file or stdout
- CLI commands
  - `dfo azure report idle-vms` (defaults to console)
  - `dfo azure report idle-vms --format json`
  - `dfo azure report idle-vms --format json --output results.json`

**Testing:**
- Unit tests with mock analysis data
- Verify table formatting
- JSON schema validation

**Exit Criteria:** Can generate both console and JSON reports showing idle VM analysis results.

---

#### Milestone 6: Execution Layer (Week 4)
**Goal:** Execute VM stop/deallocate actions safely.

**Deliverables:**
- VM stop executor (`execute/stop_vms.py`)
  - `execute_stop_idle_vms(dry_run=True, yes=False)` function
  - Read actionable VMs from `vm_idle_analysis`
  - Filter by severity (configurable minimum)
  - Interactive confirmation unless `--yes` flag
  - Stop/deallocate VMs via Azure SDK
  - Log all actions to `vm_actions` table (including dry-run)
  - Error handling and rollback tracking
- Azure provider implementation
  - `providers/azure/compute.py`: `stop_vm(client, resource_group, vm_name)`
  - `deallocate_vm(client, resource_group, vm_name)`
- CLI command
  - `dfo azure execute stop-idle-vms` (dry-run by default)
  - `dfo azure execute stop-idle-vms --dry-run=false --yes`
  - `dfo azure execute stop-idle-vms --min-severity high`

**Testing:**
- Unit tests with mocked Azure SDK
- Dry-run validation (no actual VMs stopped)
- Action logging verification
- Error handling (VM not found, permission denied)

**Exit Criteria:** Can execute stop commands in dry-run mode, see what would happen, and optionally execute for real with proper logging.

---

#### Milestone 7: Polish & Documentation (Week 4-5)
**Goal:** Production-ready MVP with full documentation and testing.

**Deliverables:**
- Comprehensive test suite
  - Achieve >80% code coverage
  - Integration tests for full pipeline
  - Fixture data for reproducible tests
- Error handling improvements
  - Graceful failures with actionable error messages
  - Retry logic for transient Azure API failures
  - Validation at each stage
- Documentation
  - README with quick start guide
  - Example .env configuration
  - Sample workflow walkthrough
  - Troubleshooting guide
- CLI enhancements
  - Help text for all commands
  - Input validation
  - Logging configuration (--verbose, --quiet flags)

**Testing:**
- End-to-end workflow testing
- Error scenario testing
- Documentation review

**Exit Criteria:** MVP is usable by external users with clear documentation. All tests pass. Ready for Phase 2 planning.

---

### 1.2 MVP Success Metrics

- Successfully discover 100+ VMs from test Azure subscription
- Accurately identify idle VMs (validated against manual review)
- Savings estimates within 10% of actual Azure pricing
- Complete discovery → report cycle in <5 minutes for 100 VMs
- Zero false positives in dry-run execution
- All CLI commands include helpful error messages and progress indicators

### 2. Components Delivered
#### 2.1 Authentication
- Azure authentication using service principal or DefaultAzureCredential.

#### 2.2 Discovery Layer
- List Azure VMs (name, size, region, tags, power state)
- Retrieve CPU metrics
- Store into DuckDB table: vm_inventory

#### 2.3 Analysis Layer
- Read vm_inventory
- Detect idle VMs based on CPU + thresholds
- Estimate monthly cost savings
- Store into vm_idle_analysis

#### 2.4 Reporting Layer
- Read vm_idle_analysis
- Output as console (Rich) or JSON

#### 2.5 Execution Layer
- Read actionable VMs from DuckDB
- Stop/deallocate idle VMs
- Respect dry-run + --yes
- Log into vm_actions table

#### 2.6 Database Layer
Environment variable: DUCKDB_FILE  
Tables:
- vm_inventory
- vm_idle_analysis
- vm_actions

#### 2.7 CLI
Commands:
dfo azure discover vms  
dfo azure analyze idle-vms  
dfo azure report idle-vms  
dfo azure execute stop-idle-vms  

---

## Phase 2 — Enhanced Azure FinOps Capabilities
### 2.1 Resource Graph Integration  
### 2.2 Storage Optimization  
### 2.3 Advisor Rightsizing  
### 2.4 Expanded Reporting (HTML, CSV)

---

## Phase 3 — Multi-Cloud Expansion (AWS)
### 3.1 AWS Provider  
### 3.2 Unified Inventory Schema  
### 3.3 Unified Analyzer  
### 3.4 Reporting Enhancements  

---

## Phase 4 — Pipeline & Automation
### 4.1 Pipeline Engine  
### 4.2 Scheduling  
### 4.3 Tag Policies  
### 4.4 Notifications  

---

## Phase 5 — Platform Layer
### 5.1 Web Dashboard  
### 5.2 REST API  
### 5.3 LLM FinOps Assistant  
### 5.4 Policy-as-Code  

---

## Phase Summary Table
Phase 1 — MVP (Idle VM + DuckDB)  
Phase 2 — Azure Enhanced  
Phase 3 — Multi-Cloud  
Phase 4 — Pipeline  
Phase 5 — Platform Layer  
