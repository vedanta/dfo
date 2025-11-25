# dfo User Guide

**DevFinOps (dfo)** - Your Azure cloud cost optimization companion.

## Table of Contents

- [What is dfo?](#what-is-dfo)
- [Getting Started](#getting-started)
- [Core Workflows](#core-workflows)
- [Command Reference](#command-reference)
- [Rules-Driven CLI](#rules-driven-cli)
- [Export and Reporting](#export-and-reporting)
- [Advanced Usage](#advanced-usage)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)

---

## What is dfo?

dfo is a command-line tool that helps you identify and reduce Azure cloud costs by finding underutilized virtual machines (VMs). It uses a sophisticated rules-driven architecture to analyze your Azure resources, identify idle or underutilized VMs, and help you take action to reduce costs.

### Key Features

- 🔍 **Discover** - Find all Azure VMs across your subscription with 14 days of CPU metrics
- 📊 **Analyze** - Identify idle or underutilized VMs using configurable rules
- 💰 **Calculate** - Accurate cost estimates using Azure VM SKU equivalence mapping
- 📋 **Export** - Generate CSV or JSON reports for management
- 🎯 **Rules-Driven** - Extensible architecture where adding new analyses requires zero CLI code changes
- 🔒 **Safe by Default** - Dry-run mode, confirmation prompts, and full audit logging

### What Makes dfo Different?

1. **Rules-Driven CLI**: The `optimization_rules.json` file is the single source of truth. Adding a new analysis type requires creating a Python module and adding a JSON entry—no CLI code changes needed.

2. **SKU Equivalence**: Accurate pricing for legacy Azure VMs through intelligent SKU mapping (e.g., Standard_B1s → Standard_B2ls_v2).

3. **Local-First**: All data stored in a local DuckDB database. No cloud storage or external dependencies.

4. **Production-Ready**: Tested, documented, and designed for real-world use.

---

## Getting Started

### Prerequisites

- **Azure Subscription**: With VMs you want to analyze
- **Azure Credentials**: Service principal with Reader role (see [Azure Setup](#azure-setup))
- **Python 3.10+**: With conda installed
- **Operating System**: macOS, Linux, or Windows with WSL

### Installation

#### 1. Clone the Repository

```bash
git clone https://github.com/your-org/dfo.git
cd dfo
```

#### 2. Create Conda Environment

```bash
# Create the environment from environment.yml
conda env create -f environment.yml

# Activate the environment
conda activate dfo
```

#### 3. Configure Azure Credentials

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your Azure credentials
nano .env  # or use your preferred editor
```

Required environment variables:

```bash
# Azure Authentication
AZURE_TENANT_ID=your-tenant-id-here
AZURE_CLIENT_ID=your-client-id-here
AZURE_CLIENT_SECRET=your-client-secret-here
AZURE_SUBSCRIPTION_ID=your-subscription-id-here

# Analysis Configuration (optional)
DFO_IDLE_CPU_THRESHOLD=5.0    # CPU % below which VM is idle
DFO_IDLE_DAYS=14              # Days of idle CPU to flag VM
DFO_DUCKDB_FILE=dfo.duckdb    # Database file path
```

<details>
<summary><b>Need help getting Azure credentials? Click here →</b></summary>

### Azure Setup

#### Option 1: Create Service Principal (Recommended)

```bash
# Login to Azure CLI
az login

# Create service principal with Reader role
az ad sp create-for-rbac \
  --name "dfo-service-principal" \
  --role Reader \
  --scopes /subscriptions/YOUR_SUBSCRIPTION_ID

# Output will contain:
# - appId (use as AZURE_CLIENT_ID)
# - password (use as AZURE_CLIENT_SECRET)
# - tenant (use as AZURE_TENANT_ID)
```

#### Option 2: Use Azure CLI (For Testing)

Simply run `az login` and dfo will use your Azure CLI credentials automatically.

#### Required Permissions

- **Reader**: For discovery and analysis (read-only)
- **Contributor**: For execution actions (start/stop VMs) - *Coming in Milestone 6*

</details>

#### 4. Initialize Database

```bash
# Initialize the DuckDB database
./dfo db init
```

This creates `dfo.duckdb` with 5 tables:
- `vm_inventory` - Discovered VMs and metrics
- `vm_idle_analysis` - Analysis results
- `vm_pricing_cache` - Cached Azure pricing
- `vm_equivalence` - Legacy-to-modern SKU mappings (29 entries)
- `vm_actions` - Execution audit log

#### 5. Test Azure Connection

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

---

## Core Workflows

### Workflow 1: Your First Cost Analysis

**Goal**: Discover VMs and identify idle resources

```bash
# Step 1: Discover VMs
./dfo azure discover

# Step 2: View discovered VMs
./dfo azure list vms

# Step 3: See what analyses are available
./dfo azure analyze --list

# Step 4: Run idle VM analysis
./dfo azure analyze idle-vms

# Step 5: Export results to CSV
./dfo azure analyze idle-vms --export-format csv --export-file idle_vms.csv
```

**What to expect:**
- Step 1 discovers VMs and fetches 14 days of CPU metrics (~1-2 min)
- Step 4 identifies VMs with avg CPU <5% for ≥14 days
- Shows total potential savings per month
- Breaks down by severity (Critical, High, Medium, Low)

### Workflow 2: Monthly Cost Review

**Goal**: Generate a management report

```bash
# 1. Fresh discovery
./dfo azure discover

# 2. Analyze with default thresholds
./dfo azure analyze idle-vms

# 3. Export full details to CSV for management
./dfo azure analyze idle-vms \
  --export-format csv \
  --export-file monthly-review-jan-2025.csv \
  --full

# 4. View rule details to understand the analysis
./dfo rules show idle-vms
```

**Full export includes:**
- VM ID, name, resource group, location, size
- Power state, OS type, priority
- CPU average, days under threshold
- Estimated monthly savings
- Severity, recommended action
- Equivalent SKU (for legacy VMs)
- Analysis timestamp
- Tags

### Workflow 3: Custom Threshold Analysis

**Goal**: Find VMs with different idle criteria

```bash
# Discover VMs
./dfo azure discover

# Stricter criteria: 10% CPU, 30 days
./dfo azure analyze idle-vms --threshold 10.0 --min-days 30

# More lenient: 15% CPU, 7 days
./dfo azure analyze idle-vms --threshold 15.0 --min-days 7

# Export each analysis separately
./dfo azure analyze idle-vms --threshold 10.0 --min-days 30 \
  --export-format json --export-file strict-analysis.json --full
```

### Workflow 4: Exploring the Rules System

**Goal**: Understand available analyses and how to manage them

```bash
# List all CLI-enabled analyses
./dfo rules keys

# See all categories
./dfo rules categories

# Show detailed info about a specific rule
./dfo rules show idle-vms

# List all rules with keys
./dfo rules list --with-keys-only

# Filter by category
./dfo rules list --category compute

# Enable/disable a rule
./dfo rules disable stopped-vms
./dfo rules enable stopped-vms
```

---

## Command Reference

### Top-Level Commands

```bash
./dfo version        # Show version
./dfo config         # Show configuration (secrets masked)
./dfo config --show-secrets  # Show config with secrets
./dfo --help         # Show help
```

### Database Commands

```bash
./dfo db init        # Initialize database
./dfo db refresh     # Drop and recreate tables
./dfo db refresh --yes  # Skip confirmation
./dfo db info        # Show table counts
```

### Azure Commands

#### Discovery

```bash
./dfo azure discover  # Discover VMs with metrics
./dfo azure discover --show-summary  # Show visual summary
./dfo azure discover --no-refresh    # Append (don't drop existing data)
```

**Progress Display Modes**

Discovery automatically adapts its progress display based on your terminal:

- **Rich Mode** (≥100 columns, interactive terminal):
  - Tree view with real-time VM progress
  - Progress bar showing completion percentage
  - Live success/failure counts
  - Failed VMs shown inline with error messages
  - Ideal for interactive sessions

- **Simple Mode** (< 100 columns, pipes, CI):
  - Single-line spinner with counts
  - Compact progress updates
  - Failure count in final message
  - Ideal for narrow terminals or automation

**After Discovery**:
- Summary panel shows total VMs, metrics coverage, and failures
- Detailed failure table if any errors occurred
- Actionable error messages (permissions, rate limits, network issues)
- Tips for retrying failed metric collections

#### Browse Inventory

```bash
./dfo azure list vms                    # List all VMs
./dfo azure list vms --power-state running  # Filter by state
./dfo azure list vms --location eastus      # Filter by location
./dfo azure list vms --tag env=prod        # Filter by tag
./dfo azure list vms --format json --output vms.json  # Export

./dfo azure show vm my-vm-name          # Show VM details
./dfo azure show vm my-vm-name --metrics  # Include CPU metrics

./dfo azure search vms "web*"           # Search by pattern
```

#### Analysis

```bash
./dfo azure analyze --list              # List available analyses
./dfo azure analyze idle-vms            # Run idle VM analysis
./dfo azure analyze idle-vms --threshold 10.0  # Custom threshold
./dfo azure analyze idle-vms --min-days 7      # Custom period

# Export options
./dfo azure analyze idle-vms --export-format csv        # Basic CSV
./dfo azure analyze idle-vms --export-format json       # Basic JSON
./dfo azure analyze idle-vms --export-format csv --full # Full CSV
./dfo azure analyze idle-vms --export-format csv \
  --export-file results.csv --full  # Full CSV to file
```

### Rules Commands

```bash
./dfo rules list                 # List all rules
./dfo rules list --with-keys-only  # CLI-enabled rules only
./dfo rules list --category compute  # Filter by category
./dfo rules list --service-type vm   # Filter by service
./dfo rules list --layer 1           # Filter by layer
./dfo rules list --enabled-only      # Only enabled rules

./dfo rules keys                 # List all CLI keys
./dfo rules categories           # List categories
./dfo rules layers               # Show layer descriptions
./dfo rules services             # List service types

./dfo rules show idle-vms        # Show rule by key
./dfo rules show "Idle VM Detection"  # Show rule by type

./dfo rules enable idle-vms      # Enable by key
./dfo rules disable stopped-vms # Disable by key
./dfo rules enable "Right-Sizing (CPU)"  # Enable by type
```

---

## Rules-Driven CLI

### How It Works

dfo uses a **rules-driven architecture** where the CLI is automatically generated from `optimization_rules.json`. This makes the system extremely extensible.

#### The Rules File

Every analysis type corresponds to a rule in `src/dfo/rules/optimization_rules.json`:

```json
{
  "service_type": "vm",
  "layer": 1,
  "sub_layer": "Self-Contained VM",
  "type": "Idle VM Detection",
  "key": "idle-vms",
  "category": "compute",
  "description": "Detect underutilized VMs based on CPU and RAM metrics",
  "module": "idle_vms",
  "metric": "CPU/RAM <5%",
  "threshold": "<5%",
  "period": "7d",
  "unit": "percent",
  "enabled": true,
  "actions": ["stop", "deallocate", "delete"],
  "export_formats": ["csv", "json"],
  "providers": {
    "azure": "CPU% + RAM% time series"
  }
}
```

#### Key Fields

| Field | Purpose | Example |
|-------|---------|---------|
| `key` | CLI command identifier | `"idle-vms"` |
| `category` | Grouping category | `"compute"` |
| `description` | Human-readable description | `"Detect underutilized VMs..."` |
| `module` | Python module in `analyze/` | `"idle_vms"` |
| `actions` | Available actions | `["stop", "deallocate"]` |
| `export_formats` | Supported formats | `["csv", "json"]` |

#### Dynamic CLI Routing

When you run `./dfo azure analyze idle-vms`:

1. CLI looks up rule with `key="idle-vms"`
2. Checks if rule is enabled
3. Dynamically imports `dfo.analysis.{module}`
4. Calls the analysis function
5. Displays results

**No CLI code changes needed!** Just add a rule and a Python module.

### Adding a New Analysis

To add a new analysis type (e.g., "memory-intensive"):

1. **Create analysis module**: `src/dfo/analyze/memory_intensive.py`
2. **Add rule to JSON**: Set `key="memory-intensive"`, `module="memory_intensive"`
3. **Done!** Run `./dfo azure analyze memory-intensive`

See [docs/rules_driven_cli.md](docs/rules_driven_cli.md) for complete details.

---

## Export and Reporting

dfo provides a comprehensive reporting system with multiple view types and output formats.

### Report Command Overview

The unified `./dfo azure report` command supports:
- **4 View Types**: Summary, by-rule, by-resource, all-resources
- **3 Output Formats**: console (Rich formatted), JSON, CSV
- **Filters**: severity, limit
- **File Output**: Export to JSON or CSV files

### View Types

#### 1. Summary View (Default)

Shows portfolio-wide statistics across all analyses:

```bash
./dfo azure report
```

**Output includes:**
- Total VMs analyzed
- Total findings and potential savings
- Breakdown by analysis type (idle-vms, low-cpu, stopped-vms)
- Breakdown by severity
- Top 10 issues by savings potential

#### 2. By-Rule View

Shows findings for a specific analysis type:

```bash
# Idle VM findings
./dfo azure report --by-rule idle-vms

# Low-CPU rightsizing opportunities
./dfo azure report --by-rule low-cpu

# Stopped VM cleanup recommendations
./dfo azure report --by-rule stopped-vms
```

**Output includes:**
- Summary metrics for this rule
- Severity breakdown
- Detailed findings table with rule-specific columns

#### 3. By-Resource View

Shows all findings for a specific VM:

```bash
./dfo azure report --by-resource vm-prod-001
```

**Output includes:**
- VM details (resource group, location, size, power state)
- All findings across all analysis types
- Total monthly and annual savings for this VM

#### 4. All-Resources View

Shows all VMs with findings, sorted by savings potential:

```bash
./dfo azure report --all-resources
```

**Output includes:**
- Summary metrics
- Table of all VMs with findings
- Finding count and max severity per VM
- Sorted by total savings (descending)

### Output Formats

#### Console Format (Default)

Rich formatted output with tables, panels, and color-coded severity:

```bash
./dfo azure report
./dfo azure report --by-rule idle-vms
```

**Features:**
- Color-coded severity levels
- Formatted tables with proper alignment
- Summary panels with key metrics
- Progress indicators and tips

#### JSON Format

Structured JSON for automation and integration:

```bash
# Output to stdout
./dfo azure report --format json

# Export to file
./dfo azure report --format json --output report.json

# Specific view with JSON
./dfo azure report --by-rule idle-vms --format json --output idle-vms.json
```

**Features:**
- Valid JSON structure
- Datetime fields in ISO format
- Suitable for CI/CD pipelines
- Easy to parse programmatically

#### CSV Format

Spreadsheet-friendly format with rule-specific columns:

```bash
# Output to stdout
./dfo azure report --format csv

# Export to file
./dfo azure report --format csv --output report.csv

# Specific view with CSV
./dfo azure report --by-rule idle-vms --format csv --output idle-vms.csv
```

**CSV Columns (varies by view):**

**Summary View:**
- VM Name, VM ID, Resource Group, Location
- Analysis Type, Rule Type, Severity
- Monthly Savings, Annual Savings, Analyzed At

**Idle VMs:**
- VM Name, VM ID, Resource Group, Location, Severity
- CPU Average (%), Days Under Threshold
- Recommended Action, Equivalent SKU
- Monthly Savings, Annual Savings, Analyzed At

**Low-CPU:**
- VM Name, VM ID, Resource Group, Location, Severity
- CPU Average (%), Days Under Threshold
- Current SKU, Recommended SKU
- Current Cost, Recommended Cost
- Monthly Savings, Savings Percentage, Annual Savings

**Stopped VMs:**
- VM Name, VM ID, Resource Group, Location, Severity
- Power State, Days Stopped
- Disk Cost, Recommended Action
- Monthly Savings, Annual Savings

**Resource View:**
- VM Name, VM ID, Resource Group, Location, Size, Power State
- Analysis Type, Rule Type, Severity
- Monthly Savings, Annual Savings

**All-Resources:**
- VM Name, Resource Group, Location
- Finding Count, Max Severity
- Total Monthly Savings, Total Annual Savings

### Filters and Options

#### Severity Filter

Filter findings by minimum severity level:

```bash
# Show only high and critical findings
./dfo azure report --severity high

# Show only critical findings
./dfo azure report --by-rule idle-vms --severity critical

# Show low severity and above (all)
./dfo azure report --severity low
```

**Severity Levels:** low < medium < high < critical

#### Limit Results

Limit the number of findings shown:

```bash
# Show top 10 findings
./dfo azure report --by-rule idle-vms --limit 10

# Show top 5 VMs with most findings
./dfo azure report --all-resources --limit 5
```

#### Combining Filters

Filters can be combined:

```bash
# Top 20 critical idle VMs
./dfo azure report --by-rule idle-vms --severity critical --limit 20

# High-severity findings across all analyses, export to CSV
./dfo azure report --severity high --format csv --output high-priority.csv
```

### Common Reporting Workflows

#### Monthly Executive Report

```bash
# 1. Generate summary view
./dfo azure report

# 2. Export to CSV for management
./dfo azure report --format csv --output monthly-summary-2025-11.csv

# 3. Export detailed findings to JSON
./dfo azure report --by-rule idle-vms --format json --output idle-details.json
```

#### Focus on High-Value Targets

```bash
# Critical findings only
./dfo azure report --severity critical

# Top 10 idle VMs by savings
./dfo azure report --by-rule idle-vms --severity critical --limit 10

# Export high-priority targets
./dfo azure report --severity high --format csv --output action-items.csv
```

#### VM-Specific Investigation

```bash
# All findings for one VM
./dfo azure report --by-resource vm-prod-database-01

# All VMs sorted by impact
./dfo azure report --all-resources

# Export VM list to CSV
./dfo azure report --all-resources --format csv --output vms-with-findings.csv
```

#### Automated Reporting

```bash
#!/bin/bash
# Daily report generation script

DATE=$(date +%Y-%m-%d)

# Discovery and analysis
./dfo azure discover vms
./dfo azure analyze idle-vms
./dfo azure analyze low-cpu
./dfo azure analyze stopped-vms

# Generate reports
./dfo azure report --format json --output reports/summary-$DATE.json
./dfo azure report --severity high --format csv --output reports/high-priority-$DATE.csv
./dfo azure report --all-resources --format csv --output reports/vms-$DATE.csv
```

### Example: Monthly Report Workflow

```bash
#!/bin/bash
# monthly-cost-review.sh

DATE=$(date +%Y-%m)

# Discover VMs
./dfo azure discover

# Generate CSV report
./dfo azure analyze idle-vms \
  --export-format csv \
  --export-file "idle-vms-${DATE}.csv" \
  --full

# Generate JSON for API consumption
./dfo azure analyze idle-vms \
  --export-format json \
  --export-file "idle-vms-${DATE}.json" \
  --full

echo "Reports generated:"
echo "- idle-vms-${DATE}.csv"
echo "- idle-vms-${DATE}.json"
```

---

## Advanced Usage

### Custom Thresholds via Environment

Instead of using `--threshold` every time, set environment variables:

```bash
# In .env
DFO_IDLE_CPU_THRESHOLD=10.0
DFO_IDLE_DAYS=30
```

Then:

```bash
./dfo azure analyze idle-vms  # Uses 10% / 30 days
```

### Filtering Discovered VMs

```bash
# Power state filters
./dfo azure list vms --power-state running
./dfo azure list vms --power-state deallocated

# Location filter
./dfo azure list vms --location eastus

# Resource group filter
./dfo azure list vms --resource-group production-rg

# Tag filters
./dfo azure list vms --tag environment=production
./dfo azure list vms --tag-key cost-center

# Date filters
./dfo azure list vms --discovered-after 2025-01-15

# Combine filters
./dfo azure list vms --power-state running --location eastus --tag env=prod

# Sort results
./dfo azure list vms --sort name --order asc
./dfo azure list vms --sort location --order desc
```

### Searching VMs by Pattern

```bash
# Wildcard search
./dfo azure search vms "web*"
./dfo azure search vms "*prod*"

# With filters
./dfo azure search vms "api" --power-state running
```

### Understanding SKU Equivalence

dfo includes 29 legacy-to-modern VM SKU mappings. When analyzing idle VMs, if a VM uses a legacy SKU not in the Azure Retail Prices API, dfo automatically:

1. Looks up the modern equivalent (e.g., Standard_B1s → Standard_B2ls_v2)
2. Fetches pricing for the modern SKU
3. Uses that price for savings calculations
4. Shows the equivalent SKU in results

View all mappings:

```bash
# Via DuckDB
duckdb dfo.duckdb "SELECT * FROM vm_equivalence ORDER BY legacy_sku"

# Or in Python
PYTHONPATH=src python -c "
from dfo.db.duck import get_db
db = get_db()
rows = db.query('SELECT * FROM vm_equivalence ORDER BY legacy_sku')
for row in rows:
    print(f'{row[0]} → {row[1]}')
"
```

See [docs/azure_vm_selection_strategy.md](docs/azure_vm_selection_strategy.md) for complete mapping rules.

### Database Operations

```bash
# Check database status
./dfo db info

# Refresh database (drops all data)
./dfo db refresh --yes

# Query database directly
duckdb dfo.duckdb "SELECT COUNT(*) FROM vm_inventory"
duckdb dfo.duckdb "SELECT * FROM vm_idle_analysis"
```

---

## Troubleshooting

### Common Issues

#### 1. "No VMs with CPU metrics found"

**Cause**: VMs were discovered but no metrics collected, or all VMs are stopped.

**Solution**:
```bash
# Check what was discovered
./dfo azure list vms

# Check power states
./dfo azure list vms --power-state running

# Re-discover with summary
./dfo azure discover --show-summary
```

#### 2. "$0.00 savings for all VMs"

**Cause**: Azure Pricing API didn't return data, or VMs use legacy SKUs without equivalence mapping.

**Solution**:
```bash
# Check if pricing cache has data
duckdb dfo.duckdb "SELECT COUNT(*) FROM vm_pricing_cache"

# Check for unknown SKUs
duckdb dfo.duckdb "
  SELECT DISTINCT size
  FROM vm_inventory
  WHERE size NOT IN (SELECT modern_sku FROM vm_equivalence)
"

# Check analysis results for equivalent_sku column
duckdb dfo.duckdb "SELECT vm_id, equivalent_sku FROM vm_idle_analysis"
```

#### 3. "Authentication failed"

**Cause**: Invalid Azure credentials or expired service principal.

**Solution**:
```bash
# Verify credentials in .env
./dfo config --show-secrets

# Test authentication
./dfo azure test-auth

# Try Azure CLI login as fallback
az login
./dfo azure test-auth
```

#### 4. "Table does not exist"

**Cause**: Database schema is outdated or not initialized.

**Solution**:
```bash
# Refresh database
./dfo db refresh --yes

# Verify tables exist
./dfo db info
```

### Debug Mode

Enable detailed logging:

```bash
# In .env
DFO_LOG_LEVEL=DEBUG

# Then run commands
./dfo azure discover
```

### Getting Help

1. Check the docs: [docs/](docs/)
2. Review error messages carefully
3. Check database with `./dfo db info`
4. Verify config with `./dfo config`
5. Open an issue with logs and error output

---

## FAQ

### General

**Q: Will dfo make changes to my Azure resources?**

A: Not yet. Current version (Milestone 4) is read-only. Execution actions (stop/deallocate VMs) are coming in Milestone 6 and will require explicit `--no-dry-run` flag.

**Q: What permissions does dfo need?**

A: **Reader** role for all current features (discovery and analysis). **Contributor** role will be needed for execution actions in Milestone 6.

**Q: Where is my data stored?**

A: Locally in `dfo.duckdb`. No cloud storage, no external services. The database file is portable—you can copy it to another machine.

**Q: How much does dfo cost to run?**

A: Zero. dfo uses Azure's public APIs which are free for read operations. No compute costs, no storage costs.

**Q: Is dfo production-ready?**

A: Yes for discovery and analysis (Milestones 1-4). VM discovery, idle VM analysis with accurate pricing, export functionality, and rules management are tested and ready for production use.

### Technical

**Q: How does SKU equivalence work?**

A: dfo maintains a mapping table of legacy→modern SKUs. When analyzing a VM with a legacy SKU (e.g., Standard_B1s), dfo looks up the modern equivalent (Standard_B2ls_v2), fetches its pricing, and uses that for calculations. See [docs/sku_equivalence_implementation.md](docs/sku_equivalence_implementation.md).

**Q: Can I add my own SKU mappings?**

A: Yes. Edit `src/dfo/db/init_data.sql` and add entries to `vm_equivalence` table, then run `./dfo db refresh --yes`.

**Q: How accurate are the cost savings estimates?**

A: Very accurate. dfo uses Azure's official Retail Prices API and accounts for:
- Region-specific pricing
- OS type (Linux vs Windows)
- Current pricing (not historical)
- Legacy SKU equivalence

**Q: Can I use dfo with multiple subscriptions?**

A: Not yet. Currently supports one subscription at a time (configured in `.env`). Multi-subscription support is planned for Phase 2.

**Q: How do I add a new analysis type?**

A: See [docs/rules_driven_cli.md](docs/rules_driven_cli.md). In short:
1. Create Python module in `src/dfo/analyze/`
2. Add rule entry to `optimization_rules.json`
3. Done!

### Usage

**Q: How often should I run discovery?**

A: Weekly or monthly. VMs change infrequently, so daily runs aren't necessary. Run before each analysis to ensure fresh data.

**Q: What's the difference between basic and full export?**

A:
- **Basic** (9 fields): Human-friendly summary for management
- **Full** (16 fields): Complete data including tags, timestamps, OS type, priority

**Q: Can I export to Excel?**

A: Export to CSV, then open in Excel. CSV files work perfectly in Excel/Google Sheets.

**Q: How do I disable a rule?**

A: `./dfo rules disable <key>` or set `"enabled": false` in `optimization_rules.json`.

**Q: What happens if I run analyze without discovering first?**

A: The analysis will run on existing data in the database. If the database is empty, you'll get "No VMs found". Always discover first.

---

## Next Steps

- **Explore rules**: `./dfo rules list`
- **Read architecture docs**: [docs/rules_driven_cli.md](docs/rules_driven_cli.md)
- **Check the roadmap**: [docs/ROADMAP.md](docs/ROADMAP.md)
- **Review code style**: [docs/CODE_STYLE.md](docs/CODE_STYLE.md)
- **Join the community**: [GitHub Issues](https://github.com/your-org/dfo/issues)

---

**Ready to optimize your Azure costs? Start with discovery!** 💰☁️

```bash
./dfo azure discover
./dfo azure analyze idle-vms
./dfo azure analyze idle-vms --export-format csv --export-file savings-report.csv --full
```
