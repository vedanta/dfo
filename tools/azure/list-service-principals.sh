#!/bin/bash
#
# list-service-principals.sh
# List all dfo-related service principals
#
# Usage: ./list-service-principals.sh [OPTIONS]
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values
LIST_ALL=false
SUBSCRIPTION=""
OUTPUT_FORMAT="table"

#==================================================================================
# Logging functions
#==================================================================================

log_error() {
    echo -e "${RED}✗${NC} $1" >&2
}

#==================================================================================
# Help message
#==================================================================================

show_help() {
    cat << EOF
List all dfo-related service principals

Usage: ./list-service-principals.sh [OPTIONS]

Options:
  --all                      List all service principals (not just dfo-*)
  --subscription SUBSCRIPTION Subscription to check (default: current)
  --format FORMAT            Output format: table|json (default: table)
  --help                     Show this help message

Examples:
  # List all dfo service principals
  ./list-service-principals.sh

  # List all service principals
  ./list-service-principals.sh --all

  # Get JSON output
  ./list-service-principals.sh --format json

  # Check specific subscription
  ./list-service-principals.sh --subscription "Production"

EOF
}

#==================================================================================
# Parse arguments
#==================================================================================

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --all)
                LIST_ALL=true
                shift
                ;;
            --subscription)
                SUBSCRIPTION="$2"
                shift 2
                ;;
            --format)
                OUTPUT_FORMAT="$2"
                if [[ ! "$OUTPUT_FORMAT" =~ ^(table|json)$ ]]; then
                    log_error "Invalid format: $OUTPUT_FORMAT (must be table or json)"
                    exit 1
                fi
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
# Check prerequisites
#==================================================================================

check_prerequisites() {
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

    # Set subscription if provided
    if [ -n "$SUBSCRIPTION" ]; then
        if ! az account set --subscription "$SUBSCRIPTION" 2>/dev/null; then
            log_error "Failed to set subscription: $SUBSCRIPTION"
            exit 1
        fi
    else
        SUBSCRIPTION=$(az account show --query id -o tsv)
    fi
}

#==================================================================================
# Get service principals
#==================================================================================

get_service_principals() {
    if [ "$LIST_ALL" = true ]; then
        # List all service principals
        SP_LIST=$(az ad sp list --all --output json)
    else
        # List only dfo-* service principals
        SP_LIST=$(az ad sp list --display-name "dfo-" --all --output json)
    fi

    # Filter and enhance the list
    ENHANCED_LIST=$(echo "$SP_LIST" | jq --arg sub "$SUBSCRIPTION" '[
        .[] |
        select(.displayName | startswith("dfo-") or ($ARGS.named.all == "true")) |
        {
            name: .displayName,
            appId: .appId,
            created: .createdDateTime,
            objectId: .id,
            passwordCreds: .passwordCredentials
        }
    ]' --argjson all "$LIST_ALL")

    # Get count
    SP_COUNT=$(echo "$ENHANCED_LIST" | jq '. | length')
}

#==================================================================================
# Add expiration info
#==================================================================================

add_expiration_info() {
    # Add expiration and status for each SP
    FINAL_LIST=$(echo "$ENHANCED_LIST" | jq '[
        .[] |
        . + {
            expires: (
                if .passwordCreds and (.passwordCreds | length) > 0 then
                    .passwordCreds[0].endDateTime
                else
                    null
                end
            ),
            status: (
                if .passwordCreds and (.passwordCreds | length) > 0 then
                    if (.passwordCreds[0].endDateTime // "" | fromdateiso8601) > now then
                        "active"
                    else
                        "expired"
                    end
                else
                    "no-creds"
                end
            )
        } |
        del(.passwordCreds)
    ]')
}

#==================================================================================
# Output as table
#==================================================================================

output_table() {
    if [ "$SP_COUNT" -eq 0 ]; then
        if [ "$LIST_ALL" = true ]; then
            echo "No service principals found"
        else
            echo "No dfo service principals found"
            echo ""
            echo "Create one with: ./setup-service-principal.sh"
        fi
        return
    fi

    if [ "$LIST_ALL" = true ]; then
        echo "All Service Principals:"
    else
        echo "DFO Service Principals:"
    fi
    echo ""

    # Print header
    printf "%-25s %-36s %-12s %-12s %-10s\n" "Name" "App ID" "Created" "Expires" "Status"
    printf "%-25s %-36s %-12s %-12s %-10s\n" "----" "------" "-------" "-------" "------"

    # Print each service principal
    echo "$FINAL_LIST" | jq -r '.[] | [
        .name,
        .appId,
        (.created // "Unknown" | split("T")[0]),
        (.expires // "Unknown" | split("T")[0]),
        .status
    ] | @tsv' | while IFS=$'\t' read -r name appId created expires status; do
        # Color code status
        if [ "$status" = "active" ]; then
            status_display="${GREEN}✓${NC} Active"
        elif [ "$status" = "expired" ]; then
            status_display="${RED}✗${NC} Expired"
        else
            status_display="${YELLOW}⚠${NC} No creds"
        fi

        # Check if expiring soon (within 7 days)
        if [ "$expires" != "Unknown" ]; then
            if [[ "$OSTYPE" == "darwin"* ]]; then
                expires_epoch=$(date -j -f "%Y-%m-%d" "$expires" +%s 2>/dev/null || echo "0")
                now_epoch=$(date +%s)
            else
                expires_epoch=$(date -d "$expires" +%s 2>/dev/null || echo "0")
                now_epoch=$(date +%s)
            fi

            days_remaining=$(( (expires_epoch - now_epoch) / 86400 ))

            if [ "$days_remaining" -lt 7 ] && [ "$days_remaining" -ge 0 ]; then
                status_display="${YELLOW}⚠${NC} Expires soon"
            fi
        fi

        printf "%-25s %-36s %-12s %-12s " "$name" "$appId" "$created" "$expires"
        echo -e "$status_display"
    done

    echo ""
    echo "Total: $SP_COUNT service principal(s)"
}

#==================================================================================
# Output as JSON
#==================================================================================

output_json() {
    echo "$FINAL_LIST" | jq '{
        subscription: "'"$SUBSCRIPTION"'",
        count: '"$SP_COUNT"',
        servicePrincipals: .
    }'
}

#==================================================================================
# Main execution
#==================================================================================

main() {
    parse_args "$@"
    check_prerequisites
    get_service_principals
    add_expiration_info

    if [ "$OUTPUT_FORMAT" = "json" ]; then
        output_json
    else
        output_table
    fi
}

# Run main function
main "$@"
