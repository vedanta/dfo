"""Tests for configuration management."""
import pytest

# Third-party
from pydantic import ValidationError

# Internal
from dfo.core.config import Settings, get_settings, reset_settings


def test_settings_defaults():
    """Test default values are set correctly (including .env overrides)."""
    # Need to provide required fields
    settings = Settings(
        azure_tenant_id="test-tenant",
        azure_client_id="test-client",
        azure_client_secret="test-secret",
        azure_subscription_id="test-sub"
    )
    # Note: .env file overrides the code defaults
    assert settings.dfo_idle_cpu_threshold == 1.0  # From .env
    assert settings.dfo_idle_days == 1  # From .env
    assert settings.dfo_dry_run_default is True
    assert settings.dfo_duckdb_file == "./dfo.duckdb"
    assert settings.dfo_log_level == "INFO"


def test_settings_validation(monkeypatch):
    """Test that missing required fields raise errors."""
    # Clear Azure env vars to ensure validation fails
    monkeypatch.delenv("AZURE_TENANT_ID", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("AZURE_SUBSCRIPTION_ID", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings(dfo_duckdb_file="test.db", _env_file=None)

    # Should complain about missing azure_* fields
    assert "azure_tenant_id" in str(exc_info.value)


def test_settings_from_env(monkeypatch):
    """Test loading settings from environment."""
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-subscription")
    monkeypatch.setenv("DFO_DUCKDB_FILE", "test.duckdb")
    monkeypatch.setenv("DFO_IDLE_CPU_THRESHOLD", "10.0")

    reset_settings()
    settings = get_settings()

    assert settings.azure_tenant_id == "test-tenant"
    assert settings.dfo_duckdb_file == "test.duckdb"
    assert settings.dfo_idle_cpu_threshold == 10.0


def test_settings_singleton(monkeypatch):
    """Test that get_settings returns the same instance."""
    monkeypatch.setenv("AZURE_TENANT_ID", "test")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test")

    reset_settings()
    settings1 = get_settings()
    settings2 = get_settings()

    assert settings1 is settings2


def test_reset_settings(monkeypatch):
    """Test that reset_settings clears the singleton."""
    monkeypatch.setenv("AZURE_TENANT_ID", "test")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test")

    reset_settings()
    settings1 = get_settings()
    reset_settings()
    settings2 = get_settings()

    # Should be different instances after reset
    assert settings1 is not settings2
