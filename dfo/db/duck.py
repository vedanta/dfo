"""DuckDB integration layer for the MVP.

This module will:
  - open the DuckDB database defined in environment variable DUCKDB_FILE
  - initialize tables if they do not exist
  - provide insert/select helpers for:
      * vm_inventory
      * vm_idle_analysis
      * vm_actions
"""

# TODO: implement DuckDB connection + helpers later.
