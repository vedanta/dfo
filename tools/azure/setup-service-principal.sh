#!/bin/bash
#
# setup-service-principal.sh
# Create Azure service principal with permissions for dfo
#
# Usage: ./setup-service-principal.sh [OPTIONS]
#

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
DEFAULT_NAME="dfo-sp-$(date +%Y-%m-%d)"
DEFAULT_ENV_FILE="../../.env"
SECRET_EXPIRATION_DAYS=90
DRY_RUN=false
SKIP_ENV=false
OUTPUT_JSON=false

# Configuration
SP_NAME=""
SUBSCRIPTION=""
ENV_FILE="$DEFAULT_ENV_FILE"

#==================================================================================
# Logging functions
#==================================================================================

log_info() {
    echo -e "${GREEN}✓${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1" >&2
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_step() {
    echo -e "${BLUE}→${NC} $1"
}

#==================================================================================
# Help message
#==================================================================================

show_help() {
    cat << EOF
Create Azure service principal with permissions for dfo

Usage: ./setup-service-principal.sh [OPTIONS]

Options:
  --name NAME                  Service principal name (default: dfo-sp-YYYY-MM-DD)
  --subscription SUBSCRIPTION  Azure subscription ID or name (default: current)
  --env-file FILE             Output .env file path (default: ../../.env)
  --no-env                    Skip .env file creation
  --json                      Output credentials as JSON
  --dry-run                   Show what would be created without creating
  --help                      Show this help message

Examples:
  # Create with default name
  ./setup-service-principal.sh

  # Create with custom name
  ./setup-service-principal.sh --name dfo-sp-production

  # Create for specific subscription
  ./setup-service-principal.sh --subscription "Production Subscription"

  # Output as JSON
  ./setup-service-principal.sh --json

  # Preview without creating
  ./setup-service-principal.sh --dry-run

Permissions Created:
  - Reader (for VM discovery)
  - Monitoring Reader (for CPU metrics)

Secret Expiration: $SECRET_EXPIRATION_DAYS days

EOF
}

#==================================================================================
# Parse arguments
#==================================================================================

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --name)
                SP_NAME="$2"
                shift 2
                ;;
            --subscription)
                SUBSCRIPTION="$2"
                shift 2
                ;;
            --env-file)
                ENV_FILE="$2"
                shift 2
                ;;
            --no-env)
                SKIP_ENV=true
                shift
                ;;
            --json)
                OUTPUT_JSON=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                echo "Run with --help for usage"
                exit 1
                ;;
        esac
    done

    # Set defaults if not provided
    if [ -z "$SP_NAME" ]; then
        SP_NAME="$DEFAULT_NAME"
    fi
}

#==================================================================================
# Prerequisites check
#==================================================================================

check_prerequisites() {
    log_step "Checking prerequisites..."

    # Check if az CLI is installed
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI not found"
        echo ""
        echo "Install Azure CLI:"
        echo "  macOS:   brew install azure-cli"
        echo "  Linux:   https://docs.microsoft.com/cli/azure/install-azure-cli-linux"
        echo "  Windows: https://aka.ms/installazurecliwindows"
        exit 1
    fi

    # Check if logged in
    if ! az account show &> /dev/null; then
        log_error "Not logged in to Azure"
        echo ""
        echo "Login to Azure:"
        echo "  az login"
        exit 1
    fi

    # Get current subscription if not specified
    if [ -z "$SUBSCRIPTION" ]; then
        SUBSCRIPTION=$(az account show --query id -o tsv)
    fi

    log_info "Prerequisites checked"
}

#==================================================================================
# Validate inputs
#==================================================================================

validate_inputs() {
    log_step "Validating inputs..."

    # Check if subscription exists
    if ! az account show --subscription "$SUBSCRIPTION" &> /dev/null; then
        log_error "Subscription not found: $SUBSCRIPTION"
        echo ""
        echo "List available subscriptions:"
        echo "  az account list --output table"
        exit 1
    fi

    # Check if service principal name already exists
    if az ad sp list --display-name "$SP_NAME" --query '[0].appId' -o tsv 2>/dev/null | grep -q .; then
        log_error "Service principal already exists: $SP_NAME"
        echo ""
        echo "Options:"
        echo "  1. Delete existing: ./delete-service-principal.sh --name $SP_NAME"
        echo "  2. Use different name: --name dfo-sp-custom"
        exit 1
    fi

    log_info "Inputs validated"
}

#==================================================================================
# Dry run preview
#==================================================================================

show_dry_run() {
    cat << EOF

${YELLOW}DRY RUN MODE${NC} - No changes will be made

Would create:
  Service Principal Name: $SP_NAME
  Subscription:          $(az account show --subscription "$SUBSCRIPTION" --query name -o tsv)
  Subscription ID:       $SUBSCRIPTION

Role Assignments:
  - Reader (subscription scope)
  - Monitoring Reader (subscription scope)

Secret:
  - Expiration: $SECRET_EXPIRATION_DAYS days

Output:
  - .env file: $ENV_FILE

To execute, run without --dry-run flag

EOF
}

#==================================================================================
# Create service principal
#==================================================================================

create_service_principal() {
    log_step "Creating service principal..."

    # Set subscription
    az account set --subscription "$SUBSCRIPTION" > /dev/null

    # Calculate expiration date
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS date command
        EXPIRATION_DATE=$(date -v+${SECRET_EXPIRATION_DAYS}d -u +"%Y-%m-%dT%H:%M:%SZ")
    else
        # Linux date command
        EXPIRATION_DATE=$(date -d "+${SECRET_EXPIRATION_DAYS} days" -u +"%Y-%m-%dT%H:%M:%SZ")
    fi

    # Create service principal with role assignment
    # Note: We assign Reader first, then add Monitoring Reader separately
    SP_OUTPUT=$(az ad sp create-for-rbac \
        --name "$SP_NAME" \
        --role "Reader" \
        --scopes "/subscriptions/$SUBSCRIPTION" \
        --years 0 \
        --end-date "$EXPIRATION_DATE" \
        --output json)

    # Extract values
    APP_ID=$(echo "$SP_OUTPUT" | jq -r '.appId')
    CLIENT_SECRET=$(echo "$SP_OUTPUT" | jq -r '.password')
    TENANT_ID=$(echo "$SP_OUTPUT" | jq -r '.tenant')

    if [ -z "$APP_ID" ] || [ "$APP_ID" == "null" ]; then
        log_error "Failed to create service principal"
        exit 1
    fi

    log_info "Service principal created: $SP_NAME"
}

#==================================================================================
# Assign additional roles
#==================================================================================

assign_monitoring_role() {
    log_step "Assigning Monitoring Reader role..."

    # Wait a bit for the service principal to propagate
    sleep 5

    # Assign Monitoring Reader role
    az role assignment create \
        --assignee "$APP_ID" \
        --role "Monitoring Reader" \
        --scope "/subscriptions/$SUBSCRIPTION" \
        --output none

    log_info "Monitoring Reader role assigned"
}

#==================================================================================
# Validate service principal
#==================================================================================

validate_service_principal() {
    log_step "Validating service principal..."

    # Wait for propagation
    sleep 3

    # Check if we can authenticate
    if az login --service-principal \
        --username "$APP_ID" \
        --password "$CLIENT_SECRET" \
        --tenant "$TENANT_ID" \
        --allow-no-subscriptions \
        --output none 2>/dev/null; then

        # Switch back to user account
        az logout --output none 2>/dev/null || true
        az account set --subscription "$SUBSCRIPTION" > /dev/null

        log_info "Service principal authentication successful"
    else
        log_warn "Service principal created but authentication test failed"
        log_warn "This may resolve after a few minutes of propagation"
    fi
}

#==================================================================================
# Generate .env file
#==================================================================================

generate_env_file() {
    if [ "$SKIP_ENV" = true ]; then
        return
    fi

    log_step "Generating .env file..."

    # Get subscription name
    SUB_NAME=$(az account show --subscription "$SUBSCRIPTION" --query name -o tsv)

    # Create .env file
    cat > "$ENV_FILE" << EOF
# Azure Service Principal for dfo
# Created: $(date +%Y-%m-%d)
# Service Principal: $SP_NAME
# Subscription: $SUB_NAME
# Expires: $(date -d "+${SECRET_EXPIRATION_DAYS} days" +%Y-%m-%d 2>/dev/null || date -v+${SECRET_EXPIRATION_DAYS}d +%Y-%m-%d)

AZURE_TENANT_ID=$TENANT_ID
AZURE_CLIENT_ID=$APP_ID
AZURE_CLIENT_SECRET=$CLIENT_SECRET
AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION

# Optional: Analysis thresholds (uncomment to override defaults)
# DFO_IDLE_CPU_THRESHOLD=5.0
# DFO_IDLE_DAYS=14
# DFO_RIGHTSIZING_CPU_THRESHOLD=20.0
# DFO_SHUTDOWN_DAYS=30

# Optional: Database configuration
# DFO_DUCKDB_FILE=./dfo.duckdb
EOF

    log_info ".env file created: $ENV_FILE"
}

#==================================================================================
# Output results
#==================================================================================

output_results() {
    echo ""

    if [ "$OUTPUT_JSON" = true ]; then
        # JSON output
        cat << EOF
{
  "servicePrincipalName": "$SP_NAME",
  "appId": "$APP_ID",
  "tenantId": "$TENANT_ID",
  "clientSecret": "$CLIENT_SECRET",
  "subscriptionId": "$SUBSCRIPTION",
  "createdAt": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "expiresAt": "$(date -d "+${SECRET_EXPIRATION_DAYS} days" -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -v+${SECRET_EXPIRATION_DAYS}d -u +%Y-%m-%dT%H:%M:%SZ)",
  "expiresInDays": $SECRET_EXPIRATION_DAYS,
  "roles": ["Reader", "Monitoring Reader"],
  "scope": "subscription"
}
EOF
    else
        # Plain text output
        cat << EOF
${GREEN}✓ Service Principal Created Successfully!${NC}

Credentials:
  Service Principal Name: ${BLUE}$SP_NAME${NC}
  Application ID:         ${BLUE}$APP_ID${NC}
  Tenant ID:             ${BLUE}$TENANT_ID${NC}
  Client Secret:         ${BLUE}$CLIENT_SECRET${NC}
  Subscription ID:       ${BLUE}$SUBSCRIPTION${NC}

${YELLOW}⚠ IMPORTANT: Save the client secret now!${NC}
${YELLOW}  It will not be shown again.${NC}

Role Assignments:
  ✓ Reader (subscription scope)
  ✓ Monitoring Reader (subscription scope)

Secret Expiration:
  Expires in: ${SECRET_EXPIRATION_DAYS} days
  Expires on: $(date -d "+${SECRET_EXPIRATION_DAYS} days" +%Y-%m-%d 2>/dev/null || date -v+${SECRET_EXPIRATION_DAYS}d +%Y-%m-%d)

EOF

        if [ "$SKIP_ENV" = false ]; then
            echo ".env file created: $ENV_FILE"
            echo ""
        fi

        cat << EOF
${GREEN}Next steps:${NC}
  1. ${BLUE}Ensure .env is in .gitignore${NC} (it should be by default)
  2. ${BLUE}Validate permissions:${NC} ./validate-permissions.sh
  3. ${BLUE}Initialize database:${NC} cd ../.. && ./dfo db init
  4. ${BLUE}Discover VMs:${NC} ./dfo azure discover vms

EOF
    fi
}

#==================================================================================
# Main execution
#==================================================================================

main() {
    parse_args "$@"

    if [ "$DRY_RUN" = true ]; then
        check_prerequisites
        validate_inputs
        show_dry_run
        exit 0
    fi

    check_prerequisites
    validate_inputs
    create_service_principal
    assign_monitoring_role
    validate_service_principal
    generate_env_file
    output_results
}

# Run main function
main "$@"
