"""Shared pytest fixtures."""

import pytest
from dfo.db.duck import reset_db, DuckDBManager
from dfo.core.config import reset_settings


@pytest.fixture
def test_db(monkeypatch, tmp_path):
    """Setup test database."""
    # Create temp database
    test_db_path = tmp_path / "test.duckdb"
    monkeypatch.setenv("DFO_DUCKDB_FILE", str(test_db_path))
    monkeypatch.setenv("DFO_IDLE_CPU_THRESHOLD", "5.0")
    monkeypatch.setenv("DFO_IDLE_DAYS", "7")

    reset_settings()
    reset_db()

    # Initialize database
    db = DuckDBManager()
    db.initialize_schema()

    yield db

    reset_settings()
    reset_db()
