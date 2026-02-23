<p align="center">
  <img src="art/dfo_logo.png" alt="dfo Logo" width="400"/>
</p>

# dfo - DevFinOps CLI

**Find and fix idle Azure VMs. Stop wasting money.**

dfo discovers VMs across your Azure subscription, collects CPU metrics, identifies underutilized resources, estimates savings, and optionally stops or resizes them -- with dry-run by default.

```
discover → analyze → report → execute
```

All data stays local (DuckDB). No cloud infrastructure required.

## Install

```bash
conda env create -f environment.yml
conda activate dfo
pip install -e .
```

## Configure

```bash
cp .env.example .env
# Set: AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_SUBSCRIPTION_ID
```

```bash
dfo db init
dfo azure test-auth
```

## Usage

### Discover and analyze

```bash
dfo azure discover vms                   # Collect VMs + 14 days of CPU metrics
dfo azure analyze idle-vms               # Flag VMs with <5% avg CPU
dfo azure analyze low-cpu                # Flag VMs for rightsizing (<20% CPU)
dfo azure analyze stopped-vms            # Flag VMs stopped 30+ days
```

### Report

```bash
dfo azure report                         # Summary across all analyses
dfo azure report --by-rule idle-vms      # Findings for one analysis
dfo azure report --by-resource vm-name   # All findings for one VM
dfo azure report --format csv --output findings.csv
```

### Execute (two workflows)

**Direct** -- quick actions on individual VMs:

```bash
dfo azure execute vm my-vm stop -g my-rg                     # Dry-run (default)
dfo azure execute vm my-vm stop -g my-rg --no-dry-run --yes  # Live
```

**Plan-based** -- batch operations with approval gates:

```bash
dfo azure plan create --from-analysis idle-vms --name "Q4 Cleanup"
dfo azure plan validate <plan-id>
dfo azure plan approve <plan-id>
dfo azure plan execute <plan-id> --force
```

### Audit trail

```bash
dfo azure logs list                      # Recent actions
dfo azure logs list --vm-name my-vm      # Filter by VM
dfo azure logs show <action-id>          # Full details
```

## Safety

- All execution commands default to **dry-run**
- Live execution requires explicit `--no-dry-run` or `--force`
- Tag VMs with `dfo-protected=true` to block actions
- Every action (including dry-runs) is logged to the local database

## Azure Permissions

| Workflow | Required Role |
|----------|--------------|
| Discover, Analyze, Report | **Reader** |
| Execute (stop/start/resize) | **Virtual Machine Contributor** |

## Tech Stack

- Python 3.10+, Typer, Rich
- DuckDB (local storage)
- Azure SDK for Python
- Pydantic Settings
- pytest (700+ tests)

## Project Structure

```
src/dfo/
  core/        Configuration, auth, models
  providers/   Azure SDK wrappers
  discovery/   VM inventory collection
  analyze/     Idle detection, rightsizing, stopped VM analysis
  report/      Console, JSON, CSV output
  execute/     Plan management, direct execution, rollback
  rules/       Optimization rules engine
  db/          DuckDB schema and queries
  cmd/         CLI command modules
  cli.py       Entry point
```

## Development

```bash
PYTHONPATH=src pytest src/dfo/tests/ -v
PYTHONPATH=src pytest --cov=dfo src/dfo/tests/
```

See [docs/CODE_STYLE.md](docs/CODE_STYLE.md) for conventions and [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for contribution guidelines.

## Documentation

- [QUICKSTART.md](QUICKSTART.md) -- Get running in 5 minutes
- [USER_GUIDE.md](USER_GUIDE.md) -- Full usage guide
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) -- System design
- [docs/ROADMAP.md](docs/ROADMAP.md) -- Future plans

## Roadmap

**Phase 1 (MVP)** -- Complete. Azure idle VM detection through execution.

**Phase 2** -- Multi-cloud (AWS, GCP), storage optimization, Advisor integration.

**Phase 3** -- Web dashboard, REST API, scheduling, notifications.

## License

This project is licensed under the [GNU Lesser General Public License v3.0](LICENSE).
