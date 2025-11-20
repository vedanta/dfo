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
| ⏳ **Milestone 4** | Planned | Analysis Layer (idle VM detection) |
| ⏳ **Milestone 5** | Planned | Reporting Layer (console + JSON) |
| ⏳ **Milestone 6** | Planned | Execution Layer (stop/deallocate VMs) |

**Currently Available:**
- ✓ Configuration management with Pydantic Settings
- ✓ DuckDB local database integration
- ✓ Azure authentication (DefaultAzureCredential + service principal)
- ✓ Azure SDK client management (Compute & Monitor)
- ✓ VM discovery with CPU metrics collection (rules-driven)
- ✓ CLI commands: `./dfo.sh azure test-auth`, `./dfo.sh azure discover vms`

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
./dfo.sh db init
```

### 4. Test your Azure connection

```bash
./dfo.sh azure test-auth
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

The `dfo.sh` wrapper script allows you to run commands from the root directory:

```bash
# Show version
./dfo.sh version

# Display configuration (secrets masked)
./dfo.sh config

# Database commands
./dfo.sh db info
./dfo.sh db refresh --yes

# Test Azure authentication
./dfo.sh azure test-auth

# Discover VMs with metrics (✓ Available now - M3)
./dfo.sh azure discover vms         # Discover VMs with CPU metrics
./dfo.sh azure discover vms --no-refresh  # Append to existing data
./dfo.sh azure discover vms --subscription SUB_ID  # Custom subscription

# Coming soon in Milestones 4-6:
./dfo.sh azure analyze idle-vms     # Analyze for idle VMs
./dfo.sh azure report idle-vms      # Generate cost report
./dfo.sh azure execute stop-idle-vms  # Take action (dry-run default)

# Get help
./dfo.sh --help
./dfo.sh db --help
./dfo.sh azure --help
```

## Documentation

- **[USER_GUIDE.md](USER_GUIDE.md)** - Complete user guide with workflow, examples, and troubleshooting
- **[CLAUDE.md](CLAUDE.md)** - Architecture and development guidelines for Claude Code
- **[CODE_STYLE.md](CODE_STYLE.md)** - Code standards and conventions
- **[MVP.md](MVP.md)** - Milestone breakdown and implementation plan
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture and design patterns

## Example Workflow (Once Complete)

### Monthly Cost Review
```bash
# Discover current state
./dfo.sh azure discover vms

# Analyze for idle VMs
./dfo.sh azure analyze idle-vms

# View findings
./dfo.sh azure report idle-vms

# Generate JSON report for management
./dfo.sh azure report idle-vms --format json --output monthly-review-2025-01.json
```

### Automated Cost Optimization
```bash
# Discover and analyze
./dfo.sh azure discover vms
./dfo.sh azure analyze idle-vms

# Stop critical idle VMs (>$500/month savings)
./dfo.sh azure execute stop-idle-vms --no-dry-run --yes --min-severity critical

# Generate audit log
./dfo.sh azure report idle-vms --format json --output executed-actions.json
```

## Project Structure

```
dfo/
├── dfo.sh              # Wrapper script for CLI
├── dfo/                # Source code directory
│   ├── core/           # Configuration and data models
│   │   ├── config.py   # Pydantic Settings ✓
│   │   ├── auth.py     # Azure authentication ✓ M2
│   │   └── models.py   # Data models ✓
│   ├── db/             # DuckDB integration ✓
│   ├── providers/      # Cloud provider SDKs ✓ M2
│   │   └── azure/      # Azure SDK clients ✓ M2
│   ├── cmd/            # CLI command modules ✓
│   ├── cli.py          # Main CLI entry point ✓
│   ├── discovery/      # VM discovery orchestration ✓ M3
│   └── tests/          # Test suite (95 tests, 97% coverage) ✓
├── environment.yml     # Conda environment
├── .env                # Environment configuration (create from .env.example)
├── dfo.duckdb         # DuckDB database (created on init)
└── USER_GUIDE.md      # Complete user documentation
```

## Development

### Run Tests
```bash
# All tests
pytest dfo/tests/ -v

# With coverage
pytest --cov=dfo dfo/tests/

# Current status: 95 tests passing, 97% coverage
```

### Code Quality
- Follows CODE_STYLE.md conventions
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

### Phase 1: MVP (Current)
- [x] Milestone 1: Foundation & Infrastructure (Week 1) ✅
- [x] Milestone 2: Authentication & Azure Provider (Week 2) ✅
- [x] Milestone 3: Discovery Layer (Week 2) ✅
- [ ] Milestone 4: Analysis Layer (Week 3)
- [ ] Milestone 5: Reporting Layer (Week 3-4)
- [ ] Milestone 6: Execution Layer (Week 4)

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
A: Milestones 1-3 are complete and tested (95 tests, 97% coverage). VM discovery is production-ready with read-only access. Milestones 4-6 are in development.

See [USER_GUIDE.md - FAQ](USER_GUIDE.md#faq) for more questions.

## Getting Help

- **User Questions:** See [USER_GUIDE.md](USER_GUIDE.md)
- **Development:** See [CLAUDE.md](CLAUDE.md)
- **Issues:** Create an issue in the repository
- **Feature Requests:** Open a discussion

## License

[Add your license information here]

## Changelog

### v0.0.3 (Current - Milestone 3 Complete)
- ✅ VM discovery layer with rules-driven metric collection
- ✅ Azure Compute provider implementation (list_vms)
- ✅ Azure Monitor provider implementation (get_cpu_metrics)
- ✅ Discovery orchestration with error handling
- ✅ CLI discover command with Rich progress indicators
- ✅ 95 tests passing, 97% coverage
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
