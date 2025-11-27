# DFO Quick Start Guide

> **Get up and running with dfo in 5 minutes!**

This guide gets you started with dfo (DevFinOps) - a CLI tool for Azure cost optimization.

---

## Prerequisites

- **Python 3.11+**
- **Conda** (recommended) or virtualenv
- **Azure subscription** with VMs to analyze

---

## 1. Install

```bash
# Clone the repository
git clone https://github.com/vedanta/dfo.git
cd dfo

# Create and activate conda environment
conda env create -f environment.yml
conda activate dfo

# Install dfo in editable mode
pip install -e .

# Verify installation
./dfo version
```

**Expected output:**
```
dfo version 0.2.0
```

---

## 2. Configure Azure Authentication

### Option A: Azure CLI (Easiest)

```bash
# Login to Azure
az login

# Set your subscription
az account set --subscription "Your Subscription Name"

# Verify
az account show
```

### Option B: Service Principal (For Automation)

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your credentials
nano .env
```

Required environment variables:
```bash
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
AZURE_SUBSCRIPTION_ID=your-subscription-id
```

---

## 3. Initialize Database

```bash
# Create local DuckDB database
./dfo db init

# Verify
./dfo db info
```

**Expected output:**
```
Database: ./dfo.duckdb
Tables: 10 tables created
Status: Ready
```

---

## 4. Discover VMs

```bash
# Discover all VMs in your subscription
./dfo azure discover vms
```

**What this does:**
- Lists all VMs in your Azure subscription
- Collects CPU metrics for the last 14 days
- Stores data in local DuckDB database

**Example output:**
```
Discovering VMs in subscription...
✓ Found 50 VMs across 5 resource groups
✓ Collected CPU metrics (14 days)
✓ Saved to database

Discovery complete!
```

**Time:** ~2-5 minutes for 50 VMs

---

## 5. Analyze for Cost Savings

### Find Idle VMs (< 5% CPU)

```bash
./dfo azure analyze idle-vms
```

**Example output:**
```
Analyzing idle VMs...
✓ Found 12 idle VMs
✓ Estimated savings: $4,320/month

Severity breakdown:
  Critical: 5 VMs ($2,500/mo)
  High: 4 VMs ($1,200/mo)
  Medium: 3 VMs ($620/mo)
```

### Find Rightsizing Opportunities (< 20% CPU)

```bash
./dfo azure analyze low-cpu
```

### Find Stopped VMs (30+ days)

```bash
./dfo azure analyze stopped-vms
```

---

## 6. View Reports

### Console Report (Summary)

```bash
./dfo azure report
```

**Example output:**
```
╭─────────── Cost Optimization Summary ───────────╮
│                                                  │
│  Total Findings: 15                              │
│  Estimated Monthly Savings: $5,280               │
│  Annual Savings: $63,360                         │
│                                                  │
╰──────────────────────────────────────────────────╯

Findings by Severity:
┌──────────┬───────┬──────────────┐
│ Severity │ Count │ Savings/Mo   │
├──────────┼───────┼──────────────┤
│ Critical │   6   │   $3,200     │
│ High     │   5   │   $1,480     │
│ Medium   │   4   │    $600      │
└──────────┴───────┴──────────────┘
```

### Rule-Specific Report

```bash
./dfo azure report --by-rule idle-vms
```

### Export to JSON

```bash
./dfo azure report --format json --output report.json
```

### Export to CSV

```bash
./dfo azure report --format csv --output findings.csv
```

---

## 7. Create Execution Plan

**Safety First:** dfo uses a plan-based workflow with validation, approval, and dry-run.

```bash
# Create a plan from analysis
./dfo azure plan create --from-analysis idle-vms

# Output:
# ✓ Created plan 'plan-2025-01-26' with 12 actions
# Plan ID: plan-abc123
```

### View Plan

```bash
./dfo azure plan show plan-abc123 --detail
```

### Validate Plan

```bash
# Validate with Azure (checks VMs exist, correct state, permissions)
./dfo azure plan validate plan-abc123
```

**Example output:**
```
Validating plan with Azure...
✓ 11/12 actions valid
⚠ 1 warning: VM 'test-vm-5' already stopped

Validation complete!
```

### Approve Plan

```bash
./dfo azure plan approve plan-abc123
```

### Execute Plan (Dry-Run)

```bash
# Safe dry-run (default, no actual changes)
./dfo azure plan execute plan-abc123
```

**Example output:**
```
Executing plan (DRY-RUN MODE)...

Action 1/12: Stop VM 'prod-vm-1'
  ✓ Would stop VM
  ✓ Savings: $320/month

Action 2/12: Deallocate VM 'test-vm-2'
  ✓ Would deallocate VM
  ✓ Savings: $180/month

...

DRY-RUN SUMMARY:
  Would execute: 11 actions
  Would skip: 1 action (already stopped)
  Estimated savings: $4,100/month
```

### Execute Plan (Live)

```bash
# LIVE execution (makes real changes!)
./dfo azure plan execute plan-abc123 --force
```

**⚠️ WARNING:** This makes real changes to your Azure resources!

---

## 8. Rollback (If Needed)

```bash
# Dry-run rollback (see what would happen)
./dfo azure plan rollback plan-abc123

# Live rollback (restart stopped VMs)
./dfo azure plan rollback plan-abc123 --force
```

---

## Common Commands Cheat Sheet

```bash
# Database
./dfo db init              # Initialize database
./dfo db info              # Show database stats

# Discovery
./dfo azure discover vms   # Discover VMs + metrics

# Inventory
./dfo azure list           # List all VMs
./dfo azure show <vm>      # Show VM details
./dfo azure search <query> # Search VMs

# Analysis
./dfo azure analyze idle-vms      # Find idle VMs
./dfo azure analyze low-cpu       # Find rightsizing opportunities
./dfo azure analyze stopped-vms   # Find stopped VMs
./dfo azure analyze --list        # List all analyses

# Reporting
./dfo azure report                     # Summary view
./dfo azure report --by-rule idle-vms  # Rule-specific view
./dfo azure report --format json       # JSON export
./dfo azure report --format csv        # CSV export
./dfo azure report --severity critical # Filter by severity

# Execution
./dfo azure plan create --from-analysis idle-vms  # Create plan
./dfo azure plan list                              # List plans
./dfo azure plan show <plan-id>                    # Show plan
./dfo azure plan validate <plan-id>                # Validate plan
./dfo azure plan approve <plan-id>                 # Approve plan
./dfo azure plan execute <plan-id>                 # Dry-run (safe)
./dfo azure plan execute <plan-id> --force         # Live (WARNING!)
./dfo azure plan status <plan-id>                  # Check status
./dfo azure plan rollback <plan-id> --force        # Rollback

# Configuration
./dfo config               # Show config (secrets masked)
./dfo version              # Show version
```

---

## Typical Workflow

```bash
# 1. Setup (one-time)
conda activate dfo
./dfo db init

# 2. Discovery (weekly)
./dfo azure discover vms

# 3. Analysis (weekly)
./dfo azure analyze idle-vms
./dfo azure analyze low-cpu
./dfo azure analyze stopped-vms

# 4. Review (weekly)
./dfo azure report
./dfo azure report --format json --output weekly-report.json

# 5. Execute (as needed)
./dfo azure plan create --from-analysis idle-vms
./dfo azure plan validate <plan-id>
./dfo azure plan approve <plan-id>
./dfo azure plan execute <plan-id>  # Dry-run first!
./dfo azure plan execute <plan-id> --force  # Live if happy with dry-run
```

---

## Configuration Options

### Environment Variables

```bash
# Analysis thresholds
DFO_IDLE_CPU_THRESHOLD=5.0     # % CPU to consider idle (default: 5.0)
DFO_IDLE_DAYS=14               # Days below threshold (default: 14)

# Database
DFO_DUCKDB_FILE=./dfo.duckdb   # Database file path

# Azure (if not using az login)
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
AZURE_SUBSCRIPTION_ID=...
```

### Show Current Config

```bash
./dfo config
./dfo config --show-secrets  # Show unmasked secrets
```

---

## Troubleshooting

### "Database not found"

```bash
./dfo db init
```

### "Authentication failed"

```bash
# Using Azure CLI
az login
az account set --subscription "Your Subscription"

# Using Service Principal
# Check .env file has correct credentials
```

### "No VMs found"

```bash
# Verify subscription
az account show

# Check permissions (need Reader + Monitoring Reader roles)
az role assignment list --assignee <client-id>
```

### "Analysis found 0 results"

```bash
# Check thresholds might be too strict
./dfo azure analyze idle-vms --cpu-threshold 10.0 --idle-days 7
```

---

## Next Steps

### Learn More

- **[README.md](README.md)** - Full documentation
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture
- **[docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md)** - Testing guide
- **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - Detailed troubleshooting

### Advanced Features

- **Multi-format Reports** - Export to JSON, CSV for integration
- **Plan-Based Execution** - Safe execution with validation and rollback
- **Rules Engine** - 29 VM optimization rules, 15 storage rules
- **Inventory Browse** - Search, filter, sort VMs

### Contribute

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for contribution guidelines.

---

## Support

- **Issues:** https://github.com/vedanta/dfo/issues
- **Documentation:** [docs/](docs/)
- **Questions:** Open issue with `question` label

---

## Summary

**You've learned:**
- ✅ Install dfo
- ✅ Configure Azure authentication
- ✅ Discover VMs and collect metrics
- ✅ Analyze for cost savings
- ✅ Generate reports
- ✅ Create and execute plans safely
- ✅ Rollback if needed

**Time to value:** ~10 minutes to first cost savings report!

---

**Version:** v0.2.0 (Phase 1 MVP Complete)
**Last Updated:** 2025-01-26
