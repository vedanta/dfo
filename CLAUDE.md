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

```bash
# The CLI entry point is defined in pyproject.toml as 'dfo'
dfo

# Future commands (per architecture):
dfo azure discover vms
dfo azure analyze idle-vms
dfo azure report idle-vms
dfo azure execute stop-idle-vms
```

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
  cli/            – Typer CLI commands and entrypoints
  core/           – config, auth, shared models
  providers/      – cloud provider SDK integrations
    azure/        – Azure SDK wrappers (compute, monitor, cost, advisor, resource_graph)
  discover/       – inventory building (writes to vm_inventory table)
  analyze/        – FinOps analysis logic (writes to vm_idle_analysis table)
  report/         – console/JSON reporting (reads from vm_idle_analysis)
  execute/        – remediation execution (writes to vm_actions table)
  db/             – DuckDB engine, schema.sql, connection helpers
  tests/          – pytest test suite
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

Currently in Phase 1 implementation.

## Important Notes

- All file paths in code must use absolute paths or paths relative to the project root
- DuckDB file path is configured via `DUCKDB_FILE` environment variable
- The CLI uses Typer with cloud-first grouping (`dfo azure ...`)
- JSON fields in DuckDB store complex data (tags, CPU timeseries)
- The system is designed to be local-first (no external infrastructure required)
