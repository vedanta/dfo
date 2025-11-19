#!/usr/bin/env bash
# dfo CLI wrapper script
# This allows you to run ./dfo.sh from the root directory

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Execute the dfo CLI module with all arguments passed through
python -m dfo.cli "$@"
