"""DuckDB integration layer.

This module provides centralized DuckDB operations for the MVP.
All database access must go through this module per CODE_STYLE.md.

Key features:
- Singleton connection manager
- Schema initialization from schema.sql
- Helper functions for common operations
"""
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

# Third-party
import duckdb

# Internal
from dfo.core.config import get_settings


class DuckDBManager:
    """DuckDB connection and query manager.

    This class manages the singleton database connection and provides
    helper methods for common database operations.
    """

    _instance: Optional['DuckDBManager'] = None
    _connection: Optional[duckdb.DuckDBPyConnection] = None

    def __new__(cls):
        """Implement singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize manager (only once due to singleton)."""
        if self._connection is None:
            settings = get_settings()
            self.db_path = settings.dfo_duckdb_file
            self._connection = self._create_connection()

    def _create_connection(self) -> duckdb.DuckDBPyConnection:
        """Create DuckDB connection.

        Returns:
            DuckDB connection object.
        """
        # Ensure parent directory exists
        db_path = Path(self.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Connect to database
        conn = duckdb.connect(str(db_path))
        return conn

    def initialize_schema(self, drop_existing: bool = False) -> None:
        """Initialize database schema from schema.sql.

        Args:
            drop_existing: If True, drop existing tables before creating.

        Raises:
            FileNotFoundError: If schema.sql file is not found.
        """
        schema_path = Path(__file__).parent / "schema.sql"
        if not schema_path.exists():
            raise FileNotFoundError(
                f"Schema file not found: {schema_path}. "
                "Ensure schema.sql exists in the db/ directory."
            )

        if drop_existing:
            tables = ["vm_actions", "vm_idle_analysis", "vm_inventory"]
            for table in tables:
                self._connection.execute(f"DROP TABLE IF EXISTS {table}")
            self._connection.commit()

        schema_sql = schema_path.read_text()
        self._connection.execute(schema_sql)
        self._connection.commit()

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        """Get the database connection.

        Returns:
            The active DuckDB connection.
        """
        return self._connection

    def execute_query(
        self,
        query: str,
        params: Optional[tuple] = None
    ) -> duckdb.DuckDBPyRelation:
        """Execute a SQL query.

        Args:
            query: SQL query string.
            params: Optional query parameters.

        Returns:
            Query result relation.
        """
        if params:
            return self._connection.execute(query, params)
        return self._connection.execute(query)

    def insert_records(
        self,
        table: str,
        records: List[Dict[str, Any]]
    ) -> None:
        """Insert multiple records into a table.

        Args:
            table: Table name.
            records: List of record dictionaries.
        """
        if not records:
            return

        # Get column names from first record
        columns = list(records[0].keys())
        placeholders = ", ".join(["?" for _ in columns])
        column_names = ", ".join(columns)

        query = f"INSERT INTO {table} ({column_names}) VALUES ({placeholders})"

        # Convert records to tuples
        values = [
            tuple(record[col] for col in columns)
            for record in records
        ]

        # Execute batch insert
        self._connection.executemany(query, values)
        self._connection.commit()

    def fetch_all(
        self,
        query: str,
        params: Optional[tuple] = None
    ) -> List[tuple]:
        """Execute query and fetch all results.

        Args:
            query: SQL query string.
            params: Optional query parameters.

        Returns:
            List of result tuples.
        """
        result = self.execute_query(query, params)
        return result.fetchall()

    def fetch_df(self, query: str, params: Optional[tuple] = None):
        """Execute query and return as pandas DataFrame.

        Args:
            query: SQL query string.
            params: Optional query parameters.

        Returns:
            Pandas DataFrame with query results.
        """
        result = self.execute_query(query, params)
        return result.df()

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists.

        Args:
            table_name: Name of the table to check.

        Returns:
            True if table exists, False otherwise.
        """
        query = """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name = ?
        """
        result = self.fetch_all(query, (table_name,))
        return result[0][0] > 0

    def count_records(self, table: str) -> int:
        """Count records in a table.

        Args:
            table: Table name.

        Returns:
            Number of records in the table.
        """
        result = self.fetch_all(f"SELECT COUNT(*) FROM {table}")
        return result[0][0]

    def clear_table(self, table: str) -> None:
        """Delete all records from a table.

        Args:
            table: Table name to clear.
        """
        self.execute_query(f"DELETE FROM {table}")
        self._connection.commit()

    def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None


# Convenience functions
def get_db() -> DuckDBManager:
    """Get the DuckDB manager singleton.

    Returns:
        The singleton DuckDBManager instance.
    """
    return DuckDBManager()


@contextmanager
def db_connection():
    """Context manager for database operations.

    Yields:
        DuckDBManager instance.

    Example:
        with db_connection() as db:
            db.insert_records("vm_inventory", records)
    """
    db = get_db()
    try:
        yield db
    finally:
        # Connection persists (singleton), just ensures proper usage
        pass


def reset_db() -> None:
    """Reset database singleton.

    Useful for testing to ensure clean state between tests.
    Should not be called in production code.
    """
    DuckDBManager._instance = None
    DuckDBManager._connection = None
