"""Pytest configuration and shared fixtures for QuantPilot."""

import pytest

from quantpilot.config.settings import Settings, get_settings


@pytest.fixture(autouse=True)
def clean_env_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure tests run in an isolated environment without real external credentials."""
    # Ensure live trading is never enabled accidentally during tests
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "false")
    monkeypatch.setenv("ENVIRONMENT", "testing")

    # Clear cached settings instance
    get_settings.cache_clear()


@pytest.fixture
def clean_settings() -> Settings:
    """Provide a fresh default Settings instance with no credentials."""
    return Settings(
        ENVIRONMENT="testing",
        LIVE_TRADING_ENABLED=False,
        ANTHROPIC_API_KEY=None,
        ZERODHA_API_KEY=None,
        ZERODHA_API_SECRET=None,
        ZERODHA_ACCESS_TOKEN=None,
        DATABASE_URL=None,
        REDIS_URL=None,
    )
