# dfo User Guide

**DevFinOps (dfo)** - Azure cloud cost optimization made simple.

## What is dfo?

dfo is a command-line tool that helps you identify and reduce Azure cloud costs by finding underutilized virtual machines (VMs). It analyzes your Azure resources, identifies idle or underutilized VMs, and helps you take action to reduce costs.

### What can dfo do?

- 🔍 **Discover** Azure VMs across your subscription
- 📊 **Analyze** CPU usage to identify idle resources
- 💰 **Estimate** potential monthly savings
- 📋 **Report** findings in console or JSON format
- ⚡ **Execute** cost-saving actions (stop/deallocate VMs)
- 🔒 **Safe by default** with dry-run mode and confirmations

---

## Quick Start

### Prerequisites

- Azure subscription with VMs
- Azure service principal credentials (see [Setup Azure Credentials](#setup-azure-credentials))
- Python 3.10+ and conda installed

### Installation

1. Clone the repository:
```bash
cd /path/to/dfo
```

2. Create and activate the conda environment:
```bash
conda env create -f environment.yml
conda activate dfo
```

3. Configure your Azure credentials (see [Configuration](#configuration))

4. Initialize the database:
```bash
./dfo.sh db init
```

5. Test your Azure connection:
```bash
./dfo.sh azure test-auth
```

You're ready to start optimizing! 🎉

---

## Configuration

### Setup Azure Credentials

dfo needs credentials to access your Azure subscription. You have two options:

#### Option 1: Service Principal (Recommended)

1. Create a service principal in Azure:
```bash
az ad sp create-for-rbac --name "dfo-service-principal" \
  --role Reader \
  --scopes /subscriptions/YOUR_SUBSCRIPTION_ID
```

2. Copy the output values to your `.env` file

#### Option 2: Azure CLI (For Testing)

Simply run `az login` and dfo will use your Azure CLI credentials.

### Environment File Setup

1. Copy the example file:
```bash
cp .env.example .env
```

2. Edit `.env` with your Azure credentials:
```bash
# Azure Authentication
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
AZURE_SUBSCRIPTION_ID=your-subscription-id

# Analysis Configuration (optional - these are defaults)
DFO_IDLE_CPU_THRESHOLD=5.0        # CPU % below which a VM is considered idle
DFO_IDLE_DAYS=14                  # Days of idle CPU to flag a VM
DFO_DRY_RUN_DEFAULT=true          # Safety: dry-run enabled by default

# Database Configuration (optional)
DFO_DUCKDB_FILE=./dfo.duckdb      # Where to store local data

# Logging Configuration (optional)
DFO_LOG_LEVEL=INFO                # DEBUG, INFO, WARNING, ERROR
```

### Verify Configuration

Check that your configuration is loaded correctly:
```bash
./dfo.sh config
```

This shows all settings (with secrets masked for security).

To see unmasked values:
```bash
./dfo.sh config --show-secrets
```

---

## Basic Workflow

### 1. Setup (One-time)

```bash
# Initialize the database
./dfo.sh db init

# Test Azure authentication
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
┠─────────────────────────────────────┨
┃ Authentication test passed!         ┃
┃                                     ┃
┃ All Azure clients initialized       ┃
┃ successfully. You are ready to      ┃
┃ proceed with VM discovery.          ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

### 2. Discover (Coming in Milestone 3)

Scan your Azure subscription for VMs and collect CPU metrics:

```bash
./dfo.sh azure discover vms
```

**What happens:**
- Lists all VMs in your subscription
- Collects 14 days of CPU metrics for each VM
- Stores data in local DuckDB database

**Check what was discovered:**
```bash
./dfo.sh db info
```

### 3. Analyze (Coming in Milestone 4)

Analyze VMs to identify idle resources:

```bash
./dfo.sh azure analyze idle-vms
```

**What happens:**
- Calculates average CPU usage over the collection period
- Identifies VMs with CPU < 5% for 14+ days
- Estimates monthly savings for each idle VM
- Assigns severity levels (critical/high/medium/low)
- Stores analysis results in database

### 4. Report (Coming in Milestone 5)

View cost optimization opportunities:

```bash
# Console report (Rich formatted table)
./dfo.sh azure report idle-vms
```

**Example output:**
```
                    Idle VM Analysis Results
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┓
┃ VM Name      ┃ Resource Group ┃ CPU % ┃ Idle Days┃ Savings  ┃ Severity ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━┩
│ prod-web-01  │ production-rg  │ 1.2%  │ 14       │ $856/mo  │ CRITICAL │
│ dev-test-vm  │ development-rg │ 3.5%  │ 21       │ $124/mo  │ HIGH     │
│ backup-srv   │ backup-rg      │ 4.8%  │ 14       │ $65/mo   │ MEDIUM   │
└──────────────┴────────────────┴───────┴──────────┴──────────┴──────────┘

Total Potential Savings: $1,045/month
```

**Export to JSON:**
```bash
./dfo.sh azure report idle-vms --format json --output results.json
```

### 5. Execute (Coming in Milestone 6)

Take action to reduce costs:

```bash
# Dry-run (see what would happen - NO changes made)
./dfo.sh azure execute stop-idle-vms

# Actually stop VMs (requires confirmation)
./dfo.sh azure execute stop-idle-vms --no-dry-run

# Auto-confirm for automation/CI-CD
./dfo.sh azure execute stop-idle-vms --no-dry-run --yes

# Only act on critical and high severity VMs
./dfo.sh azure execute stop-idle-vms --no-dry-run --min-severity high
```

**Safety features:**
- ✓ Dry-run enabled by default
- ✓ Requires confirmation prompt
- ✓ All actions logged to database
- ✓ Severity filtering to control scope

---

## Command Reference

### Top-Level Commands

#### `dfo version`
Display version information.

```bash
./dfo.sh version
```

#### `dfo config`
Display current configuration.

```bash
./dfo.sh config              # Masked secrets
./dfo.sh config --show-secrets  # Show actual values
```

---

### Database Commands (`dfo db`)

#### `dfo db init`
Initialize the database schema. Creates a new DuckDB file with required tables.

```bash
./dfo.sh db init
```

**When to use:** First time setup, or after deleting the database file.

**Tables created:**
- `vm_inventory` - Discovered VMs and metrics
- `vm_idle_analysis` - Analysis results
- `vm_actions` - Executed actions log

#### `dfo db info`
Show database statistics.

```bash
./dfo.sh db info
```

**Output:** Table names, record counts, database size.

#### `dfo db refresh`
Drop and recreate all tables (⚠️ deletes all data).

```bash
./dfo.sh db refresh         # Requires confirmation
./dfo.sh db refresh --yes   # Skip confirmation
```

**When to use:**
- Reset database to clean state
- Apply schema changes during development
- Clear all data before fresh discovery

---

### Azure Commands (`dfo azure`)

#### `dfo azure test-auth` ✓ Available Now
Test Azure authentication and SDK client creation.

```bash
./dfo.sh azure test-auth
```

**What it does:**
1. Loads configuration from .env
2. Authenticates to Azure
3. Creates Compute and Monitor clients
4. Reports success or failure

**When to use:**
- Verify Azure credentials are correct
- Troubleshoot authentication issues
- Validate setup after configuration changes

---

#### `dfo azure discover <resource>` ⏳ Coming in Milestone 3
Discover Azure resources and store in database.

```bash
./dfo.sh azure discover vms
```

**What it does:**
- Lists all VMs in your subscription
- Retrieves VM metadata (name, size, location, tags)
- Collects 14 days of CPU metrics
- Stores everything in `vm_inventory` table

**Options:**
- `<resource>` - Resource type to discover (currently only `vms`)

**Time:** ~2-5 minutes for 100 VMs

---

#### `dfo azure analyze <analysis-type>` ⏳ Coming in Milestone 4
Analyze resources for optimization opportunities.

```bash
./dfo.sh azure analyze idle-vms
```

**What it does:**
- Reads VM data from `vm_inventory`
- Calculates average CPU usage
- Identifies VMs below threshold for specified days
- Estimates monthly cost savings
- Assigns severity levels
- Stores results in `vm_idle_analysis` table

**Options:**
- `<analysis-type>` - Type of analysis (currently only `idle-vms`)

**Time:** < 1 minute for 100 VMs

---

#### `dfo azure report <report-type>` ⏳ Coming in Milestone 5
Generate reports from analysis results.

```bash
./dfo.sh azure report idle-vms [OPTIONS]
```

**Options:**
- `--format <format>` - Output format: `console` (default) or `json`
- `--output <file>` - Write to file instead of stdout

**Examples:**
```bash
# Console report (default)
./dfo.sh azure report idle-vms

# JSON output to stdout
./dfo.sh azure report idle-vms --format json

# Save to file
./dfo.sh azure report idle-vms --format json --output report-$(date +%Y%m%d).json
```

---

#### `dfo azure execute <action>` ⏳ Coming in Milestone 6
Execute remediation actions on Azure resources.

```bash
./dfo.sh azure execute stop-idle-vms [OPTIONS]
```

**Options:**
- `--dry-run` / `--no-dry-run` - Dry-run mode (default: enabled)
- `--yes` / `-y` - Skip confirmation prompt
- `--min-severity <level>` - Minimum severity: `low`, `medium`, `high`, `critical`

**Safety Features:**
1. **Dry-run by default** - No changes made unless `--no-dry-run`
2. **Confirmation prompt** - Requires user approval (unless `--yes`)
3. **Action logging** - All actions logged to `vm_actions` table
4. **Severity filtering** - Control scope with `--min-severity`

**Examples:**
```bash
# See what would happen (dry-run)
./dfo.sh azure execute stop-idle-vms

# Actually stop VMs (with confirmation)
./dfo.sh azure execute stop-idle-vms --no-dry-run

# Stop only critical VMs without prompting
./dfo.sh azure execute stop-idle-vms --no-dry-run --yes --min-severity critical

# Automation-friendly (use in scripts)
./dfo.sh azure execute stop-idle-vms --no-dry-run --yes --min-severity high
```

**Actions performed:**
- `stop` - Stop VM (keeps it allocated, faster restart)
- `deallocate` - Deallocate VM (releases compute, more savings)

---

## Typical Use Cases

### Use Case 1: Monthly Cost Review

Run this monthly to identify optimization opportunities:

```bash
# Discover current state
./dfo.sh azure discover vms

# Analyze for idle VMs
./dfo.sh azure analyze idle-vms

# Generate report
./dfo.sh azure report idle-vms --format json --output monthly-review-$(date +%Y-%m).json

# Review the report and decide on actions
```

### Use Case 2: Automated Cost Optimization

Set up a weekly cron job to automatically stop idle VMs:

```bash
#!/bin/bash
# Weekly cost optimization script

cd /path/to/dfo
source activate dfo

# Discover and analyze
./dfo.sh azure discover vms
./dfo.sh azure analyze idle-vms

# Stop critical idle VMs (>$500/month savings)
./dfo.sh azure execute stop-idle-vms \
  --no-dry-run \
  --yes \
  --min-severity critical

# Generate report
./dfo.sh azure report idle-vms --format json --output /var/log/dfo/report-$(date +%Y%m%d).json
```

### Use Case 3: Development Environment Cleanup

Stop all idle dev/test VMs at end of week:

```bash
# Discover and analyze
./dfo.sh azure discover vms
./dfo.sh azure analyze idle-vms

# Review findings
./dfo.sh azure report idle-vms

# Stop ALL idle VMs (not just critical)
./dfo.sh azure execute stop-idle-vms --no-dry-run --min-severity low
```

### Use Case 4: Cost Report for Management

Generate a monthly cost optimization report:

```bash
#!/bin/bash
# Monthly cost report for management

DATE=$(date +%Y-%m)

./dfo.sh azure discover vms
./dfo.sh azure analyze idle-vms
./dfo.sh azure report idle-vms --format json --output cost-report-$DATE.json

# Upload to S3/Azure Blob/etc for dashboard
# aws s3 cp cost-report-$DATE.json s3://finops-reports/
```

---

## Understanding the Results

### Severity Levels

dfo assigns severity based on estimated monthly savings:

| Severity | Monthly Savings | Recommended Action |
|----------|----------------|-------------------|
| 🔴 **CRITICAL** | > $500 | Immediate review & action |
| 🟠 **HIGH** | $200 - $500 | Review within 1 week |
| 🟡 **MEDIUM** | $50 - $200 | Review within 1 month |
| 🟢 **LOW** | < $50 | Monitor for trends |

### CPU Threshold

By default, VMs with average CPU < 5% for 14 days are flagged as idle.

You can adjust this in `.env`:
```bash
DFO_IDLE_CPU_THRESHOLD=3.0  # More sensitive (more VMs flagged)
DFO_IDLE_CPU_THRESHOLD=10.0 # Less sensitive (fewer VMs flagged)
DFO_IDLE_DAYS=7             # Shorter observation period
```

### Cost Savings Calculation

Savings are estimated based on:
- VM size/SKU pricing
- Region (location)
- Current power state
- Assumption: 730 hours/month

**Note:** Actual savings may vary based on:
- Reserved instances
- Spot VMs
- Azure Hybrid Benefit
- Enterprise agreements

---

## Troubleshooting

### Authentication Errors

**Problem:** `Azure authentication failed`

**Solutions:**
1. Check `.env` file has correct credentials:
   ```bash
   ./dfo.sh config --show-secrets
   ```

2. Verify service principal exists and has permissions:
   ```bash
   az ad sp show --id $AZURE_CLIENT_ID
   ```

3. Test authentication:
   ```bash
   ./dfo.sh azure test-auth
   ```

4. Try Azure CLI authentication:
   ```bash
   az login
   ./dfo.sh azure test-auth
   ```

---

### Database Errors

**Problem:** `Database tables already exist`

**Solution:**
```bash
# If you want to keep data, check what's there:
./dfo.sh db info

# If you want to start fresh:
./dfo.sh db refresh --yes
```

---

**Problem:** `Database file not found`

**Solution:**
```bash
./dfo.sh db init
```

---

### Permission Errors

**Problem:** `Permission denied` when discovering VMs

**Solution:** Ensure service principal has Reader role:
```bash
az role assignment create \
  --assignee $AZURE_CLIENT_ID \
  --role Reader \
  --scope /subscriptions/$AZURE_SUBSCRIPTION_ID
```

---

### No VMs Found

**Problem:** Discovery returns 0 VMs

**Possible causes:**
1. Wrong subscription ID in `.env`
2. No VMs in the subscription
3. Service principal lacks permissions

**Solution:**
```bash
# Verify subscription
az account show

# List VMs manually
az vm list --output table

# Check service principal permissions
az role assignment list --assignee $AZURE_CLIENT_ID
```

---

## Best Practices

### 1. Start with Dry-Run
Always test with dry-run first:
```bash
./dfo.sh azure execute stop-idle-vms  # See what would happen
```

### 2. Use Severity Filtering
Start with critical VMs only:
```bash
./dfo.sh azure execute stop-idle-vms --no-dry-run --min-severity critical
```

### 3. Regular Cadence
Run discovery and analysis regularly:
- **Daily**: For active development environments
- **Weekly**: For production environments
- **Monthly**: For cost reporting

### 4. Backup Your Data
The DuckDB file contains your analysis history:
```bash
cp dfo.duckdb backups/dfo-$(date +%Y%m%d).duckdb
```

### 5. Monitor Action Logs
Review executed actions:
```bash
./dfo.sh db info  # Check vm_actions table
```

### 6. Adjust Thresholds
Fine-tune based on your workloads:
```bash
# Edit .env
DFO_IDLE_CPU_THRESHOLD=3.0  # For stricter detection
DFO_IDLE_DAYS=7             # For quicker action
```

### 7. Tag Your VMs
Use Azure tags to:
- Exclude VMs from analysis (e.g., `dfo:skip=true`)
- Identify ownership (e.g., `team:platform`)
- Track cost centers (e.g., `cost-center:engineering`)

---

## FAQ

### Q: Will dfo make changes to my Azure resources?

**A:** Only if you explicitly run `execute` commands with `--no-dry-run`. All other commands are read-only. Dry-run is enabled by default for safety.

### Q: What permissions does dfo need?

**A:**
- **Reader** role for discovery and analysis (read-only)
- **Contributor** role for execute actions (start/stop VMs)

### Q: Where is my data stored?

**A:** All data is stored locally in `dfo.duckdb` (configurable via `DFO_DUCKDB_FILE`). No cloud storage required.

### Q: Can I use dfo with multiple Azure subscriptions?

**A:** Currently, dfo works with one subscription at a time (specified in `AZURE_SUBSCRIPTION_ID`). To analyze multiple subscriptions, create separate `.env` files and databases for each.

### Q: How accurate are the cost savings estimates?

**A:** Estimates are based on public Azure pricing for standard VMs. Actual savings may vary based on reserved instances, spot VMs, hybrid benefits, and enterprise agreements.

### Q: Can dfo automatically restart VMs?

**A:** Not currently. dfo focuses on identifying and stopping idle resources. Restarting VMs should be done manually or through your existing automation.

### Q: What happens to stopped VMs?

**A:**
- **Stop**: VM is stopped but still allocated. You still pay for storage. Quick to restart.
- **Deallocate**: VM is deallocated, no compute charges. Storage charges remain. Slower to restart.

### Q: Is dfo production-ready?

**A:** dfo is currently in MVP development:
- ✅ **Milestones 1-2 Complete**: Configuration, database, authentication
- ⏳ **Milestones 3-6 In Progress**: Discovery, analysis, reporting, execution

Use with caution in production. Test thoroughly in dev/test environments first.

---

## Roadmap

### Current Status (Milestones 1-2) ✅

- ✅ Configuration management
- ✅ DuckDB integration
- ✅ Azure authentication
- ✅ CLI foundation
- ✅ Test infrastructure

### Coming Soon

**Milestone 3 (Week 2):** Discovery Layer
- VM discovery and metric collection
- Store in local database

**Milestone 4 (Week 3):** Analysis Layer
- Idle VM detection
- Savings calculation

**Milestone 5 (Week 3-4):** Reporting Layer
- Console reports with Rich tables
- JSON export

**Milestone 6 (Week 4):** Execution Layer
- Stop/deallocate VMs
- Dry-run mode
- Action logging

**Phase 2 (Future):**
- Multi-cloud support (AWS, GCP)
- Additional resource types (databases, storage)
- Web dashboard
- API endpoints
- LLM-powered recommendations

---

## Getting Help

### Documentation
- **User Guide**: This file
- **Developer Guide**: `CLAUDE.md`
- **Architecture**: `ARCHITECTURE.md`
- **Code Style**: `CODE_STYLE.md`
- **Milestones**: `MVP.md`

### Support
- Report issues: Create an issue in the repository
- Feature requests: Open a discussion
- Questions: Check the FAQ first

---

## Contributing

We welcome contributions! See `CONTRIBUTING.md` for guidelines.

---

## License

[Add your license information here]

---

## Changelog

### v0.0.2 (Current)
- ✅ Milestone 1: Foundation & Infrastructure
- ✅ Milestone 2: Authentication & Azure Provider
- Added `azure test-auth` command
- 75 tests, 97% coverage

### v0.0.1
- Initial scaffold

---

**Happy optimizing! 💰☁️**
