"""Configuration management using Pydantic Settings.

This module provides centralized configuration loading from environment variables.
Settings are validated using Pydantic and exposed via a singleton pattern.

All DFO-specific environment variables use the DFO_ prefix per CODE_STYLE.md.
"""
from typing import Optional

# Third-party
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings can be configured via:
    - .env file in project root
    - Environment variables

    Environment variables use uppercase names (e.g., AZURE_TENANT_ID).
    DFO-specific variables use DFO_ prefix (e.g., DFO_IDLE_CPU_THRESHOLD).
    """

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False
    )

    # Azure Authentication (standard Azure SDK variables)
    azure_tenant_id: str
    azure_client_id: str
    azure_client_secret: str
    azure_subscription_id: str

    # Analysis Configuration (DFO_ prefix)
    dfo_idle_cpu_threshold: float = 5.0
    dfo_idle_days: int = 14
    dfo_dry_run_default: bool = True
    dfo_disable_rules: str = ""  # Comma-separated list of rule types to disable
    dfo_service_types: str = ""  # Comma-separated list of service types to enable (empty = all)

    # DuckDB Configuration (DFO_ prefix)
    dfo_duckdb_file: str = "./dfo.duckdb"

    # Logging Configuration (DFO_ prefix)
    dfo_log_level: str = "INFO"


# Singleton instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the settings singleton.

    Returns:
        Settings: The application settings instance.

    Raises:
        ValidationError: If required environment variables are missing or invalid.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset settings singleton.

    Useful for testing to ensure clean state between tests.
    Should not be called in production code.
    """
    global _settings
    _settings = None
