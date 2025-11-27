# Feature Design: Azure Helper Scripts

> **Feature:** Helper scripts for Azure service principal creation and management
> **Created:** 2025-01-26
> **Status:** Design Phase

---

## Problem Statement

Users need to create Azure service principals with correct permissions to run dfo, but this involves multiple manual steps:
1. Creating a service principal
2. Assigning Reader role (for VM discovery)
3. Assigning Monitoring Reader role (for metrics)
4. Extracting credentials (tenant ID, client ID, secret, subscription ID)
5. Configuring dfo with these credentials

**Goal:** Provide simple, automated scripts that handle Azure setup with one command.

---

## User Stories

### Story 1: First-Time Setup
> As a new dfo user, I want to quickly create a service principal with correct permissions, so I can start using dfo without reading Azure documentation.

**Acceptance Criteria:**
- Single command creates service principal with all required permissions
- Outputs credentials in .env format ready to use
- Validates that setup was successful
- Provides clear error messages if anything fails

### Story 2: Multiple Subscriptions
> As a user with multiple Azure subscriptions, I want to create service principals for each subscription, so I can analyze VMs across all my subscriptions.

**Acceptance Criteria:**
- Script accepts subscription ID as parameter
- Can run multiple times for different subscriptions
- Clearly labels which subscription each service principal is for

### Story 3: Permission Validation
> As a user, I want to verify my service principal has correct permissions, so I can troubleshoot authentication issues.

**Acceptance Criteria:**
- Validation script checks all required permissions
- Reports which permissions are missing
- Suggests commands to fix permission issues

### Story 4: Cleanup
> As a user, I want to easily remove service principals when I'm done testing, so I don't leave unused credentials around.

**Acceptance Criteria:**
- Delete script safely removes service principal
- Lists what will be deleted before confirmation
- Handles cases where service principal is already deleted

---

## Design Decisions

### Language Choice

**Recommended: Bash scripts with Azure CLI**

**Pros:**
- ✅ No additional dependencies (az CLI already required for dfo)
- ✅ Cross-platform (works on Linux, macOS, WSL, Git Bash)
- ✅ Simple to understand and modify
- ✅ Direct Azure CLI commands are well-documented
- ✅ Easy to debug (users can run commands individually)

**Also Provide: PowerShell scripts**

**Pros:**
- ✅ Native Windows experience
- ✅ Azure PowerShell module widely used in enterprise
- ✅ Better error handling and object manipulation

**Decision:** Provide both bash and PowerShell versions for maximum compatibility.

---

## Directory Structure

```
scripts/
├── README.md                           # Overview and usage guide
├── azure/                              # Azure-specific scripts
│   ├── setup-service-principal.sh     # Main setup script (bash)
│   ├── setup-service-principal.ps1    # Main setup script (PowerShell)
│   ├── validate-permissions.sh        # Validate service principal
│   ├── validate-permissions.ps1       # Validate service principal (PS)
│   ├── delete-service-principal.sh    # Cleanup script
│   ├── delete-service-principal.ps1   # Cleanup script (PS)
│   ├── list-service-principals.sh     # List dfo service principals
│   └── list-service-principals.ps1    # List dfo service principals (PS)
└── examples/
    ├── .env.example                   # Example .env file
    └── multi-subscription-setup.sh    # Example: multiple subscriptions
```

---

## Script Specifications

### 1. Setup Service Principal (`setup-service-principal.sh`)

**Purpose:** Create Azure service principal with correct permissions for dfo.

**Usage:**
```bash
./scripts/azure/setup-service-principal.sh [OPTIONS]

Options:
  --name NAME                  Service principal name (default: dfo-sp-YYYY-MM-DD)
  --subscription SUBSCRIPTION  Azure subscription ID or name (default: current)
  --scope SCOPE               Role assignment scope (default: subscription)
  --env-file FILE             Output .env file path (default: .env)
  --no-env                    Skip .env file creation
  --json                      Output credentials as JSON
  --dry-run                   Show what would be created without creating
  --help                      Show this help message
```

**Features:**
- ✅ Creates service principal with auto-generated name (e.g., `dfo-sp-2025-01-26`)
- ✅ Assigns Reader role (for VM discovery)
- ✅ Assigns Monitoring Reader role (for CPU metrics)
- ✅ Generates strong client secret (valid for 1 year by default)
- ✅ Outputs credentials in multiple formats (.env, JSON, plain text)
- ✅ Validates prerequisites (az CLI installed, logged in)
- ✅ Tests service principal immediately after creation
- ✅ Provides clear success/failure messages

**Output Formats:**

**Plain Text (default):**
```
✓ Service Principal Created Successfully!

Credentials:
  Service Principal Name: dfo-sp-2025-01-26
  Application ID:         12345678-1234-1234-1234-123456789abc
  Tenant ID:             87654321-4321-4321-4321-abcdef123456
  Client Secret:         ****** (shown once - save it now!)
  Subscription ID:       abcdef12-3456-7890-abcd-ef1234567890

.env file created: .env

Next steps:
  1. Review .env file and ensure it's in .gitignore
  2. Run: ./dfo db init
  3. Run: ./dfo azure discover vms
```

**.env Format:**
```bash
# Azure Service Principal for dfo
# Created: 2025-01-26
# Service Principal: dfo-sp-2025-01-26

AZURE_TENANT_ID=87654321-4321-4321-4321-abcdef123456
AZURE_CLIENT_ID=12345678-1234-1234-1234-123456789abc
AZURE_CLIENT_SECRET=super-secret-value-here
AZURE_SUBSCRIPTION_ID=abcdef12-3456-7890-abcd-ef1234567890

# Optional: Analysis thresholds
# DFO_IDLE_CPU_THRESHOLD=5.0
# DFO_IDLE_DAYS=14
```

**JSON Format:**
```json
{
  "servicePrincipalName": "dfo-sp-2025-01-26",
  "appId": "12345678-1234-1234-1234-123456789abc",
  "tenantId": "87654321-4321-4321-4321-abcdef123456",
  "clientSecret": "super-secret-value-here",
  "subscriptionId": "abcdef12-3456-7890-abcd-ef1234567890",
  "createdAt": "2025-01-26T10:30:00Z",
  "expiresAt": "2026-01-26T10:30:00Z"
}
```

**Error Handling:**
- Check if az CLI is installed
- Check if user is logged in (`az account show`)
- Check if subscription exists
- Check if service principal name already exists
- Check if role assignments succeeded
- Provide actionable error messages

**Example Errors:**
```
✗ Azure CLI not found
  Install: https://docs.microsoft.com/cli/azure/install-azure-cli

✗ Not logged in to Azure
  Run: az login

✗ Service principal 'dfo-sp-2025-01-26' already exists
  Choose different name with --name flag
  Or delete existing: ./scripts/azure/delete-service-principal.sh dfo-sp-2025-01-26
```

---

### 2. Validate Permissions (`validate-permissions.sh`)

**Purpose:** Verify service principal has all required permissions.

**Usage:**
```bash
./scripts/azure/validate-permissions.sh [OPTIONS]

Options:
  --app-id APP_ID            Application/Client ID (from .env or arg)
  --subscription SUBSCRIPTION Subscription to check (default: current)
  --env-file FILE            Read credentials from .env file (default: .env)
  --help                     Show this help message
```

**Features:**
- ✅ Checks Reader role assignment
- ✅ Checks Monitoring Reader role assignment
- ✅ Tests actual API access (list VMs, get metrics)
- ✅ Reports missing permissions with fix commands
- ✅ Validates credential expiration

**Output:**
```
Validating Service Principal Permissions...

Credentials:
  ✓ AZURE_TENANT_ID found
  ✓ AZURE_CLIENT_ID found
  ✓ AZURE_CLIENT_SECRET found
  ✓ AZURE_SUBSCRIPTION_ID found

Authentication:
  ✓ Service principal can authenticate

Role Assignments:
  ✓ Reader role assigned (subscription scope)
  ✓ Monitoring Reader role assigned (subscription scope)

API Access Tests:
  ✓ Can list VMs (found 10 VMs)
  ✓ Can read metrics (tested on vm-1)

Credential Expiration:
  ✓ Valid until: 2026-01-26 (365 days remaining)

✓ All permissions valid! dfo is ready to use.
```

**Failure Example:**
```
Validating Service Principal Permissions...

✗ Missing Role Assignment: Monitoring Reader
  Fix: az role assignment create \
    --assignee 12345678-1234-1234-1234-123456789abc \
    --role "Monitoring Reader" \
    --subscription abcdef12-3456-7890-abcd-ef1234567890

✗ Cannot read metrics
  Ensure Monitoring Reader role is assigned

⚠ Credential expires in 7 days
  Consider rotating: az ad sp credential reset --id 12345678-1234-1234-1234-123456789abc
```

---

### 3. Delete Service Principal (`delete-service-principal.sh`)

**Purpose:** Safely remove service principal and role assignments.

**Usage:**
```bash
./scripts/azure/delete-service-principal.sh [OPTIONS]

Options:
  --app-id APP_ID            Application/Client ID to delete
  --name NAME                Service principal name to delete
  --env-file FILE            Read APP_ID from .env file (default: .env)
  --yes                      Skip confirmation prompt
  --help                     Show this help message
```

**Features:**
- ✅ Lists what will be deleted before confirmation
- ✅ Removes role assignments first
- ✅ Removes service principal
- ✅ Optionally removes .env file
- ✅ Dry-run mode to preview

**Output:**
```
Service Principal to Delete:
  Name:              dfo-sp-2025-01-26
  Application ID:    12345678-1234-1234-1234-123456789abc
  Created:           2025-01-26

Role Assignments to Remove:
  - Reader (subscription scope)
  - Monitoring Reader (subscription scope)

⚠ This action cannot be undone!

Delete service principal? [y/N]: y

✓ Removed role assignment: Reader
✓ Removed role assignment: Monitoring Reader
✓ Deleted service principal: dfo-sp-2025-01-26

Next steps:
  - Delete or update .env file if it contains these credentials
  - Create new service principal: ./scripts/azure/setup-service-principal.sh
```

---

### 4. List Service Principals (`list-service-principals.sh`)

**Purpose:** List all dfo-related service principals.

**Usage:**
```bash
./scripts/azure/list-service-principals.sh [OPTIONS]

Options:
  --all                      List all service principals (not just dfo-*)
  --subscription SUBSCRIPTION Subscription to check (default: current)
  --format FORMAT            Output format: table|json (default: table)
  --help                     Show this help message
```

**Output:**
```
DFO Service Principals:

Name                 App ID                               Created      Expires      Status
dfo-sp-2025-01-26   12345678-1234-1234-1234-123456789abc 2025-01-26  2026-01-26   ✓ Active
dfo-sp-2024-12-15   87654321-4321-4321-4321-abcdef123456 2024-12-15  2025-12-15   ⚠ Expires soon
dfo-sp-test         abcdef12-3456-7890-abcd-ef1234567890 2025-01-20  2026-01-20   ✓ Active

Total: 3 service principals
```

---

## Script Implementation Details

### Bash Script Template

```bash
#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}✓${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1" >&2
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI not found"
        echo "Install: https://docs.microsoft.com/cli/azure/install-azure-cli"
        exit 1
    fi

    if ! az account show &> /dev/null; then
        log_error "Not logged in to Azure"
        echo "Run: az login"
        exit 1
    fi

    log_info "Prerequisites checked"
}

# Main logic
main() {
    check_prerequisites
    # ... rest of script
}

main "$@"
```

### PowerShell Script Template

```powershell
#Requires -Version 5.1
#Requires -Modules Az.Accounts, Az.Resources

[CmdletBinding()]
param(
    [Parameter()]
    [string]$Name,

    [Parameter()]
    [string]$Subscription,

    [Parameter()]
    [string]$EnvFile = ".env"
)

# Error handling
$ErrorActionPreference = "Stop"

# Logging functions
function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Failure {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

# Check prerequisites
function Test-Prerequisites {
    if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
        Write-Failure "Azure CLI not found"
        Write-Host "Install: https://docs.microsoft.com/cli/azure/install-azure-cli"
        exit 1
    }

    try {
        az account show | Out-Null
    } catch {
        Write-Failure "Not logged in to Azure"
        Write-Host "Run: az login"
        exit 1
    }

    Write-Success "Prerequisites checked"
}

# Main logic
Test-Prerequisites
# ... rest of script
```

---

## Security Considerations

### Credential Handling
- ✅ **Never log secrets:** Client secrets should only be shown once
- ✅ **Secure storage:** Remind users to add .env to .gitignore
- ✅ **Expiration:** Default to 1-year secret expiration, allow customization
- ✅ **Rotation:** Provide script to rotate secrets

### Permissions
- ✅ **Least privilege:** Only assign Reader and Monitoring Reader
- ✅ **Scope:** Default to subscription scope, allow resource group scope
- ✅ **Audit:** Log all service principal creation and deletion

### Validation
- ✅ **Input validation:** Sanitize all user inputs
- ✅ **Prerequisites:** Check az CLI version, login status
- ✅ **Confirmation:** Require confirmation for destructive operations

---

## Documentation Requirements

### scripts/README.md

```markdown
# DFO Helper Scripts

This directory contains helper scripts for setting up and managing Azure resources needed by dfo.

## Quick Start

### Create Service Principal (Bash)
```bash
./azure/setup-service-principal.sh
```

### Create Service Principal (PowerShell)
```powershell
./azure/setup-service-principal.ps1
```

## Available Scripts

| Script | Purpose | Bash | PowerShell |
|--------|---------|------|------------|
| Setup Service Principal | Create SP with permissions | ✓ | ✓ |
| Validate Permissions | Check SP permissions | ✓ | ✓ |
| Delete Service Principal | Remove SP | ✓ | ✓ |
| List Service Principals | Show all dfo SPs | ✓ | ✓ |

## Prerequisites

- Azure CLI installed and logged in
- Appropriate permissions to create service principals
- Owner or User Access Administrator role on subscription

## Common Workflows

### First Time Setup
1. Run setup script: `./azure/setup-service-principal.sh`
2. Script creates .env file with credentials
3. Validate: `./azure/validate-permissions.sh`
4. Start using dfo: `./dfo azure discover vms`

### Multiple Subscriptions
```bash
./azure/setup-service-principal.sh --subscription "Production"
./azure/setup-service-principal.sh --subscription "Development"
```

### Cleanup
```bash
./azure/list-service-principals.sh
./azure/delete-service-principal.sh --name dfo-sp-2025-01-26
```

## Troubleshooting

See [TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md) for common issues.
```

---

## Implementation Plan

### Phase 1: Core Scripts (Bash) - 4 hours
- [ ] Create `scripts/azure/` directory
- [ ] Implement `setup-service-principal.sh`
  - Prerequisites check
  - Service principal creation
  - Role assignments
  - .env file generation
  - Success message
- [ ] Implement `validate-permissions.sh`
  - Credential validation
  - Role assignment checks
  - API access tests
- [ ] Implement `delete-service-principal.sh`
  - Confirmation prompt
  - Role assignment removal
  - Service principal deletion
- [ ] Implement `list-service-principals.sh`
  - List dfo service principals
  - Table format output

### Phase 2: PowerShell Versions - 2 hours
- [ ] Port scripts to PowerShell
- [ ] Test on Windows
- [ ] Ensure feature parity

### Phase 3: Documentation - 1 hour
- [ ] Create `scripts/README.md`
- [ ] Update main `README.md` with scripts section
- [ ] Update `QUICKSTART.md` to reference scripts
- [ ] Add to `TROUBLESHOOTING.md`

### Phase 4: Testing - 1 hour
- [ ] Test on Linux
- [ ] Test on macOS
- [ ] Test on Windows (PowerShell)
- [ ] Test on Windows (Git Bash)
- [ ] Test error scenarios

**Total Effort:** ~8 hours

---

## Success Criteria

### Must Have
- ✅ Bash script creates service principal with correct permissions
- ✅ Script generates .env file ready to use
- ✅ Validation script confirms permissions
- ✅ Delete script safely removes service principal
- ✅ Clear error messages for common issues

### Should Have
- ✅ PowerShell versions for Windows users
- ✅ JSON output format option
- ✅ Dry-run mode
- ✅ List command to show existing service principals

### Nice to Have
- 🔮 Multi-subscription batch setup
- 🔮 Secret rotation helper
- 🔮 Permission escalation detection
- 🔮 Terraform module as alternative

---

## Future Enhancements

### v2.0 - Multi-Cloud Support
- AWS IAM role/user creation scripts
- GCP service account creation scripts
- Cross-cloud permission validation

### v2.0 - Advanced Features
- Secret rotation automation
- Service principal health monitoring
- Permission drift detection
- Compliance reporting

---

## Questions for Review

1. **Script Language:** Bash + PowerShell coverage acceptable?
2. **Naming Convention:** `dfo-sp-YYYY-MM-DD` or allow custom naming?
3. **Secret Expiration:** 1 year default, or make it configurable?
4. **Scope:** Subscription-level only, or support resource group scope?
5. **Directory:** `scripts/` or `tools/` for the top-level?

---

## Related Documentation

- [Azure Service Principal Documentation](https://docs.microsoft.com/azure/active-directory/develop/app-objects-and-service-principals)
- [Azure RBAC Roles](https://docs.microsoft.com/azure/role-based-access-control/built-in-roles)
- [QUICKSTART.md](../QUICKSTART.md) - References these scripts
- [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) - Authentication section

---

**Status:** Ready for Review
**Next Step:** Get feedback on design, then implement Phase 1
