"""Security sanitization utilities for QuantPilot.

Prevents credentials, authorization tokens, connection string passwords,
and sensitive keys from leaking into log files, error reports, and console outputs.
"""

import logging
import re
from typing import Any

# Regular expression patterns for common sensitive tokens and credential strings
_URL_PASSWORD_PATTERN = re.compile(
    r"((?:postgresql|postgres|redis|mysql|https?|amqp)://[^:]+:)([^@\s]+)(@)",
    re.IGNORECASE,
)
_BEARER_PATTERN = re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{8,}", re.IGNORECASE)
_AUTH_HEADER_PATTERN = re.compile(
    r"((?:authorization|x-api-key|x-auth-token)\s*[:=]\s*['\"]?)([^\r\n,'\"\}]+)(['\"]?)",
    re.IGNORECASE,
)
_KEY_VALUE_SECRET_PATTERN = re.compile(
    r"((?:api_key|api_secret|access_token|password|secret_key|client_secret)\s*[:=]\s*['\"]?)([^'\"\s,\}]+)(['\"]?)",
    re.IGNORECASE,
)


def _sanitize_auth_header(match: re.Match) -> str:
    prefix = match.group(1)
    val = match.group(2).strip()
    quote = match.group(3) or ""
    if re.match(r"^Bearer\s+", val, re.IGNORECASE):
        return f"{prefix}Bearer ***REDACTED***{quote}"
    return f"{prefix}***REDACTED***{quote}"


def sanitize_text(text: str, custom_secrets: list[str] | None = None) -> str:
    """Sanitize sensitive credentials, tokens, and passwords from a string.

    Args:
        text: Input string to sanitize.
        custom_secrets: Optional list of known secret strings to redact.

    Returns:
        Sanitized string with sensitive information redacted.
    """
    if not text:
        return text

    sanitized = text

    # Redact URL passwords (e.g., postgresql://user:pass@host)
    sanitized = _URL_PASSWORD_PATTERN.sub(r"\1***REDACTED***\3", sanitized)

    # Redact Authorization headers (Bearer, Basic, or raw tokens)
    sanitized = _AUTH_HEADER_PATTERN.sub(_sanitize_auth_header, sanitized)

    # Redact standalone Bearer tokens
    sanitized = _BEARER_PATTERN.sub(r"\1***REDACTED***", sanitized)

    # Redact key-value secrets
    sanitized = _KEY_VALUE_SECRET_PATTERN.sub(r"\1***REDACTED***\3", sanitized)

    # Redact explicit custom secrets (e.g. from active Settings)
    if custom_secrets:
        for secret in custom_secrets:
            if secret and len(secret.strip()) >= 4:
                sanitized = sanitized.replace(secret.strip(), "***REDACTED***")

    return sanitized


def sanitize_dict(data: dict[str, Any], custom_secrets: list[str] | None = None) -> dict[str, Any]:
    """Recursively sanitize keys and values in a dictionary."""
    sanitized: dict[str, Any] = {}
    sensitive_keys = {
        "api_key",
        "api_secret",
        "access_token",
        "password",
        "secret",
        "token",
        "auth",
        "authorization",
        "webhook_secret",
        "anthropic_api_key",
        "zerodha_api_key",
        "zerodha_api_secret",
        "zerodha_access_token",
    }

    for key, value in data.items():
        lower_key = str(key).lower()
        if any(sens in lower_key for sens in sensitive_keys):
            sanitized[key] = "***REDACTED***"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict(value, custom_secrets)
        elif isinstance(value, str):
            sanitized[key] = sanitize_text(value, custom_secrets)
        else:
            sanitized[key] = value

    return sanitized


class SecurityLogFilter(logging.Filter):
    """Logging filter that scrubs sensitive patterns from all log records."""

    def __init__(self, custom_secrets: list[str] | None = None) -> None:
        super().__init__()
        self.custom_secrets = custom_secrets or []

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = sanitize_text(record.msg, self.custom_secrets)
        if record.args:
            if isinstance(record.args, dict):
                record.args = sanitize_dict(record.args, self.custom_secrets)
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    sanitize_text(str(arg), self.custom_secrets) if isinstance(arg, str) else arg
                    for arg in record.args
                )
        return True
