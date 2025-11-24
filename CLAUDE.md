# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**dfo** (DevFinOps) is a CLI-based FinOps toolkit for multi-cloud cost optimization. The MVP focuses on Azure idle VM detection using DuckDB as the local storage backend. The architecture follows a modular pipeline: `auth → discover → analyze → report → execute`.

## Environment Setup

### Creating the Environment

```bash
# Create conda environment
conda env create -f environment.yml

# Activate environment
conda activate dfo

# Install in editable mode
pip install -e .
```

### Configuration

Copy `.env.example` to `.env` and configure:
- Azure credentials (tenant, client ID, secret, subscription)
- Analysis thresholds (CPU threshold, idle days)
- DuckDB file path

## Development Commands

### Running the CLI

You can run the CLI in three ways:

```bash
# 1. Using the wrapper script (easiest from root directory)
./dfo version
./dfo db init

# 2. Using Python module directly
python -m dfo.cli version
python -m dfo.cli db init

# 3. After pip install -e . (CLI entry point: dfo.cli:run)
dfo version
dfo db init
```

### CLI Commands

```bash
# Top-level commands
./dfo version                 # Show version
./dfo config                  # Show configuration
./dfo config --show-secrets   # Show config with unmasked secrets

# Database commands
./dfo db init                 # Initialize database
./dfo db refresh              # Drop and recreate tables
./dfo db refresh --yes        # Skip confirmation
./dfo db info                 # Show database stats

# Azure commands (to be implemented in Milestone 2)
./dfo azure discover
./dfo azure analyze
./dfo azure report
./dfo azure report --format json
./dfo azure execute
./dfo azure execute --no-dry-run
```

### CLI Organization Principles

The CLI follows a modular organization pattern:

1. **Separate Files**: Each command group has its own file in `cmd/`
2. **Comprehensive Help**: All commands include detailed docstrings with examples
3. **Main Assembly**: `cli.py` imports and registers all command modules
4. **Consistent Testing**: Each command module has a corresponding test file

**Adding New Commands:**
1. Create command file in `dfo/cmd/new_command.py`
2. Import and register in `dfo/cli.py`
3. Create test file `dfo/tests/test_cmd_new_command.py`

### Testing

```bash
# Run all tests
pytest dfo/tests/

# Run specific test file
pytest dfo/tests/test_analyze.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=dfo
```

## Architecture

### Modular Pipeline Design

The system follows a strict layered architecture with clear data flow:

```
auth → discover → analyze → report → execute
                 ↓         ↓         ↓
               DuckDB ←——— analysis ←—— actions
```

Each stage is isolated, testable, and writes to DuckDB tables. Stages never directly call each other; DuckDB is the shared state.

### Directory Structure

```
dfo/
  cli.py          – Main CLI entry point (assembles all commands)
  cmd/            – CLI command modules (modular organization)
    version.py    – Version command
    config.py     – Config command
    db.py         – Database management commands (init, refresh, info)
    azure.py      – Azure commands (discover, analyze, report, execute)
  core/           – config, auth, shared models
  providers/      – cloud provider SDK integrations
    azure/        – Azure SDK wrappers (compute, monitor, cost, advisor, resource_graph)
  discover/       – inventory building (writes to vm_inventory table)
  analyze/        – FinOps analysis logic (writes to vm_idle_analysis table)
  report/         – console/JSON reporting (reads from vm_idle_analysis)
  execute/        – remediation execution (writes to vm_actions table)
  db/             – DuckDB engine, schema.sql, connection helpers
  tests/          – pytest test suite (one test file per module)
```

### DuckDB Tables

Three core tables (defined in `dfo/db/schema.sql`):

1. **vm_inventory** – raw discovery output (VM metadata + CPU metrics)
2. **vm_idle_analysis** – analysis results (CPU avg, savings estimates, severity, recommendations)
3. **vm_actions** – execution logs (action taken, status, dry-run flag)

### Provider Layer

The `providers/azure/` module wraps Azure SDK calls:
- `client.py` – constructs Azure clients
- `compute.py` – VM listing and metadata
- `monitor.py` – CPU metrics retrieval
- `cost.py` – cost estimation helpers
- `advisor.py` – rightsizing recommendations (future)
- `resource_graph.py` – multi-resource queries (future)

Providers are responsible for SDK integration only, never for storage or analysis.

### Data Flow Principle

Each stage has a single responsibility:
- **discover**: Azure SDK → DuckDB (vm_inventory)
- **analyze**: vm_inventory → analysis logic → vm_idle_analysis
- **report**: vm_idle_analysis → console/JSON output
- **execute**: vm_idle_analysis → Azure SDK (stop VMs) → vm_actions

## Key Implementation Patterns

### Authentication

Uses Azure `DefaultAzureCredential` with service principal fallback. All Azure clients are constructed through the auth layer in `core/auth.py`.

### Configuration

Uses Pydantic Settings for type-safe configuration loading from environment variables. All settings defined in `core/config.py`.

### Safety-First Execution

Execution commands default to dry-run mode. Real actions require explicit `--yes` flag. All executions are logged to `vm_actions` table regardless of dry-run status.

### Analysis Thresholds

Configurable via environment:
- `DFO_IDLE_CPU_THRESHOLD` – CPU percentage threshold (default: 5.0)
- `DFO_IDLE_DAYS` – minimum days below threshold (default: 14)
- `DFO_DRY_RUN_DEFAULT` – execution safety flag (default: true)

### Progress Callbacks and Terminal Adaptation

Long-running operations (e.g., VM discovery) use a callback-based progress system that adapts to terminal capabilities:

**Architecture:**
1. **Event System**: Business logic emits progress events via callback
   - Type: `Callable[[stage: str, status: str, data: Dict[str, Any]], None]`
   - Events: `(stage, status, data)` tuples
   - Example stages: "list_vms", "metrics", "database"
   - Example statuses: "started", "complete", "fetching", "failed"

2. **Terminal Detection**: `common/terminal.py` provides `get_display_mode()`
   - Checks terminal width (via `shutil.get_terminal_size()`)
   - Checks TTY status (via `sys.stdout.isatty()`)
   - Returns "simple" or "rich" based on capabilities
   - Graceful fallback to "simple" on errors

3. **Display Handlers**: CLI creates appropriate handler based on mode
   - **Simple**: Single-line spinner (Rich Progress)
   - **Rich**: Tree view with live updates (Rich Live + Tree)
   - Both track failures for post-completion summary

4. **Error Handling**: Failed operations emit "failed" events
   - Handlers track failures separately
   - CLI shows detailed failure table after completion
   - Error messages mapped to actionable suggestions

**Implementation Pattern:**

```python
# In business logic module (discover/vms.py)
def discover_vms(
    subscription_id: str,
    progress_callback: Optional[ProgressCallback] = None
) -> List[VMInventory]:
    if progress_callback:
        progress_callback("list_vms", "started", {})

    vms = list_vms(client)

    if progress_callback:
        progress_callback("list_vms", "complete", {"count": len(vms)})

    for idx, vm in enumerate(vms):
        try:
            if progress_callback:
                progress_callback("metrics", "fetching", {
                    "vm_name": vm["name"],
                    "index": idx + 1,
                    "total": len(vms)
                })

            metrics = get_cpu_metrics(client, vm["vm_id"])

            if progress_callback:
                progress_callback("metrics", "complete", {
                    "vm_name": vm["name"],
                    "data_points": len(metrics)
                })
        except Exception as e:
            if progress_callback:
                progress_callback("metrics", "failed", {
                    "vm_name": vm["name"],
                    "error": str(e)
                })

# In CLI command (cmd/azure.py)
from dfo.common.terminal import get_display_mode

display_mode = get_display_mode(min_width=100)

if display_mode == "simple":
    with Progress(...) as progress:
        handler = _create_simple_progress_handler(progress, task)
        inventory = discover_vms(progress_callback=handler)
else:  # rich
    with Live(...) as live:
        handler = _create_rich_progress_handler(live)
        inventory = discover_vms(progress_callback=handler)

# Show failure summary if errors occurred
if handler.state["failed_vms"]:
    console.print("[yellow]Metric Collection Failures:[/yellow]")
    # Display actionable error messages
```

**Testing**: See `tests/test_discovery_progress.py` for patterns on testing:
- Terminal detection with mocked `shutil.get_terminal_size()`
- Progress callback events with event capture
- Handler state tracking
- Error message mapping

## Extensibility

### Adding New Cloud Providers

Create parallel provider structure:
```
providers/aws/compute.py
providers/aws/monitor.py
```

Analyzers remain cloud-agnostic; only discovery layer is provider-specific.

### Adding New Analyzers

Follow the read → analyze → write pattern:
1. Read from existing inventory table
2. Apply analysis logic
3. Write to new analysis table
4. Create corresponding report and execute modules

Examples: rightsizing, storage optimization, networking cleanup.

## Project Phases

The project follows a phased roadmap:
- **Phase 1 (MVP)**: Azure idle VMs with DuckDB backend
- **Phase 2**: Enhanced Azure (Resource Graph, storage optimization, Advisor integration)
- **Phase 3**: Multi-cloud (AWS support)
- **Phase 4**: Pipeline & automation (YAML pipelines, scheduling, notifications)
- **Phase 5**: Platform layer (web dashboard, REST API, LLM assistant)

### Current Status: Phase 1 (MVP)

Phase 1 is broken into 7 incremental milestones (see docs/MVP.md for full details):

1. **Foundation & Infrastructure** - Config, DuckDB, models, CLI skeleton
2. **Authentication & Azure Provider** - Azure auth, client factory
3. **Discovery Layer** - VM discovery, CPU metrics, DuckDB storage
4. **Analysis Layer** - Idle detection, savings calculation
5. **Reporting Layer** - Console and JSON reports
6. **Execution Layer** - Safe VM stop/deallocate with dry-run
7. **Polish & Documentation** - Testing, error handling, documentation

Each milestone has clear deliverables, testing requirements, and exit criteria.

## Code Style & Standards

**All code MUST follow the standards defined in docs/CODE_STYLE.md.**

### Key Principles
- **Explicit > Implicit**: No hidden magic or side effects
- **Small modules** (≤ 250 lines) and **small functions** (≤ 40 lines)
- **Rule of One**: Each module has exactly one responsibility
- **No circular imports**: Follow dependency direction (core → providers → discover → analyze → report → execute → cli)
- **Strong typing**: All functions have type hints; all cross-layer data uses Pydantic models

### Naming Conventions
- **Files/Modules**: `snake_case.py` (e.g., `idle_vms.py`)
- **Classes**: `CamelCase` (e.g., `VMInventory`, `DuckDBManager`)
- **Functions**: `snake_case` verbs (e.g., `list_vms()`, `get_cpu_metrics()`)
- **Environment Variables**: `ALL_CAPS` with `DFO_` prefix (e.g., `DFO_IDLE_CPU_THRESHOLD`)

### Import Order
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

### Error Handling
- **Fail fast** with actionable messages
- **Never swallow exceptions**
- Tell users what to do: `"Database not found. Run 'dfo db init' to create it."`

### Layer Responsibilities

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

See docs/CODE_STYLE.md for complete specifications.

## Important Notes

- All file paths in code must use absolute paths or paths relative to the project root
- DuckDB file path is configured via `DFO_DUCKDB_FILE` environment variable
- **All DFO-specific environment variables use `DFO_` prefix** (e.g., `DFO_IDLE_CPU_THRESHOLD`, `DFO_DUCKDB_FILE`)
- External SDK variables (e.g., `AZURE_TENANT_ID`) keep their standard names
- The CLI uses Typer with cloud-first grouping (`dfo azure ...`)
- JSON fields in DuckDB store complex data (tags, CPU timeseries)
- The system is designed to be local-first (no external infrastructure required)
- Use Python `logging` module (not `print()`) in all modules except CLI commands
- CLI commands use Rich console for output
