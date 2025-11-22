<p align="center">
  <img src="art/dfo_logo.png" alt="dfo Logo" width="400"/>
</p>

# dfo - DevFinOps CLI

**Reduce Azure cloud costs by identifying and optimizing underutilized virtual machines.**

dfo is a command-line tool that discovers Azure VMs, analyzes their CPU usage, identifies idle resources, and helps you take action to reduce costs—all with built-in safety features like dry-run mode and confirmation prompts.

## What Can dfo Do?

- 🔍 **Discover** Azure VMs across your subscription with 14 days of CPU metrics
- 📊 **Analyze** CPU usage to identify idle or underutilized resources
- 💰 **Estimate** potential monthly savings per VM
- 📋 **Report** findings in rich console tables or JSON format
- ⚡ **Execute** cost-saving actions (stop/deallocate idle VMs)
- 🔒 **Safe by default** with dry-run mode, confirmation prompts, and full action logging

## Current Status

| Milestone | Status | Description |
|-----------|--------|-------------|
| ✅ **Milestone 1** | Complete | Foundation & Infrastructure |
| ✅ **Milestone 2** | Complete | Authentication & Azure Provider |
| ✅ **Milestone 3** | Complete | Discovery Layer (VM listing + metrics) |
| ✅ **Milestone 4** | Complete | Analysis Layer (idle VM detection + SKU equivalence) |
| ⏳ **Milestone 5** | Planned | Reporting Layer (enhanced reporting) |
| ⏳ **Milestone 6** | Planned | Execution Layer (stop/deallocate VMs) |

**Currently Available:**
- ✓ Configuration management with Pydantic Settings
- ✓ DuckDB local database with 5 tables (inventory, analysis, pricing, equivalence, actions)
- ✓ Azure authentication (DefaultAzureCredential + service principal)
- ✓ Azure SDK client management (Compute, Monitor, Pricing)
- ✓ VM discovery with CPU metrics collection (rules-driven)
- ✓ **Idle VM analysis with accurate pricing** (Milestone 4)
- ✓ **Azure VM SKU equivalence mapping** (29 legacy→modern mappings)
- ✓ **Export to CSV/JSON** with basic and full modes
- ✓ **Rules-driven CLI architecture** (optimization_rules.json as source of truth)
- ✓ **Enhanced rules management** (key-based lookup, categories, smart search)
- ✓ Multi-service optimization rules engine (VMs, databases, storage, networking, AKS)
- ✓ Common visualization module (sparklines, charts, dashboards)
- ✓ CLI commands: discover, analyze, export, rules (list/show/keys/categories)

## Quick Start

### 1. Set up the conda environment

```bash
# Create and activate the environment
conda env create -f environment.yml
conda activate dfo
```

### 2. Configure Azure credentials

```bash
# Copy the example .env file
cp .env.example .env

# Edit .env with your Azure credentials
# Required: AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_SUBSCRIPTION_ID
```

**Need help getting Azure credentials?** See [USER_GUIDE.md - Setup Azure Credentials](USER_GUIDE.md#setup-azure-credentials)

### 3. Initialize the database

```bash
# Use the wrapper script from root directory
./dfo db init
```

> **Note:** If you're updating from a previous version with schema changes, run `./dfo db refresh --yes` instead. See [MIGRATIONS.md](docs/MIGRATIONS.md) for details.

### 4. Test your Azure connection

```bash
./dfo azure test-auth
```

**Expected output:**
```
1/4 Loading configuration...
✓ Subscription: your-subscription-id

2/4 Authenticating to Azure...
✓ Authentication successful

3/4 Creating Compute client...
✓ Compute client created

4/4 Creating Monitor client...
✓ Monitor client created

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Success                             ┃
┃ Authentication test passed!         ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

You're ready! 🎉

## Usage

The `dfo` wrapper script allows you to run commands from the root directory:

```bash
# Show version
./dfo version

# Display configuration (secrets masked)
./dfo config

# Database commands
./dfo db info
./dfo db refresh --yes

# Test Azure authentication
./dfo azure test-auth

# Discover VMs with metrics (✓ Available now - M3)
./dfo azure discover vms         # Discover VMs with CPU metrics
./dfo azure discover vms --visual  # Show visual summary after discovery
./dfo azure discover vms --no-refresh  # Append to existing data
./dfo azure discover vms --subscription SUB_ID  # Custom subscription

# Browse discovered inventory (✓ Available now - M3 + Phase 2)
./dfo azure list vms             # List all discovered VMs
./dfo azure list vms --resource-group production-rg  # Filter by resource group
./dfo azure list vms --power-state running  # Filter by power state
./dfo azure list vms --location eastus --limit 10  # Combined filters
./dfo azure list vms --tag env=production  # Filter by tag
./dfo azure list vms --tag-key cost-center  # Filter by tag key exists
./dfo azure list vms --discovered-after 2025-01-15  # Filter by date
./dfo azure list vms --sort location --order desc  # Sort results
./dfo azure list vms --format json --output inventory.json  # Export to JSON
./dfo azure list vms --format csv --output inventory.csv  # Export to CSV
./dfo azure show vm my-vm        # Show detailed VM information
./dfo azure show vm my-vm --metrics  # Include detailed metrics
./dfo azure show vm my-vm --format json  # Export VM details as JSON
./dfo azure search vms "prod*"   # Search VMs by pattern
./dfo azure search vms "web" --power-state running  # Search with filters

# Analyze VMs for optimization opportunities (✓ Available now - M4)
./dfo azure analyze --list       # List all available analyses
./dfo azure analyze idle-vms     # Analyze for idle VMs
./dfo azure analyze idle-vms --threshold 10.0  # Custom CPU threshold
./dfo azure analyze idle-vms --min-days 7      # Custom minimum days

# Export analysis results (✓ Available now - M4)
./dfo azure analyze idle-vms --export-format csv                    # Basic CSV export
./dfo azure analyze idle-vms --export-format json --full           # Full JSON export
./dfo azure analyze idle-vms --export-format csv --export-file results.csv --full  # Export to file

# View and manage optimization rules (✓ Enhanced in M4)
./dfo rules list                 # List all rules with keys, service, category
./dfo rules list --with-keys-only  # Show only CLI-enabled rules
./dfo rules list --category compute  # Filter by category
./dfo rules keys                 # List all CLI keys
./dfo rules categories           # List all categories
./dfo rules show idle-vms        # Show rule details by key
./dfo rules show "Idle VM Detection"  # Show rule details by type
./dfo rules enable idle-vms      # Enable a rule by key
./dfo rules disable shutdown-vms # Disable a rule by key

# Coming soon in Milestones 5-6:
./dfo azure report idle-vms      # Generate enhanced reports
./dfo azure execute stop-idle-vms  # Take action (dry-run default)

# Get help
./dfo --help
./dfo db --help
./dfo azure --help
```

## Documentation

- **[USER_GUIDE.md](USER_GUIDE.md)** - Complete user guide with workflow, examples, and troubleshooting
- **[CLAUDE.md](CLAUDE.md)** - Architecture and development guidelines for Claude Code
- **[docs/rules_driven_cli.md](docs/rules_driven_cli.md)** - Rules-driven CLI architecture guide
- **[docs/sku_equivalence_implementation.md](docs/sku_equivalence_implementation.md)** - Azure VM SKU equivalence strategy
- **[docs/azure_vm_selection_strategy.md](docs/azure_vm_selection_strategy.md)** - VM SKU mapping rules and examples
- **[docs/VISUALIZATIONS.md](docs/VISUALIZATIONS.md)** - Visualization module API reference and usage guide
- **[docs/MIGRATIONS.md](docs/MIGRATIONS.md)** - Database schema changes and upgrade instructions
- **[docs/CODE_STYLE.md](docs/CODE_STYLE.md)** - Code standards and conventions
- **[docs/MVP.md](docs/MVP.md)** - Milestone breakdown and implementation plan
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture and design patterns
- **[docs/ROADMAP.md](docs/ROADMAP.md)** - Project roadmap and future plans

## Example Workflows

### Monthly Cost Review (✓ Available Now)
```bash
# 1. Discover current state
./dfo azure discover

# 2. Analyze for idle VMs
./dfo azure analyze idle-vms

# 3. Export findings for management (CSV or JSON)
./dfo azure analyze idle-vms --export-format csv --export-file monthly-review-2025-01.csv --full

# 4. View specific rule details
./dfo rules show idle-vms
```

### Exploring Available Analyses (✓ Available Now)
```bash
# 1. See what analyses are available
./dfo azure analyze --list

# 2. View rule details by key
./dfo rules show idle-vms

# 3. List all CLI keys
./dfo rules keys

# 4. List rules by category
./dfo rules list --category compute
```

### Custom Analysis Threshold (✓ Available Now)
```bash
# Discover VMs
./dfo azure discover

# Analyze with stricter criteria (10% CPU, 30 days)
./dfo azure analyze idle-vms --threshold 10.0 --min-days 30

# Export results
./dfo azure analyze idle-vms --export-format json --full
```

### Automated Cost Optimization (Coming in M6)
```bash
# Discover and analyze
./dfo azure discover
./dfo azure analyze idle-vms

# Stop critical idle VMs (>$500/month savings)
./dfo azure execute stop-idle-vms --no-dry-run --yes --min-severity critical

# Generate audit log
./dfo azure report idle-vms --format json --output executed-actions.json
```

## Project Structure

```
dfo/
├── dfo                 # Wrapper script for CLI (executable)
├── src/                # Source code root
│   └── dfo/            # Main package directory
│       ├── core/       # Configuration and data models
│       │   ├── config.py   # Pydantic Settings ✓
│       │   ├── auth.py     # Azure authentication ✓ M2
│       │   └── models.py   # Data models ✓
│       ├── db/         # DuckDB integration ✓
│       ├── providers/  # Cloud provider SDKs ✓ M2
│       │   └── azure/  # Azure SDK clients ✓ M2
│       ├── cmd/        # CLI command modules ✓
│       ├── cli.py      # Main CLI entry point ✓
│       ├── discovery/  # VM discovery orchestration ✓ M3
│       ├── rules/      # Optimization rules engine ✓ M3
│       └── tests/      # Test suite (119 tests passing) ✓
├── docs/               # Documentation
│   ├── MIGRATIONS.md   # Database schema changes
│   ├── CODE_STYLE.md   # Code standards and conventions
│   ├── MVP.md          # Milestone breakdown
│   ├── ARCHITECTURE.md # System architecture
│   └── ROADMAP.md      # Project roadmap
├── README.md           # This file (project overview)
├── USER_GUIDE.md       # Complete user guide
├── CLAUDE.md           # Development guide for Claude Code
├── environment.yml     # Conda environment
├── .env                # Environment configuration (create from .env.example)
└── dfo.duckdb         # DuckDB database (created on init)
```

## Development

### Run Tests
```bash
# All tests
PYTHONPATH=src pytest src/dfo/tests/ -v

# With coverage
PYTHONPATH=src pytest --cov=dfo src/dfo/tests/

# Current status: 119 tests passing
```

### Code Quality
- Follows [docs/CODE_STYLE.md](docs/CODE_STYLE.md) conventions
- Type hints on all functions
- Import order: stdlib → third-party → internal
- Max 250 lines per file, 40 lines per function

### Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines (coming soon).

## Technical Details

- **Language:** Python 3.10+
- **CLI Framework:** Typer with Rich formatting
- **Database:** DuckDB (local, no external dependencies)
- **Cloud SDK:** Azure SDK for Python
- **Testing:** pytest with 97% coverage
- **Configuration:** Pydantic Settings with .env support

## Roadmap

### Phase 1: MVP
- [x] Milestone 1: Foundation & Infrastructure ✅
- [x] Milestone 2: Authentication & Azure Provider ✅
- [x] Milestone 3: Discovery Layer ✅
- [x] Milestone 4: Analysis Layer (Idle VMs + SKU Equivalence) ✅
- [ ] Milestone 5: Enhanced Reporting Layer (In Progress)
- [ ] Milestone 6: Execution Layer

### Phase 2: Enhancement
- Multi-cloud support (AWS, GCP)
- Additional resource types (databases, storage, networking)
- Advanced cost allocation and tagging
- Historical trending and forecasting

### Phase 3: Platform
- Web dashboard
- REST API
- Scheduling and automation
- LLM-powered recommendations
- Multi-tenant support

## FAQ

**Q: Will dfo make changes to my Azure resources?**
A: Only if you explicitly run `execute` commands with `--no-dry-run`. All other commands are read-only. Dry-run is enabled by default.

**Q: What permissions does dfo need?**
A: **Reader** role for discovery/analysis (read-only). **Contributor** role for execute actions (start/stop VMs).

**Q: Where is my data stored?**
A: All data is stored locally in `dfo.duckdb`. No cloud storage or external services required.

**Q: Is dfo production-ready?**
A: Milestones 1-4 are complete and tested. VM discovery, idle VM analysis with accurate pricing, export functionality, and rules management are production-ready. Analysis is read-only. Milestones 5-6 (enhanced reporting and execution) are in development.

See [USER_GUIDE.md - FAQ](USER_GUIDE.md#faq) for more questions.

## Getting Help

- **User Questions:** See [USER_GUIDE.md](USER_GUIDE.md)
- **Development:** See [CLAUDE.md](CLAUDE.md)
- **Issues:** Create an issue in the repository
- **Feature Requests:** Open a discussion

## License

[Add your license information here]

## Changelog

### v0.0.6 (Current - Rules-Driven CLI & Milestone 4)
- ✅ **Milestone 4 Complete**: Analysis Layer with idle VM detection
- ✅ **Azure VM SKU Equivalence**: 29 legacy-to-modern VM SKU mappings
  - New module: `src/dfo/analyze/compute_mapper.py`
  - New table: `vm_equivalence` with B/A/D/E-series mappings
  - Auto-initialization via `init_data.sql`
- ✅ **Enhanced Pricing Module**:
  - Fixed Azure Retail Prices API integration
  - Pricing cache table (`vm_pricing_cache`)
  - Accurate cost calculations for legacy SKUs
- ✅ **Export Functionality**:
  - CSV and JSON export formats
  - Basic export (9 fields) and Full export (16 fields)
  - Export to file or stdout
- ✅ **Rules-Driven CLI Architecture**:
  - `optimization_rules.json` as single source of truth
  - Dynamic CLI command generation
  - New fields: key, category, description, module, actions, export_formats
  - Smart lookup: supports both keys and rule types
- ✅ **Enhanced Rules Commands**:
  - New: `./dfo rules keys` - List all CLI keys
  - New: `./dfo rules categories` - List all categories
  - Updated: `./dfo rules list` - Shows key, service, category columns
  - Updated: `./dfo rules show` - Smart lookup by key or type
  - Updated: `./dfo rules enable/disable` - Accepts keys or types
  - New filters: `--category`, `--with-keys-only`
- ✅ **Database Schema Updates**:
  - 5 tables total: vm_inventory, vm_idle_analysis, vm_pricing_cache, vm_equivalence, vm_actions
  - Dynamic `db info` command
- ✅ **Directory Consolidation**: Verb forms (discover/, analyze/) for consistency
- ✅ **Documentation**:
  - `docs/rules_driven_cli.md` - Complete architecture guide
  - `docs/sku_equivalence_implementation.md` - SKU mapping implementation
  - `docs/azure_vm_selection_strategy.md` - VM SKU selection rules

### v0.0.5 (Visualization Module)
- ✅ **Common Visualization Module**: Reusable terminal visualization library
- ✅ **Micro-visualizations**: Sparklines, progress bars, color indicators
- ✅ **Chart Visualizations**: Horizontal bar charts, time-series charts, histograms
- ✅ **Composite Visualizations**: Metric panels with trends
- ✅ **Comprehensive Testing**: 50 tests passing for visualization module
- ✅ **Documentation**: Complete API reference and usage guide
- ✅ **Demo Script**: Interactive examples in `examples/visualization_demo.py`
- ✅ **Ready for M4**: Visualization infrastructure for Analysis Layer

### v0.0.4 (Inventory Browse Phase 2 Complete)
- ✅ **Output Formats**: JSON and CSV export with `--format` and `--output` flags
- ✅ **Search Command**: `azure search vms` with wildcard pattern support
- ✅ **Enhanced Filtering**: Tag filtering (`--tag`, `--tag-key`) and date filtering (`--discovered-after`, `--discovered-before`)
- ✅ **Sorting**: Sort by any field (`--sort`) with ascending/descending order (`--order`)
- ✅ **Formatters Module**: Reusable JSON/CSV formatters for all commands
- ✅ **Comprehensive Testing**: 174 tests passing (+37 new tests)
- ✅ **Documentation**: Updated README, USER_GUIDE, and test guides

### v0.0.3 (Milestone 3 Complete)
- ✅ VM discovery layer with rules-driven metric collection
- ✅ Azure Compute provider implementation (list_vms)
- ✅ Azure Monitor provider implementation (get_cpu_metrics)
- ✅ Discovery orchestration with error handling
- ✅ CLI discover command with Rich progress indicators
- ✅ Multi-service optimization rules engine (VMs, databases, storage, networking, AKS)
- ✅ Rules management CLI: list, show, enable, disable, services, layers, mvp
- ✅ Service type filtering (--service-type flag, DFO_SERVICE_TYPES env var)
- ✅ Inventory browse commands: list and show with filters
- ✅ 137 tests passing, 97% coverage
- ✅ Production-ready VM discovery with read-only access

### v0.0.2 (Milestone 2 Complete)
- ✅ Core authentication layer with DefaultAzureCredential
- ✅ Azure SDK client factory with caching
- ✅ Provider stub implementations (compute, monitor)
- ✅ CLI test command: `azure test-auth`
- ✅ 75 tests passing, 97% coverage
- ✅ Complete user guide documentation

### v0.0.1 (Milestone 1 Complete)
- Configuration management with Pydantic Settings
- DuckDB integration with schema management
- Data models with DuckDB serialization
- Modular CLI architecture
- Database commands (init, refresh, info)
- 52 tests, comprehensive documentation

---

**Ready to optimize your Azure costs? Start with the [USER_GUIDE.md](USER_GUIDE.md)!** 💰☁️
