# DFO Troubleshooting Guide

> **Version:** 1.0
> **Last Updated:** 2025-01-26
> **Status:** ✅ Current

This guide helps you diagnose and resolve common issues with dfo (DevFinOps).

---

## Table of Contents

1. [Installation Issues](#installation-issues)
2. [Configuration Problems](#configuration-problems)
3. [Database Errors](#database-errors)
4. [Azure Authentication](#azure-authentication)
5. [CLI Command Errors](#cli-command-errors)
6. [Discovery Issues](#discovery-issues)
7. [Analysis Problems](#analysis-problems)
8. [Execution Failures](#execution-failures)
9. [Test Failures](#test-failures)
10. [Performance Issues](#performance-issues)
11. [Getting Help](#getting-help)

---

## Installation Issues

### Problem: `pip install -e .` fails

**Symptoms:**
```
ERROR: Could not find a version that satisfies the requirement...
```

**Solutions:**

**1. Check Python version:**
```bash
python --version  # Should be 3.11+

# If too old
conda install python=3.11
```

**2. Update pip:**
```bash
pip install --upgrade pip setuptools wheel
```

**3. Install dependencies manually:**
```bash
# Install from requirements file
pip install -r requirements.txt

# Then install dfo
pip install -e .
```

**4. Check conda environment:**
```bash
# Recreate environment
conda deactivate
conda env remove -n dfo
conda env create -f environment.yml
conda activate dfo
```

---

### Problem: `./dfo` command not found

**Symptoms:**
```bash
./dfo version
# zsh: no such file or directory: ./dfo
```

**Solutions:**

**1. Wrong directory:**
```bash
# Must be in project root
pwd  # Should show .../dfo

# Navigate to root
cd /path/to/dfo
```

**2. Script not executable:**
```bash
chmod +x dfo
```

**3. Use alternative methods:**
```bash
# Method 1: Python module
python -m dfo.cli version

# Method 2: After pip install -e .
dfo version
```

---

### Problem: Import errors after installation

**Symptoms:**
```python
ModuleNotFoundError: No module named 'dfo'
```

**Solutions:**

**1. Verify installation:**
```bash
pip list | grep dfo
# Should show: dfo 0.2.0 /path/to/dfo/src
```

**2. Reinstall in editable mode:**
```bash
pip uninstall dfo
pip install -e .
```

**3. Check PYTHONPATH:**
```bash
# Add to .bashrc or .zshrc if needed
export PYTHONPATH="${PYTHONPATH}:/path/to/dfo/src"
```

---

## Configuration Problems

### Problem: Configuration not loading

**Symptoms:**
```
Configuration validation error
```

**Solutions:**

**1. Check .env file exists:**
```bash
ls -la .env
# If missing, copy example
cp .env.example .env
```

**2. Validate .env format:**
```bash
# Check for syntax errors
cat .env | grep -v "^#" | grep "="

# Common issues:
# - Missing quotes for values with spaces
# - Extra spaces around =
# - Invalid environment variable names
```

**3. Use minimal configuration:**
```bash
# .env
DFO_DUCKDB_FILE=./dfo.duckdb
DFO_IDLE_CPU_THRESHOLD=5.0
DFO_IDLE_DAYS=14
```

**4. Verify configuration:**
```bash
./dfo config
./dfo config --show-secrets  # Check sensitive values
```

---

### Problem: Azure credentials not found

**Symptoms:**
```
DefaultAzureCredential failed to retrieve a token
```

**Solutions:**

**See [Azure Authentication](#azure-authentication) section below.**

---

### Problem: Invalid threshold values

**Symptoms:**
```
ValidationError: CPU threshold must be between 0 and 100
```

**Solutions:**

```bash
# Check .env file
cat .env | grep THRESHOLD

# Valid ranges:
# DFO_IDLE_CPU_THRESHOLD=5.0  # 0.0 to 100.0
# DFO_IDLE_DAYS=14            # Positive integer
```

---

## Database Errors

### Problem: Database file not found

**Symptoms:**
```
FileNotFoundError: Database not found at ./dfo.duckdb
Run 'dfo db init' to create it.
```

**Solutions:**

```bash
# Initialize database
./dfo db init

# Verify creation
ls -lh dfo.duckdb

# Check database info
./dfo db info
```

---

### Problem: Database corruption

**Symptoms:**
```
duckdb.IOException: Failed to read from file
IO Error: File header is invalid
```

**Solutions:**

**1. Refresh database (destructive):**
```bash
# WARNING: This deletes all data
./dfo db refresh --yes

# Re-discover VMs
./dfo azure discover vms
```

**2. Backup and recreate:**
```bash
# Backup old database
mv dfo.duckdb dfo.duckdb.backup

# Create new database
./dfo db init

# If still failing, check disk space
df -h .
```

**3. Check file permissions:**
```bash
ls -l dfo.duckdb
# Should be readable/writable by current user
chmod 644 dfo.duckdb
```

---

### Problem: Schema mismatch

**Symptoms:**
```
RuntimeError: Column not found: new_column
```

**Solutions:**

```bash
# Database schema is outdated
# Refresh to latest schema (WARNING: deletes data)
./dfo db refresh --yes

# Or migrate data manually (advanced)
# 1. Export data
./dfo azure report --format json --output backup.json

# 2. Refresh schema
./dfo db refresh --yes

# 3. Re-import data (custom script needed)
```

---

### Problem: Database locked

**Symptoms:**
```
duckdb.IOException: Could not acquire lock on database file
```

**Solutions:**

**1. Check for other processes:**
```bash
# Find processes using dfo.duckdb
lsof dfo.duckdb

# Kill if needed
kill <PID>
```

**2. Remove lock file:**
```bash
# DuckDB lock files (if exist)
rm dfo.duckdb.wal
```

**3. Close other connections:**
```python
# If using Python shell
db.close()
```

---

## Azure Authentication

### Problem: DefaultAzureCredential fails

**Symptoms:**
```
azure.core.exceptions.ClientAuthenticationError:
DefaultAzureCredential failed to retrieve a token
```

**Solutions:**

**1. Use Azure CLI login:**
```bash
# Login with browser
az login

# Verify
az account show

# Set subscription
az account set --subscription "Your Subscription Name"
```

**2. Use Service Principal (recommended for automation):**
```bash
# Set in .env file
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
AZURE_SUBSCRIPTION_ID=your-subscription-id
```

**3. Check credential order:**
```python
# DefaultAzureCredential tries in order:
# 1. Environment variables (AZURE_CLIENT_ID, etc.)
# 2. Managed Identity (if running on Azure)
# 3. Azure CLI credentials (az login)
# 4. Visual Studio Code credentials
# 5. Azure PowerShell credentials

# Troubleshoot by enabling logging
export AZURE_LOG_LEVEL=DEBUG
./dfo azure discover vms
```

**4. Verify permissions:**
```bash
# Service Principal needs these roles:
# - Reader (to list VMs)
# - Monitoring Reader (to read metrics)
# - Contributor (to execute actions like stop/start)

# Check role assignments
az role assignment list --assignee <client-id> --all
```

---

### Problem: Insufficient permissions

**Symptoms:**
```
AuthorizationFailed: The client does not have authorization
to perform action 'Microsoft.Compute/virtualMachines/read'
```

**Solutions:**

```bash
# Grant necessary permissions
az role assignment create \
  --assignee <client-id> \
  --role "Reader" \
  --scope "/subscriptions/<subscription-id>"

az role assignment create \
  --assignee <client-id> \
  --role "Monitoring Reader" \
  --scope "/subscriptions/<subscription-id>"

# For execution capabilities
az role assignment create \
  --assignee <client-id> \
  --role "Contributor" \
  --scope "/subscriptions/<subscription-id>/resourceGroups/<rg-name>"
```

---

### Problem: Subscription not found

**Symptoms:**
```
SubscriptionNotFound: The subscription 'xxx' could not be found
```

**Solutions:**

```bash
# List available subscriptions
az account list --output table

# Set correct subscription
az account set --subscription "subscription-name-or-id"

# Update .env
AZURE_SUBSCRIPTION_ID=correct-subscription-id
```

---

## CLI Command Errors

### Problem: Command not found

**Symptoms:**
```bash
./dfo azure discover vms
# Error: No such command "azure"
```

**Solutions:**

**1. Check installation:**
```bash
./dfo --help
# Should show all available commands

# Reinstall if needed
pip install -e .
```

**2. Check CLI structure:**
```bash
# Correct command structure
./dfo <command-group> <subcommand> [options]

# Examples:
./dfo db init
./dfo azure discover vms
./dfo azure analyze idle-vms
```

---

### Problem: Invalid option

**Symptoms:**
```
Error: No such option: --invalid-option
```

**Solutions:**

```bash
# Check available options
./dfo azure analyze idle-vms --help

# Common mistakes:
# Wrong: --cpu-threshold=5.0
# Right: --cpu-threshold 5.0  (space, not =)
```

---

### Problem: Missing required argument

**Symptoms:**
```
Error: Missing argument 'VM_NAME'
```

**Solutions:**

```bash
# Check command signature
./dfo azure show --help

# Provide required argument
./dfo azure show my-vm-name
```

---

## Discovery Issues

### Problem: No VMs found

**Symptoms:**
```
Discovered 0 VMs
```

**Solutions:**

**1. Check subscription:**
```bash
# Verify you're targeting the right subscription
az account show

# List VMs manually
az vm list --output table
```

**2. Check permissions:**
```bash
# Verify read permissions
az vm list --subscription <subscription-id>
```

**3. Check filters (if any):**
```bash
# Discovery should find all VMs by default
# Check for any custom filtering in code
```

---

### Problem: CPU metrics missing

**Symptoms:**
```
Warning: VM 'vm-name' has no CPU metrics
```

**Solutions:**

**1. Enable VM diagnostics:**
```bash
# VM needs Azure Monitor diagnostics enabled
# Check VM in Azure Portal > Diagnostics settings
```

**2. Wait for metrics:**
```bash
# Metrics may take 5-15 minutes to appear
# For new VMs, wait before discovery
```

**3. Check time range:**
```bash
# DFO looks back 14 days by default
# Ensure VM has been running for at least 1 day
```

**4. Verify Monitor permissions:**
```bash
# Needs "Monitoring Reader" role
az role assignment create \
  --assignee <client-id> \
  --role "Monitoring Reader" \
  --scope "/subscriptions/<subscription-id>"
```

---

### Problem: Discovery takes too long

**Symptoms:**
- Discovery hangs or takes > 5 minutes for < 100 VMs

**Solutions:**

**1. Check API throttling:**
```bash
# Azure may throttle requests
# Look for "429 Too Many Requests" in debug logs

export AZURE_LOG_LEVEL=DEBUG
./dfo azure discover vms
```

**2. Reduce parallelism (future feature):**
```bash
# Currently sequential - parallel discovery coming soon
```

---

## Analysis Problems

### Problem: No idle VMs detected

**Symptoms:**
```
Idle VMs analysis: 0 findings
```

**Solutions:**

**1. Check threshold:**
```bash
# Default threshold is 5% - might be too strict
./dfo azure analyze idle-vms --cpu-threshold 10.0

# Or update .env
DFO_IDLE_CPU_THRESHOLD=10.0
```

**2. Check idle days:**
```bash
# Default is 14 days - VMs might not have been idle that long
./dfo azure analyze idle-vms --idle-days 7
```

**3. Verify VM data:**
```bash
# Check VMs were discovered
./dfo azure list

# Check CPU metrics exist
./dfo azure show <vm-name>
```

---

### Problem: Analysis crashes

**Symptoms:**
```
RuntimeError: Analysis failed
```

**Solutions:**

**1. Check database:**
```bash
# Ensure database has data
./dfo db info

# Re-discover if needed
./dfo azure discover vms
```

**2. Check for data corruption:**
```bash
# Try refreshing database
./dfo db refresh --yes
./dfo azure discover vms
./dfo azure analyze idle-vms
```

**3. Enable debug logging:**
```python
# Add to code temporarily
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

### Problem: Pricing data incorrect

**Symptoms:**
- Monthly savings estimates seem wrong
- $0.00 costs for all VMs

**Solutions:**

**1. Check Azure region:**
```bash
# Pricing varies by region
# Ensure VMs are in supported regions (eastus, westus, etc.)
```

**2. Verify VM size:**
```bash
# VM size must match Azure pricing API
# Check: https://azure.microsoft.com/en-us/pricing/details/virtual-machines/
```

**3. Re-fetch pricing:**
```bash
# Pricing is cached - may need to re-discover
./dfo azure discover vms
```

---

## Execution Failures

### Problem: Plan validation fails

**Symptoms:**
```
ValidationError: VM 'vm-name' not found in Azure
```

**Solutions:**

**1. VM was deleted:**
```bash
# VM existed during analysis but was deleted
# Remove from plan or re-analyze
./dfo azure analyze idle-vms  # Get fresh analysis
./dfo azure plan create --from-analysis idle-vms-<date>
```

**2. Stale plan:**
```bash
# Plan is old - re-validate or create new plan
./dfo azure plan validate <plan-id>

# If validation fails, create new plan
./dfo azure plan create --from-analysis <latest-analysis>
```

---

### Problem: Plan approval fails

**Symptoms:**
```
ApprovalError: Plan validation is stale
```

**Solutions:**

```bash
# Re-validate plan before approving
./dfo azure plan validate <plan-id>
./dfo azure plan approve <plan-id>
```

---

### Problem: Execution fails

**Symptoms:**
```
ExecutionError: Failed to stop VM 'vm-name'
```

**Solutions:**

**1. Check permissions:**
```bash
# Needs "Contributor" or "Virtual Machine Contributor" role
az role assignment create \
  --assignee <client-id> \
  --role "Virtual Machine Contributor" \
  --scope "/subscriptions/<subscription-id>"
```

**2. Check VM state:**
```bash
# VM might already be stopped/deallocated
az vm show -g <rg> -n <vm-name> --query "powerState"
```

**3. Retry:**
```bash
# Check execution status
./dfo azure plan status <plan-id> --verbose

# Retry execution (only retries failed actions)
./dfo azure plan execute <plan-id> --force
```

---

### Problem: Dry-run doesn't work

**Symptoms:**
- Dry-run mode is making real changes

**Solutions:**

```bash
# Dry-run is DEFAULT - should be safe
./dfo azure plan execute <plan-id>  # Dry-run (no changes)

# Verify you're NOT using --force
# NEVER use --force unless you intend to make real changes
./dfo azure plan execute <plan-id> --force  # LIVE execution
```

---

### Problem: Rollback fails

**Symptoms:**
```
RollbackError: Cannot rollback non-reversible action
```

**Solutions:**

**1. Check action type:**
```bash
# Only these actions are reversible:
# - stop → start
# - deallocate → start
# - downsize → upsize (resize back)

# NOT reversible:
# - delete

# Check plan details
./dfo azure plan show <plan-id> --detail
```

**2. Manual rollback:**
```bash
# If rollback command fails, manually start VM
az vm start -g <resource-group> -n <vm-name>
```

---

## Test Failures

### Problem: Tests fail with database errors

**Symptoms:**
```
fixture 'test_db' not found
```

**Solutions:**

```bash
# Ensure conftest.py exists
ls src/dfo/tests/conftest.py

# Check fixture definition
grep "def test_db" src/dfo/tests/conftest.py

# If missing, reinstall
pip install -e .
```

---

### Problem: Pydantic validation errors in tests

**Symptoms:**
```
ValidationError: 1 validation error for VMInventory
```

**Solutions:**

```python
# ❌ Don't use Mock for Pydantic models
vm = Mock(spec=VMInventory)

# ✅ Use real instances
vm = VMInventory(
    id="vm1",
    name="test-vm",
    # ... all required fields
)
```

---

### Problem: Import errors in tests

**Symptoms:**
```
ModuleNotFoundError: No module named 'dfo'
```

**Solutions:**

```bash
# Install in editable mode
pip install -e .

# Verify
python -c "import dfo; print(dfo.__file__)"
```

---

## Performance Issues

### Problem: Slow discovery

**Symptoms:**
- Discovery takes > 1 minute per VM

**Solutions:**

**1. Check network:**
```bash
# Slow Azure API responses
# Check network latency to Azure
ping eastus.management.azure.com
```

**2. Reduce metric timeframe (future):**
```bash
# Currently fetches 14 days of metrics
# Future: Add --days option
./dfo azure discover vms --days 7
```

---

### Problem: Large database file

**Symptoms:**
- dfo.duckdb is > 1GB

**Solutions:**

```bash
# Check size
du -h dfo.duckdb

# Vacuum database
./dfo db refresh --yes  # WARNING: Deletes data

# Alternatively, export and re-import
./dfo azure report --format json --output backup.json
./dfo db refresh --yes
# (Re-discover VMs)
```

---

### Problem: Report generation is slow

**Symptoms:**
- `dfo azure report` takes > 30 seconds

**Solutions:**

```bash
# Use filters to reduce data
./dfo azure report --severity high --limit 50

# Check database size
./dfo db info
```

---

## Getting Help

### Diagnostic Information

**When reporting issues, include:**

```bash
# 1. dfo version
./dfo version

# 2. Environment
python --version
pip list | grep dfo

# 3. Configuration (sanitized)
./dfo config  # Secrets are masked

# 4. Database info
./dfo db info

# 5. Error message (full stack trace)
./dfo azure discover vms 2>&1 | tee error.log

# 6. OS and platform
uname -a  # Linux/macOS
```

### Debugging Steps

**1. Enable verbose logging:**
```bash
export DFO_LOG_LEVEL=DEBUG
export AZURE_LOG_LEVEL=DEBUG
./dfo azure discover vms
```

**2. Run in debug mode (Python):**
```python
# Add to code
import logging
logging.basicConfig(level=logging.DEBUG)
```

**3. Check for known issues:**
- GitHub Issues: https://github.com/vedanta/dfo/issues
- Search for similar problems

### Reporting Bugs

**Create an issue on GitHub with:**
1. Clear title (e.g., "Discovery fails with AuthenticationError")
2. Steps to reproduce
3. Expected vs. actual behavior
4. Diagnostic information (see above)
5. Logs/screenshots

**Issue template:** See [CONTRIBUTING.md](/docs/CONTRIBUTING.md#reporting-bugs)

---

## Common Error Messages

| Error Message | Likely Cause | Solution |
|---------------|--------------|----------|
| `FileNotFoundError: Database not found` | Database not initialized | `./dfo db init` |
| `ValidationError: CPU threshold must be...` | Invalid config value | Check `.env` file, range 0-100 |
| `DefaultAzureCredential failed` | Not authenticated | `az login` or set service principal env vars |
| `AuthorizationFailed: client does not have authorization` | Missing permissions | Grant Reader + Monitoring Reader roles |
| `fixture 'test_db' not found` | Missing conftest.py | Check `src/dfo/tests/conftest.py` exists |
| `ModuleNotFoundError: No module named 'dfo'` | Not installed | `pip install -e .` |
| `duckdb.IOException: Could not acquire lock` | Database locked | Kill other processes using DB |
| `SubscriptionNotFound` | Wrong subscription ID | `az account set --subscription <id>` |
| `RuntimeError: Column not found` | Schema mismatch | `./dfo db refresh --yes` (WARNING: deletes data) |

---

## Still Stuck?

1. **Check documentation:**
   - [README.md](/README.md) - Quick start
   - [ARCHITECTURE.md](/docs/ARCHITECTURE.md) - System design
   - [DEVELOPER_ONBOARDING.md](/docs/DEVELOPER_ONBOARDING.md) - Developer setup

2. **Search GitHub Issues:**
   - https://github.com/vedanta/dfo/issues

3. **Ask for help:**
   - Open a new issue with `question` label
   - Provide diagnostic information

4. **Community support (future):**
   - GitHub Discussions
   - Slack channel

---

**Last Updated:** 2025-01-26
**Maintained By:** DFO Development Team
