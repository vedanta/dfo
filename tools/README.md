# DFO Helper Tools

This directory contains helper tools and scripts for setting up and managing cloud resources needed by dfo.

## Quick Start

### Create Azure Service Principal

```bash
cd tools/azure
./setup-service-principal.sh
```

This will:
- Create a service principal with correct permissions
- Generate a `.env` file with credentials
- Validate the setup works

Then start using dfo:
```bash
./dfo db init
./dfo azure discover vms
```

---

## Available Tools

### Azure Setup Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `setup-service-principal.sh` | Create service principal with permissions | `./setup-service-principal.sh` |
| `validate-permissions.sh` | Verify service principal permissions | `./validate-permissions.sh` |
| `delete-service-principal.sh` | Remove service principal | `./delete-service-principal.sh --name dfo-sp-YYYY-MM-DD` |
| `list-service-principals.sh` | List all dfo service principals | `./list-service-principals.sh` |

---

## Prerequisites

Before using these scripts:

1. **Azure CLI** must be installed
   ```bash
   # Check if installed
   az --version

   # Install if needed
   # https://docs.microsoft.com/cli/azure/install-azure-cli
   ```

2. **Login to Azure**
   ```bash
   az login
   ```

3. **Set your subscription** (if you have multiple)
   ```bash
   az account set --subscription "Your Subscription Name"
   ```

4. **Required permissions:** You need Owner or User Access Administrator role on the subscription to create service principals and assign roles.

---

## Common Workflows

### First Time Setup

```bash
# 1. Create service principal
cd tools/azure
./setup-service-principal.sh

# 2. Review generated .env file
cat ../../.env

# 3. Validate permissions
./validate-permissions.sh

# 4. Start using dfo
cd ../..
./dfo db init
./dfo azure discover vms
```

### Multiple Subscriptions

```bash
# Setup for production subscription
./setup-service-principal.sh --subscription "Production" --env-file .env.prod

# Setup for development subscription
./setup-service-principal.sh --subscription "Development" --env-file .env.dev
```

### Validate Existing Setup

```bash
# Check if your service principal has correct permissions
./validate-permissions.sh

# Or check specific .env file
./validate-permissions.sh --env-file .env.prod
```

### List All Service Principals

```bash
# See all dfo service principals
./list-service-principals.sh

# Get JSON output
./list-service-principals.sh --format json
```

### Cleanup

```bash
# List existing service principals
./list-service-principals.sh

# Delete specific service principal
./delete-service-principal.sh --name dfo-sp-2025-01-26

# Or delete using app ID from .env
./delete-service-principal.sh --env-file ../../.env
```

---

## Script Details

### setup-service-principal.sh

**Purpose:** Create Azure service principal with correct permissions for dfo.

**Options:**
```bash
./setup-service-principal.sh [OPTIONS]

Options:
  --name NAME                  Service principal name (default: dfo-sp-YYYY-MM-DD)
  --subscription SUBSCRIPTION  Azure subscription ID or name (default: current)
  --env-file FILE             Output .env file path (default: ../../.env)
  --no-env                    Skip .env file creation
  --json                      Output credentials as JSON
  --dry-run                   Show what would be created without creating
  --help                      Show this help message
```

**What it creates:**
- Service principal with auto-generated name
- Role assignment: Reader (for VM discovery)
- Role assignment: Monitoring Reader (for CPU metrics)
- Client secret (valid for 90 days)
- .env file with all credentials

**Example:**
```bash
./setup-service-principal.sh --name dfo-sp-prod

# Output:
# ✓ Service Principal Created Successfully!
#
# Credentials:
#   Service Principal Name: dfo-sp-prod
#   Application ID:         12345678-1234-1234-1234-123456789abc
#   ...
#
# .env file created: ../../.env
```

### validate-permissions.sh

**Purpose:** Verify service principal has all required permissions.

**Options:**
```bash
./validate-permissions.sh [OPTIONS]

Options:
  --app-id APP_ID            Application/Client ID (from .env or arg)
  --subscription SUBSCRIPTION Subscription to check (default: current)
  --env-file FILE            Read credentials from .env file (default: ../../.env)
  --help                     Show this help message
```

**What it checks:**
- ✓ Credentials are present
- ✓ Service principal can authenticate
- ✓ Reader role is assigned
- ✓ Monitoring Reader role is assigned
- ✓ Can list VMs via API
- ✓ Can read metrics via API
- ✓ Credential expiration date

**Example:**
```bash
./validate-permissions.sh

# Output:
# Validating Service Principal Permissions...
#
# ✓ AZURE_TENANT_ID found
# ✓ Service principal can authenticate
# ✓ Reader role assigned
# ✓ Can list VMs (found 10 VMs)
# ✓ All permissions valid!
```

### delete-service-principal.sh

**Purpose:** Safely remove service principal and role assignments.

**Options:**
```bash
./delete-service-principal.sh [OPTIONS]

Options:
  --app-id APP_ID            Application/Client ID to delete
  --name NAME                Service principal name to delete
  --env-file FILE            Read APP_ID from .env file (default: ../../.env)
  --yes                      Skip confirmation prompt
  --help                     Show this help message
```

**Safety features:**
- Shows what will be deleted before proceeding
- Requires confirmation (unless --yes flag used)
- Removes role assignments first
- Then removes service principal

**Example:**
```bash
./delete-service-principal.sh --name dfo-sp-2025-01-26

# Output:
# Service Principal to Delete:
#   Name:              dfo-sp-2025-01-26
#   Application ID:    12345678-...
#
# ⚠ This action cannot be undone!
# Delete service principal? [y/N]:
```

### list-service-principals.sh

**Purpose:** List all dfo-related service principals.

**Options:**
```bash
./list-service-principals.sh [OPTIONS]

Options:
  --all                      List all service principals (not just dfo-*)
  --subscription SUBSCRIPTION Subscription to check (default: current)
  --format FORMAT            Output format: table|json (default: table)
  --help                     Show this help message
```

**Example:**
```bash
./list-service-principals.sh

# Output:
# DFO Service Principals:
#
# Name                 App ID                               Created      Expires      Status
# dfo-sp-2025-01-26   12345678-...                         2025-01-26  2025-04-26   ✓ Active
# dfo-sp-prod         87654321-...                         2025-01-20  2025-04-20   ✓ Active
#
# Total: 2 service principals
```

---

## Security Best Practices

### Credentials

- ✅ **Never commit .env to git** - Already in `.gitignore`
- ✅ **Store secrets securely** - Use Azure Key Vault for production
- ✅ **Rotate regularly** - Scripts create 90-day secrets
- ✅ **One service principal per environment** - Don't share across prod/dev

### Permissions

- ✅ **Least privilege** - Scripts only assign Reader + Monitoring Reader
- ✅ **Subscription scope** - Access limited to one subscription
- ✅ **Regular audits** - Use list and validate scripts to check permissions

### Monitoring

```bash
# Check expiration dates regularly
./list-service-principals.sh

# Validate permissions still work
./validate-permissions.sh
```

---

## Troubleshooting

### "Azure CLI not found"

Install Azure CLI:
- **macOS:** `brew install azure-cli`
- **Linux:** See https://docs.microsoft.com/cli/azure/install-azure-cli-linux
- **Windows:** Download from https://aka.ms/installazurecliwindows

### "Not logged in to Azure"

```bash
az login
```

### "Insufficient permissions to create service principal"

You need one of these roles on the subscription:
- Owner
- User Access Administrator

Check your roles:
```bash
az role assignment list --assignee $(az account show --query user.name -o tsv)
```

### "Service principal already exists"

Either:
1. Delete the existing one: `./delete-service-principal.sh --name dfo-sp-YYYY-MM-DD`
2. Use a different name: `./setup-service-principal.sh --name dfo-sp-custom`

### "Cannot read metrics" in validation

Ensure Monitoring Reader role is assigned:
```bash
az role assignment create \
  --assignee YOUR_APP_ID \
  --role "Monitoring Reader" \
  --subscription YOUR_SUBSCRIPTION_ID
```

---

## Examples

### Create Service Principal for Specific Subscription

```bash
./setup-service-principal.sh \
  --name dfo-sp-production \
  --subscription "Production Subscription" \
  --env-file ../../.env.production
```

### JSON Output for Automation

```bash
./setup-service-principal.sh --json > credentials.json
```

### Dry Run (Preview Without Creating)

```bash
./setup-service-principal.sh --dry-run
```

### Validate Multiple Environments

```bash
./validate-permissions.sh --env-file ../../.env.prod
./validate-permissions.sh --env-file ../../.env.dev
```

---

## Related Documentation

- [QUICKSTART.md](../QUICKSTART.md) - Getting started with dfo
- [TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md) - Common issues
- [Azure Service Principals](https://docs.microsoft.com/azure/active-directory/develop/app-objects-and-service-principals)
- [Azure RBAC Roles](https://docs.microsoft.com/azure/role-based-access-control/built-in-roles)

---

## Support

If you encounter issues:

1. Check [TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md)
2. Run validation: `./validate-permissions.sh`
3. Open an issue: https://github.com/vedanta/dfo/issues

---

**Last Updated:** 2025-01-26
