# dfo - DevFinOps CLI

Multi-cloud FinOps optimization toolkit for discovering, analyzing, and optimizing cloud resources.

## Quick Start

### 1. Set up the conda environment

```bash
# Create and activate the environment
conda env create -f environment.yml
conda activate dfo
```

### 2. Configure environment variables

```bash
# Copy the example .env file
cp .env.example .env

# Edit .env with your Azure credentials
# Required: AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_SUBSCRIPTION_ID
```

### 3. Initialize the database

```bash
# Use the wrapper script from root directory
./dfo.sh db init

# Or use Python module directly
python -m dfo.cli db init
```

## Usage

The `dfo.sh` wrapper script allows you to run commands from the root directory:

```bash
# Show version
./dfo.sh version

# Display configuration
./dfo.sh config

# Database commands
./dfo.sh db info
./dfo.sh db refresh --yes

# Azure commands (stubs in Milestone 1)
./dfo.sh azure discover
./dfo.sh azure analyze
./dfo.sh azure report
./dfo.sh azure execute

# Get help
./dfo.sh --help
./dfo.sh db --help
```

## Project Structure

```
dfo/
├── dfo.sh              # Wrapper script for CLI
├── dfo/                # Source code directory
│   ├── core/           # Configuration and data models
│   ├── db/             # DuckDB integration
│   ├── cmd/            # CLI command modules
│   ├── cli.py          # Main CLI entry point
│   └── tests/          # Test suite
├── environment.yml     # Conda environment
├── .env                # Environment configuration (create from .env.example)
└── dfo.duckdb         # DuckDB database (created on init)
```

## Development

Run tests:
```bash
pytest dfo/tests/ -v
pytest --cov=dfo dfo/tests/  # With coverage
```

See [CLAUDE.md](CLAUDE.md) for detailed architecture and development guidelines.
