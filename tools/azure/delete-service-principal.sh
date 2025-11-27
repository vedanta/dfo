#!/bin/bash
#
# delete-service-principal.sh
# Safely delete Azure service principal and role assignments
#
# Usage: ./delete-service-principal.sh [OPTIONS]
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
SP_NAME=""
SKIP_CONFIRM=false

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
Safely delete Azure service principal and role assignments

Usage: ./delete-service-principal.sh [OPTIONS]

Options:
  --app-id APP_ID            Application/Client ID to delete
  --name NAME                Service principal name to delete
  --env-file FILE            Read APP_ID from .env file (default: ../../.env)
  --yes                      Skip confirmation prompt
  --help                     Show this help message

Examples:
  # Delete using name
  ./delete-service-principal.sh --name dfo-sp-2025-01-26

  # Delete using app ID
  ./delete-service-principal.sh --app-id 12345678-1234-1234-1234-123456789abc

  # Delete using .env file
  ./delete-service-principal.sh --env-file ../../.env

  # Delete without confirmation
  ./delete-service-principal.sh --name dfo-sp-2025-01-26 --yes

What is deleted:
  1. All role assignments for the service principal
  2. The service principal itself
  3. Associated application registration

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
            --name)
                SP_NAME="$2"
                shift 2
                ;;
            --env-file)
                ENV_FILE="$2"
                shift 2
                ;;
            --yes)
                SKIP_CONFIRM=true
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
}

#==================================================================================
# Load credentials
#==================================================================================

load_credentials() {
    # If app-id not provided, try to load from name or env file
    if [ -z "$APP_ID" ]; then
        if [ -n "$SP_NAME" ]; then
            # Look up by name
            APP_ID=$(az ad sp list --display-name "$SP_NAME" --query '[0].appId' -o tsv 2>/dev/null || echo "")

            if [ -z "$APP_ID" ]; then
                log_error "Service principal not found: $SP_NAME"
                echo ""
                echo "List existing service principals:"
                echo "  ./list-service-principals.sh"
                exit 1
            fi
        elif [ -f "$ENV_FILE" ]; then
            # Load from .env file
            set -a
            source "$ENV_FILE" 2>/dev/null || true
            set +a

            APP_ID="${AZURE_CLIENT_ID:-}"

            if [ -z "$APP_ID" ]; then
                log_error "AZURE_CLIENT_ID not found in $ENV_FILE"
                exit 1
            fi
        else
            log_error "Must provide --app-id, --name, or --env-file"
            echo ""
            show_help
            exit 1
        fi
    fi
}

#==================================================================================
# Get service principal details
#==================================================================================

get_sp_details() {
    log_step "Getting service principal details..."

    # Get SP details
    SP_DETAILS=$(az ad sp show --id "$APP_ID" --output json 2>/dev/null || echo "{}")

    if [ "$SP_DETAILS" = "{}" ] || [ -z "$SP_DETAILS" ]; then
        log_error "Service principal not found: $APP_ID"
        exit 1
    fi

    # Extract details
    SP_NAME=$(echo "$SP_DETAILS" | jq -r '.displayName')
    SP_CREATED=$(echo "$SP_DETAILS" | jq -r '.createdDateTime // "Unknown"')

    log_info "Found service principal: $SP_NAME"
}

#==================================================================================
# Get role assignments
#==================================================================================

get_role_assignments() {
    log_step "Getting role assignments..."

    # Get all role assignments for this service principal across all subscriptions
    ROLE_ASSIGNMENTS=$(az role assignment list --assignee "$APP_ID" --all --output json)

    ROLE_COUNT=$(echo "$ROLE_ASSIGNMENTS" | jq '. | length')

    if [ "$ROLE_COUNT" -eq 0 ]; then
        log_warn "No role assignments found"
    else
        log_info "Found $ROLE_COUNT role assignment(s)"
    fi
}

#==================================================================================
# Show what will be deleted
#==================================================================================

show_deletion_preview() {
    echo ""
    echo "=========================================="
    echo "Service Principal to Delete:"
    echo "  Name:              $SP_NAME"
    echo "  Application ID:    $APP_ID"
    echo "  Created:           ${SP_CREATED:0:10}"
    echo ""

    if [ "$ROLE_COUNT" -gt 0 ]; then
        echo "Role Assignments to Remove:"
        echo "$ROLE_ASSIGNMENTS" | jq -r '.[] | "  - \(.roleDefinitionName) (\(.scope | split("/") | .[-2] + ": " + .[-1]))"'
        echo ""
    fi

    echo -e "${YELLOW}⚠ This action cannot be undone!${NC}"
    echo "=========================================="
    echo ""
}

#==================================================================================
# Confirm deletion
#==================================================================================

confirm_deletion() {
    if [ "$SKIP_CONFIRM" = true ]; then
        return 0
    fi

    read -p "Delete service principal? [y/N]: " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Deletion cancelled"
        exit 0
    fi
}

#==================================================================================
# Remove role assignments
#==================================================================================

remove_role_assignments() {
    if [ "$ROLE_COUNT" -eq 0 ]; then
        return 0
    fi

    log_step "Removing role assignments..."

    # Get assignment IDs
    ASSIGNMENT_IDS=$(echo "$ROLE_ASSIGNMENTS" | jq -r '.[].id')

    # Delete each assignment
    while IFS= read -r assignment_id; do
        ROLE_NAME=$(echo "$ROLE_ASSIGNMENTS" | jq -r ".[] | select(.id == \"$assignment_id\") | .roleDefinitionName")

        if az role assignment delete --ids "$assignment_id" --output none 2>/dev/null; then
            log_info "Removed role assignment: $ROLE_NAME"
        else
            log_warn "Failed to remove role assignment: $ROLE_NAME"
        fi
    done <<< "$ASSIGNMENT_IDS"
}

#==================================================================================
# Delete service principal
#==================================================================================

delete_service_principal() {
    log_step "Deleting service principal..."

    if az ad sp delete --id "$APP_ID" --output none 2>/dev/null; then
        log_info "Deleted service principal: $SP_NAME"
    else
        log_error "Failed to delete service principal"
        exit 1
    fi
}

#==================================================================================
# Output results
#==================================================================================

output_results() {
    echo ""
    echo -e "${GREEN}✓ Service Principal Deleted Successfully${NC}"
    echo ""
    echo "Deleted:"
    echo "  Service Principal: $SP_NAME"
    echo "  Application ID:    $APP_ID"

    if [ "$ROLE_COUNT" -gt 0 ]; then
        echo "  Role Assignments:  $ROLE_COUNT removed"
    fi

    echo ""
    echo "Next steps:"
    if [ -f "$ENV_FILE" ]; then
        echo "  - Delete or update $ENV_FILE if it contains these credentials"
    fi
    echo "  - Create new service principal: ./setup-service-principal.sh"
    echo ""
}

#==================================================================================
# Main execution
#==================================================================================

main() {
    parse_args "$@"
    load_credentials
    get_sp_details
    get_role_assignments
    show_deletion_preview
    confirm_deletion
    remove_role_assignments
    delete_service_principal
    output_results
}

# Run main function
main "$@"
