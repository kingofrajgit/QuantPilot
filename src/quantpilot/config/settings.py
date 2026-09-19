"""Centralized configuration management for QuantPilot.

All configuration is parsed from environment variables or a local `.env` file.
No credentials are hardcoded or required for standard import or startup.
"""

from functools import lru_cache
from typing import Any

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from quantpilot.exceptions import ConfigurationError


class Settings(BaseSettings):
    """Application settings with fail-closed security and safe secret handling."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Core Application Settings (Safe defaults)
    ENVIRONMENT: str = Field(
        default="development",
        description="Runtime environment: development, testing, paper, or production",
    )
    LIVE_TRADING_ENABLED: bool = Field(
        default=False,
        description="Explicit safety gate for live trading. Must default to False.",
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    # AI / LLM Integration Credentials (Optional at startup; validated when invoked)
    ANTHROPIC_API_KEY: SecretStr | None = Field(
        default=None,
        description="Anthropic Claude API key. Never use default fallback secrets.",
    )

    # Broker Integration Credentials (Optional at startup; validated when invoked)
    ZERODHA_API_KEY: SecretStr | None = Field(
        default=None,
        description="Zerodha Kite API key. Never hardcode or fallback.",
    )
    ZERODHA_API_SECRET: SecretStr | None = Field(
        default=None,
        description="Zerodha Kite API secret.",
    )
    ZERODHA_ACCESS_TOKEN: SecretStr | None = Field(
        default=None,
        description="Zerodha Kite access token.",
    )

    # Database & Cache (Optional in local development/testing)
    DATABASE_URL: SecretStr | None = Field(
        default=None,
        description="PostgreSQL connection string.",
    )
    REDIS_URL: SecretStr | None = Field(
        default=None,
        description="Redis connection URL.",
    )

    # Alerting & Webhooks (Optional)
    TELEGRAM_BOT_TOKEN: SecretStr | None = Field(
        default=None,
        description="Telegram bot token for trade and risk alerts.",
    )
    WEBHOOK_SECRET: SecretStr | None = Field(
        default=None,
        description="Secret for validating incoming webhook payloads.",
    )

    def get_anthropic_api_key(self) -> str:
        """Retrieve Anthropic API key, failing closed if absent.

        Never falls back to a default or mock secret.
        """
        if not self.ANTHROPIC_API_KEY or not self.ANTHROPIC_API_KEY.get_secret_value().strip():
            raise ConfigurationError(
                "ANTHROPIC_API_KEY is not configured. Provide it via environment variable "
                "or local .env file. No default fallback secret is permitted."
            )
        return self.ANTHROPIC_API_KEY.get_secret_value()

    def get_zerodha_credentials(self) -> dict[str, str]:
        """Retrieve Zerodha credentials, failing closed if any are missing.

        Never falls back to default or mock secrets.
        """
        missing = []
        if not self.ZERODHA_API_KEY or not self.ZERODHA_API_KEY.get_secret_value().strip():
            missing.append("ZERODHA_API_KEY")
        if not self.ZERODHA_API_SECRET or not self.ZERODHA_API_SECRET.get_secret_value().strip():
            missing.append("ZERODHA_API_SECRET")
        if (
            not self.ZERODHA_ACCESS_TOKEN
            or not self.ZERODHA_ACCESS_TOKEN.get_secret_value().strip()
        ):
            missing.append("ZERODHA_ACCESS_TOKEN")

        if missing:
            raise ConfigurationError(
                f"Missing required Zerodha credential(s): {', '.join(missing)}. "
                "Credentials must be supplied via environment variables or local .env file."
            )

        return {
            "api_key": self.ZERODHA_API_KEY.get_secret_value(),  # type: ignore[union-attr]
            "api_secret": self.ZERODHA_API_SECRET.get_secret_value(),  # type: ignore[union-attr]
            "access_token": self.ZERODHA_ACCESS_TOKEN.get_secret_value(),  # type: ignore[union-attr]
        }

    def safe_dict(self) -> dict[str, Any]:
        """Return a representation with all secrets completely redacted for safe logging."""
        dump = self.model_dump()
        redacted = {}
        for key, value in dump.items():
            field_info = type(self).model_fields.get(key)
            is_secret = False
            if field_info and field_info.annotation:
                is_secret = "SecretStr" in str(field_info.annotation)

            if is_secret:
                secret_obj = getattr(self, key, None)
                if secret_obj is not None and hasattr(secret_obj, "get_secret_value"):
                    redacted[key] = (
                        "***SET***" if secret_obj.get_secret_value().strip() else "***UNSET***"
                    )
                else:
                    redacted[key] = "***UNSET***"
            else:
                redacted[key] = value
        return redacted

    def __repr__(self) -> str:
        safe_fields = ", ".join(f"{k}={v!r}" for k, v in self.safe_dict().items())
        return f"Settings({safe_fields})"

    def __str__(self) -> str:
        return self.__repr__()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
