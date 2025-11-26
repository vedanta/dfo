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
| ✅ **Milestone 4** | Complete | Analysis Layer (3 VM analyses: idle, low-CPU, stopped) |
| ✅ **Milestone 5** | Complete | Reporting Layer (4 views, 3 formats, filters) |
| ✅ **Milestone 6** | Complete | Execution Layer (plans, validation, approval, execution, rollback) |

**Currently Available:**
- ✓ Configuration management with Pydantic Settings
- ✓ DuckDB local database with 10 tables (inventory, 3 analysis tables, pricing, equivalence, actions, plans)
- ✓ Azure authentication (DefaultAzureCredential + service principal)
- ✓ Azure SDK client management (Compute, Monitor, Pricing)
- ✓ VM discovery with CPU metrics collection (rules-driven)
- ✓ **3 VM analysis types** (Milestone 4): idle detection, low-CPU rightsizing, stopped VM cleanup
- ✓ **Unified reporting system** (Milestone 5): 4 view types, 3 output formats (console/JSON/CSV)
- ✓ **Complete execution system** (Milestone 6): plan management, validation, approval workflow, execution, rollback
- ✓ **Azure VM SKU equivalence mapping** (29 legacy→modern mappings)
- ✓ **Rules-driven CLI architecture** (service-based rules: vm_rules.json, storage_rules.json, etc.)
- ✓ **Enhanced rules management** (key-based lookup, categories, smart search)
- ✓ Multi-service optimization rules engine (VMs, databases, storage, networking, AKS)
- ✓ Common visualization module (sparklines, charts, dashboards)
- ✓ CLI commands: discover, analyze, report, rules, **plan** (9 execution commands)

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
./dfo azure analyze idle-vms     # Analyze for idle VMs (<5% CPU)
./dfo azure analyze low-cpu      # Analyze for rightsizing opportunities (<20% CPU)
./dfo azure analyze stopped-vms  # Analyze VMs stopped for 30+ days
./dfo azure analyze idle-vms --threshold 10.0  # Custom CPU threshold
./dfo azure analyze low-cpu --min-days 7      # Custom minimum days

# Generate reports from analysis results (✓ Available now - M5)
./dfo azure report                                  # Default summary view
./dfo azure report --by-rule idle-vms               # Findings for specific analysis
./dfo azure report --by-rule low-cpu --severity high  # Filter by severity
./dfo azure report --by-resource vm-prod-001        # All findings for one VM
./dfo azure report --all-resources                  # All VMs with findings
./dfo azure report --format json --output report.json  # Export to JSON
./dfo azure report --by-rule idle-vms --format csv --output report.csv  # Export to CSV
./dfo azure report --by-rule idle-vms --limit 20    # Limit results

# View and manage optimization rules (✓ Enhanced in M4)
./dfo rules list                 # List all rules with keys, service, category
./dfo rules list --with-keys-only  # Show only CLI-enabled rules
./dfo rules list --category compute  # Filter by category
./dfo rules keys                 # List all CLI keys
./dfo rules categories           # List all categories
./dfo rules show idle-vms        # Show rule details by key
./dfo rules show "Idle VM Detection"  # Show rule details by type
./dfo rules enable idle-vms      # Enable a rule by key
./dfo rules disable stopped-vms # Disable a rule by key

# Execution system: Create and execute plans (✓ Available now - M6)
./dfo azure plan create --from-analysis idle-vms --name "Q4 Cleanup"  # Create plan
./dfo azure plan list                              # List all plans
./dfo azure plan list --status approved            # Filter by status
./dfo azure plan show <plan-id>                    # Show plan details
./dfo azure plan show <plan-id> --detail           # Show with action list
./dfo azure plan validate <plan-id>                # Validate with Azure SDK
./dfo azure plan approve <plan-id>                 # Approve for execution
./dfo azure plan approve <plan-id> --approved-by "admin@company.com"
./dfo azure plan execute <plan-id>                 # Dry-run execution (default)
./dfo azure plan execute <plan-id> --force         # Live execution (requires approval)
./dfo azure plan execute <plan-id> --action-ids act-001,act-002 --force  # Execute specific actions
./dfo azure plan status <plan-id>                  # Check execution status
./dfo azure plan status <plan-id> --verbose        # Detailed action status
./dfo azure plan rollback <plan-id>                # Rollback simulation
./dfo azure plan rollback <plan-id> --force        # Live rollback
./dfo azure plan delete <plan-id> --force          # Delete draft/validated plans

# Get help
./dfo --help
./dfo db --help
./dfo azure --help
./dfo azure plan --help
```

## Documentation

- **[USER_GUIDE.md](USER_GUIDE.md)** - Complete user guide with workflow, examples, and troubleshooting
- **[CLAUDE.md](CLAUDE.md)** - Architecture and development guidelines for Claude Code
- **[docs/PLAN_STATUS.md](docs/PLAN_STATUS.md)** - Execution plan status lifecycle and behavior guide
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
./dfo azure discover vms

# 2. Analyze for optimization opportunities
./dfo azure analyze idle-vms
./dfo azure analyze low-cpu
./dfo azure analyze stopped-vms

# 3. Generate comprehensive report
./dfo azure report                      # Summary view

# 4. Export findings for management
./dfo azure report --format csv --output monthly-review-2025-11.csv
./dfo azure report --by-rule idle-vms --format json --output idle-vms.json

# 5. View specific VM details
./dfo azure report --by-resource vm-prod-001
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

### Complete Cost Optimization Workflow (✓ Available Now - M6)
```bash
# 1. Discover and analyze
./dfo azure discover vms
./dfo azure analyze idle-vms

# 2. Review findings
./dfo azure report --by-rule idle-vms

# 3. Create execution plan
./dfo azure plan create --from-analysis idle-vms --name "Q4 2025 Cleanup"

# 4. Validate plan (Azure SDK checks)
./dfo azure plan validate plan-20251126-001

# 5. Review plan details
./dfo azure plan show plan-20251126-001 --detail

# 6. Approve plan
./dfo azure plan approve plan-20251126-001 --approved-by "admin@company.com"

# 7. Test with dry-run
./dfo azure plan execute plan-20251126-001

# 8. Check results
./dfo azure plan status plan-20251126-001 --verbose

# 9. Execute for real
./dfo azure plan execute plan-20251126-001 --force --yes

# 10. Monitor status
./dfo azure plan status plan-20251126-001

# 11. Rollback if needed
./dfo azure plan rollback plan-20251126-001 --force
```

### Automated Cost Optimization (Legacy Example)
```bash
# Discover and analyze
./dfo azure discover vms
./dfo azure analyze idle-vms
./dfo azure analyze low-cpu

# Review findings
./dfo azure report                      # Summary view
./dfo azure report --by-rule idle-vms --severity critical  # High-value targets

# Export pre-execution audit
./dfo azure report --by-rule idle-vms --format json --output pre-execution-audit.json

# Execute actions (Coming in M6)
./dfo azure execute stop-idle-vms --no-dry-run --yes --min-severity critical
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

# Current status: 589 tests passing
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

### Phase 1: MVP ✅ **COMPLETE**
- [x] Milestone 1: Foundation & Infrastructure ✅
- [x] Milestone 2: Authentication & Azure Provider ✅
- [x] Milestone 3: Discovery Layer ✅
- [x] Milestone 4: Analysis Layer (3 Analyses + SKU Equivalence) ✅
- [x] Milestone 5: Reporting Layer (4 Views, 3 Formats) ✅
- [x] Milestone 6: Execution Layer (Plans, Validation, Approval, Execution, Rollback) ✅

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
A: **Phase 1 (MVP) is complete!** All 6 milestones are done and tested. VM discovery, 3 types of analysis (idle, low-CPU, stopped), comprehensive reporting (console/JSON/CSV), rules management, and the full execution system (plan management, validation, approval, execution, rollback) are production-ready. 589 tests passing with 70%+ coverage.

See [USER_GUIDE.md - FAQ](USER_GUIDE.md#faq) for more questions.

## Getting Help

- **User Questions:** See [USER_GUIDE.md](USER_GUIDE.md)
- **Development:** See [CLAUDE.md](CLAUDE.md)
- **Issues:** Create an issue in the repository
- **Feature Requests:** Open a discussion

## License

[Add your license information here]

## Changelog

### v0.2.0 (Current - Phase 1 MVP Complete)
- ✅ **Milestone 6 Complete**: Full execution system with plan-based workflows
- ✅ **Plan Management**: Create, list, show, delete execution plans
- ✅ **Validation System**: Azure SDK validation checks before execution
- ✅ **Approval Workflow**: Safety gates with user attribution and stale validation detection
- ✅ **Execution Engine**: Dry-run (default) and live execution modes
- ✅ **Rollback Capability**: Reverse actions for stop/deallocate/downsize (delete is irreversible)
- ✅ **9 Execution Commands**: Complete plan lifecycle management
- ✅ **Comprehensive Testing**: 150 execution tests, 92% coverage
- ✅ **Production Ready**: Phase 1 (MVP) complete with 589 tests passing

### v0.1.0 (Milestone 5: Reporting Layer Complete)
- ✅ **Milestone 5 Complete**: Unified reporting system with 4 view types
- ✅ **Unified Report Command**: Single entry point for all report types
  - Default summary view with portfolio-wide statistics
  - `--by-rule` view for specific analysis findings
  - `--by-resource <vm-name>` view for single VM analysis
  - `--all-resources` view for all VMs sorted by savings
- ✅ **Multiple Output Formats**:
  - Rich formatted console output (tables, panels, metrics)
  - JSON export with datetime serialization
  - CSV export with rule-specific columns
- ✅ **Advanced Features**:
  - Severity filtering (`--severity`)
  - Result limiting (`--limit`)
  - File output (`--output` for JSON/CSV)
- ✅ **Data Architecture**:
  - Normalized data models across all analysis types
  - Data collectors for querying analysis results
  - Formatters for console, JSON, and CSV output
- ✅ **Testing**: 349 tests passing (+6 new report tests)
- ✅ **Documentation**: Comprehensive user guide updates

### v0.0.6 (Rules-Driven CLI & Milestone 4)
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
  - Service-based rules files (`vm_rules.json`, `storage_rules.json`, etc.)
  - Backward compatible with legacy `optimization_rules.json`
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
