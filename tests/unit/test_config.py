"""Unit tests for centralized configuration management."""

import pytest
from pydantic import SecretStr

from quantpilot.config.settings import Settings
from quantpilot.exceptions import ConfigurationError


def test_default_settings_are_safe():
    """Verify that default settings enforce safe states and require no credentials."""
    settings = Settings()
    assert settings.ENVIRONMENT in ("development", "testing")
    assert settings.LIVE_TRADING_ENABLED is False
    assert settings.LOG_LEVEL == "INFO"
    assert settings.ANTHROPIC_API_KEY is None
    assert settings.ZERODHA_API_KEY is None


def test_missing_anthropic_credential_fails_closed():
    """Verify missing Anthropic API key raises ConfigurationError without fallbacks."""
    settings = Settings(ANTHROPIC_API_KEY=None)
    with pytest.raises(ConfigurationError, match="ANTHROPIC_API_KEY is not configured"):
        settings.get_anthropic_api_key()


def test_missing_zerodha_credentials_fails_closed():
    """Verify missing Zerodha credentials raise ConfigurationError listing missing fields."""
    settings = Settings(
        ZERODHA_API_KEY=None,
        ZERODHA_API_SECRET=None,
        ZERODHA_ACCESS_TOKEN=None,
    )
    with pytest.raises(ConfigurationError, match="Missing required Zerodha credential"):
        settings.get_zerodha_credentials()


def test_partial_zerodha_credentials_fails_closed():
    """Verify partial credentials are also rejected without fallback."""
    settings = Settings(
        ZERODHA_API_KEY=SecretStr("mock-key"),
        ZERODHA_API_SECRET=None,
        ZERODHA_ACCESS_TOKEN=None,
    )
    with pytest.raises(ConfigurationError, match="ZERODHA_API_SECRET, ZERODHA_ACCESS_TOKEN"):
        settings.get_zerodha_credentials()


def test_configured_credentials_retrieved_correctly():
    """Verify provided credentials can be accessed via getter methods."""
    settings = Settings(
        ANTHROPIC_API_KEY=SecretStr("mock-anthropic-key-for-test"),
        ZERODHA_API_KEY=SecretStr("mock-zerodha-key-for-test"),
        ZERODHA_API_SECRET=SecretStr("mock-zerodha-secret-for-test"),
        ZERODHA_ACCESS_TOKEN=SecretStr("mock-zerodha-token-for-test"),
    )
    assert settings.get_anthropic_api_key() == "mock-anthropic-key-for-test"
    creds = settings.get_zerodha_credentials()
    assert creds["api_key"] == "mock-zerodha-key-for-test"
    assert creds["api_secret"] == "mock-zerodha-secret-for-test"
    assert creds["access_token"] == "mock-zerodha-token-for-test"


def test_safe_dict_redaction():
    """Verify safe_dict completely hides secrets from dumps."""
    settings = Settings(
        ANTHROPIC_API_KEY=SecretStr("sensitive-key"),
        ZERODHA_API_KEY=None,
    )
    dump = settings.safe_dict()
    assert dump["ANTHROPIC_API_KEY"] == "***SET***"
    assert dump["ZERODHA_API_KEY"] == "***UNSET***"
    assert "sensitive-key" not in str(dump)


def test_settings_repr_does_not_leak_secrets():
    """Verify __repr__ and __str__ never output raw secret values."""
    settings = Settings(
        ANTHROPIC_API_KEY=SecretStr("super-secret-key-12345"),
        ZERODHA_API_SECRET=SecretStr("super-secret-kite-secret"),
    )
    repr_str = repr(settings)
    str_str = str(settings)

    assert "super-secret-key-12345" not in repr_str
    assert "super-secret-kite-secret" not in repr_str
    assert "super-secret-key-12345" not in str_str
    assert "super-secret-kite-secret" not in str_str
