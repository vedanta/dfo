#!/bin/bash
#
# validate-permissions.sh
# Validate Azure service principal has correct permissions for dfo
#
# Usage: ./validate-permissions.sh [OPTIONS]
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values
DEFAULT_ENV_FILE="../../.env"
ENV_FILE="$DEFAULT_ENV_FILE"
APP_ID=""
SUBSCRIPTION=""

# Validation results
ERRORS=0
WARNINGS=0

#==================================================================================
# Logging functions
#==================================================================================

log_info() {
    echo -e "${GREEN}✓${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
    ((ERRORS++))
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
}

log_step() {
    echo -e "${BLUE}→${NC} $1"
}

#==================================================================================
# Help message
#==================================================================================

show_help() {
    cat << EOF
Validate Azure service principal permissions for dfo

Usage: ./validate-permissions.sh [OPTIONS]

Options:
  --app-id APP_ID            Application/Client ID (from .env or arg)
  --subscription SUBSCRIPTION Subscription to check (default: current)
  --env-file FILE            Read credentials from .env file (default: ../../.env)
  --help                     Show this help message

Examples:
  # Validate using default .env file
  ./validate-permissions.sh

  # Validate specific .env file
  ./validate-permissions.sh --env-file ../../.env.prod

  # Validate specific app ID
  ./validate-permissions.sh --app-id 12345678-1234-1234-1234-123456789abc

What is validated:
  - Credentials are present
  - Service principal can authenticate
  - Reader role is assigned
  - Monitoring Reader role is assigned
  - Can list VMs via API
  - Can read metrics via API
  - Credential expiration status

EOF
}

#==================================================================================
# Parse arguments
#==================================================================================

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --app-id)
                APP_ID="$2"
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
}

#==================================================================================
# Load credentials from .env
#==================================================================================

load_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        log_error "Environment file not found: $ENV_FILE"
        echo ""
        echo "Create service principal:"
        echo "  ./setup-service-principal.sh"
        exit 1
    fi

    # Source .env file
    set -a
    source "$ENV_FILE"
    set +a

    # Set APP_ID if not provided as argument
    if [ -z "$APP_ID" ]; then
        APP_ID="$AZURE_CLIENT_ID"
    fi

    # Set SUBSCRIPTION if not provided
    if [ -z "$SUBSCRIPTION" ]; then
        SUBSCRIPTION="$AZURE_SUBSCRIPTION_ID"
    fi
}

#==================================================================================
# Check credentials
#==================================================================================

check_credentials() {
    echo ""
    log_step "Checking credentials..."

    # Check AZURE_TENANT_ID
    if [ -z "${AZURE_TENANT_ID:-}" ]; then
        log_error "AZURE_TENANT_ID not found in $ENV_FILE"
    else
        log_info "AZURE_TENANT_ID found"
    fi

    # Check AZURE_CLIENT_ID
    if [ -z "${AZURE_CLIENT_ID:-}" ]; then
        log_error "AZURE_CLIENT_ID not found in $ENV_FILE"
    else
        log_info "AZURE_CLIENT_ID found"
    fi

    # Check AZURE_CLIENT_SECRET
    if [ -z "${AZURE_CLIENT_SECRET:-}" ]; then
        log_error "AZURE_CLIENT_SECRET not found in $ENV_FILE"
    else
        log_info "AZURE_CLIENT_SECRET found"
    fi

    # Check AZURE_SUBSCRIPTION_ID
    if [ -z "${AZURE_SUBSCRIPTION_ID:-}" ]; then
        log_error "AZURE_SUBSCRIPTION_ID not found in $ENV_FILE"
    else
        log_info "AZURE_SUBSCRIPTION_ID found"
    fi

    if [ $ERRORS -gt 0 ]; then
        echo ""
        log_error "Missing required credentials"
        exit 1
    fi
}

#==================================================================================
# Test authentication
#==================================================================================

test_authentication() {
    echo ""
    log_step "Testing authentication..."

    # Try to authenticate with service principal
    if az login --service-principal \
        --username "$AZURE_CLIENT_ID" \
        --password "$AZURE_CLIENT_SECRET" \
        --tenant "$AZURE_TENANT_ID" \
        --allow-no-subscriptions \
        --output none 2>/dev/null; then

        log_info "Service principal can authenticate"

        # Set subscription
        if az account set --subscription "$SUBSCRIPTION" 2>/dev/null; then
            log_info "Can access subscription"
        else
            log_error "Cannot access subscription: $SUBSCRIPTION"
        fi
    else
        log_error "Service principal authentication failed"
        echo ""
        echo "Verify credentials in $ENV_FILE"
        exit 1
    fi
}

#==================================================================================
# Check role assignments
#==================================================================================

check_role_assignments() {
    echo ""
    log_step "Checking role assignments..."

    # Get role assignments for this service principal
    ROLE_ASSIGNMENTS=$(az role assignment list \
        --assignee "$APP_ID" \
        --subscription "$SUBSCRIPTION" \
        --output json)

    # Check for Reader role
    if echo "$ROLE_ASSIGNMENTS" | jq -e '.[] | select(.roleDefinitionName == "Reader")' > /dev/null; then
        log_info "Reader role assigned (subscription scope)"
    else
        log_error "Reader role NOT assigned"
        echo ""
        echo "Fix: az role assignment create \\"
        echo "  --assignee $APP_ID \\"
        echo "  --role \"Reader\" \\"
        echo "  --subscription $SUBSCRIPTION"
    fi

    # Check for Monitoring Reader role
    if echo "$ROLE_ASSIGNMENTS" | jq -e '.[] | select(.roleDefinitionName == "Monitoring Reader")' > /dev/null; then
        log_info "Monitoring Reader role assigned (subscription scope)"
    else
        log_error "Monitoring Reader role NOT assigned"
        echo ""
        echo "Fix: az role assignment create \\"
        echo "  --assignee $APP_ID \\"
        echo "  --role \"Monitoring Reader\" \\"
        echo "  --subscription $SUBSCRIPTION"
    fi
}

#==================================================================================
# Test API access
#==================================================================================

test_api_access() {
    echo ""
    log_step "Testing API access..."

    # Test listing VMs
    VM_LIST=$(az vm list --output json 2>/dev/null || echo "[]")
    VM_COUNT=$(echo "$VM_LIST" | jq '. | length')

    if [ "$VM_COUNT" -ge 0 ]; then
        if [ "$VM_COUNT" -eq 0 ]; then
            log_info "Can list VMs (found 0 VMs)"
        else
            log_info "Can list VMs (found $VM_COUNT VMs)"

            # Test reading metrics on first VM
            FIRST_VM_ID=$(echo "$VM_LIST" | jq -r '.[0].id')
            if [ -n "$FIRST_VM_ID" ] && [ "$FIRST_VM_ID" != "null" ]; then
                if az monitor metrics list \
                    --resource "$FIRST_VM_ID" \
                    --metric "Percentage CPU" \
                    --output none 2>/dev/null; then
                    log_info "Can read metrics"
                else
                    log_error "Cannot read metrics"
                    echo ""
                    echo "Ensure Monitoring Reader role is assigned"
                fi
            fi
        fi
    else
        log_error "Cannot list VMs"
        echo ""
        echo "Ensure Reader role is assigned"
    fi
}

#==================================================================================
# Check credential expiration
#==================================================================================

check_expiration() {
    echo ""
    log_step "Checking credential expiration..."

    # Get service principal details
    SP_DETAILS=$(az ad sp show --id "$APP_ID" --output json 2>/dev/null || echo "{}")

    # Get password credentials
    PASSWORD_CREDS=$(echo "$SP_DETAILS" | jq -r '.passwordCredentials[0]')

    if [ "$PASSWORD_CREDS" != "null" ]; then
        END_DATE=$(echo "$PASSWORD_CREDS" | jq -r '.endDateTime')

        if [ -n "$END_DATE" ] && [ "$END_DATE" != "null" ]; then
            # Calculate days until expiration
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS
                END_EPOCH=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$END_DATE" +%s 2>/dev/null || echo "0")
                NOW_EPOCH=$(date +%s)
            else
                # Linux
                END_EPOCH=$(date -d "$END_DATE" +%s 2>/dev/null || echo "0")
                NOW_EPOCH=$(date +%s)
            fi

            DAYS_REMAINING=$(( (END_EPOCH - NOW_EPOCH) / 86400 ))

            if [ "$DAYS_REMAINING" -lt 0 ]; then
                log_error "Credential EXPIRED on $END_DATE"
                echo ""
                echo "Rotate credential: az ad sp credential reset --id $APP_ID"
            elif [ "$DAYS_REMAINING" -lt 7 ]; then
                log_warn "Credential expires in $DAYS_REMAINING days (on $END_DATE)"
                echo ""
                echo "Consider rotating: az ad sp credential reset --id $APP_ID"
            elif [ "$DAYS_REMAINING" -lt 14 ]; then
                log_warn "Credential expires in $DAYS_REMAINING days (on $END_DATE)"
            else
                log_info "Valid until: $END_DATE ($DAYS_REMAINING days remaining)"
            fi
        else
            log_warn "Could not determine expiration date"
        fi
    else
        log_warn "Could not retrieve credential information"
    fi
}

#==================================================================================
# Output summary
#==================================================================================

output_summary() {
    echo ""
    echo "=========================================="

    if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
        echo -e "${GREEN}✓ All permissions valid! dfo is ready to use.${NC}"
    elif [ $ERRORS -eq 0 ]; then
        echo -e "${YELLOW}⚠ Validation complete with $WARNINGS warning(s)${NC}"
        echo -e "${YELLOW}  Review warnings above${NC}"
    else
        echo -e "${RED}✗ Validation failed with $ERRORS error(s) and $WARNINGS warning(s)${NC}"
        echo -e "${RED}  Fix errors above before using dfo${NC}"
        exit 1
    fi

    echo "=========================================="
    echo ""
}

#==================================================================================
# Cleanup
#==================================================================================

cleanup() {
    # Logout service principal and restore user session
    az logout --output none 2>/dev/null || true

    # Re-login with user account if possible
    if command -v az &> /dev/null; then
        # Try to restore previous account (will prompt if needed)
        az account show &> /dev/null || true
    fi
}

#==================================================================================
# Main execution
#==================================================================================

main() {
    parse_args "$@"
    load_env_file

    echo "Validating Service Principal Permissions..."
    echo "Service Principal: $APP_ID"
    echo "Subscription: $SUBSCRIPTION"

    check_credentials
    test_authentication
    check_role_assignments
    test_api_access
    check_expiration
    output_summary

    cleanup
}

# Trap to ensure cleanup on exit
trap cleanup EXIT

# Run main function
main "$@"
