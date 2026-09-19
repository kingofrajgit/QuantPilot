"""Unit tests for repository security rules, secret absence, and log sanitization."""

import logging
import re
from pathlib import Path

from quantpilot.security.sanitizer import SecurityLogFilter, sanitize_dict, sanitize_text

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_gitignore_contains_mandatory_security_rules():
    """Verify that .gitignore includes all mandatory patterns to prevent credential leaks."""
    gitignore_path = REPO_ROOT / ".gitignore"
    assert gitignore_path.exists(), ".gitignore must exist in the repository root"

    content = gitignore_path.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines()]

    # Mandatory credential patterns
    assert ".env" in lines
    assert ".env.*" in lines
    assert "!.env.example" in lines
    assert "*.pem" in lines
    assert "*.key" in lines
    assert "*.p12" in lines
    assert "*.pfx" in lines
    assert "secrets/" in lines
    assert "credentials/" in lines
    assert "private/" in lines
    assert ".local/" in lines

    # Mandatory data patterns
    assert "*.db" in lines
    assert "*.sqlite" in lines
    assert "*.csv" in lines
    assert "*.parquet" in lines


def test_env_example_exists_and_contains_only_placeholders():
    """Verify .env.example exists and does not contain real credentials."""
    env_example_path = REPO_ROOT / ".env.example"
    assert env_example_path.exists(), ".env.example must exist"

    content = env_example_path.read_text(encoding="utf-8")

    # Disallow common real key indicators
    assert "LIVE_TRADING_ENABLED=false" in content
    assert "ENVIRONMENT=development" in content

    # Ensure placeholders are clearly marked
    assert "your-anthropic-api-key-here" in content or "ANTHROPIC_API_KEY=" in content
    assert "your-zerodha-api-key-here" in content or "ZERODHA_API_KEY=" in content


def test_repository_files_do_not_contain_hardcoded_secrets():
    """Scan tracked repository files for private keys or leaked secret patterns.

    Allows safe placeholders like 'your-api-key-here', '<YOUR_API_KEY>', 'example-token'.
    """
    private_key_pattern = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")

    # Obvious high-entropy or API key prefixes that should never be in repo
    aws_pattern = re.compile(r"AKIA[0-9A-Z]{16}")
    anthropic_real_pattern = re.compile(r"sk-ant-[a-zA-Z0-9]{32,}")
    openai_real_pattern = re.compile(r"sk-[a-zA-Z0-9]{40,}")

    scanned_files = 0
    ignored_dirs = {".git", ".pytest_cache", ".ruff_cache", "__pycache__", ".venv", "venv"}

    for path in REPO_ROOT.rglob("*"):
        if path.is_file():
            if any(part in ignored_dirs for part in path.parts):
                continue

            # Read text files
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            scanned_files += 1
            rel_path = path.relative_to(REPO_ROOT)

            assert not private_key_pattern.search(content), f"Private key detected in {rel_path}"
            assert not aws_pattern.search(content), f"AWS access key pattern detected in {rel_path}"
            assert not anthropic_real_pattern.search(content), (
                f"Real Anthropic key pattern detected in {rel_path}"
            )
            assert not openai_real_pattern.search(content), (
                f"Real OpenAI key pattern detected in {rel_path}"
            )

    assert scanned_files > 0, "Security scanner must inspect repository files"


def test_sanitize_text_bearer_token():
    """Verify Bearer tokens are redacted."""
    raw = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.t-ID"
    sanitized = sanitize_text(raw)
    assert "Bearer ***REDACTED***" in sanitized
    assert "eyJhbGci" not in sanitized


def test_sanitize_text_database_url_password():
    """Verify passwords in connection strings are redacted."""
    raw = "Connecting to postgresql://postgres:SuperSecretPassword123@localhost:5432/quantpilot"
    sanitized = sanitize_text(raw)
    assert "postgresql://postgres:***REDACTED***@localhost:5432/quantpilot" in sanitized
    assert "SuperSecretPassword123" not in sanitized


def test_sanitize_text_custom_secrets():
    """Verify custom secrets passed from config are redacted from output."""
    raw = "Broker session established with token secret_access_token_val_99."
    sanitized = sanitize_text(raw, custom_secrets=["secret_access_token_val_99"])
    assert "secret_access_token_val_99" not in sanitized
    assert "***REDACTED***" in sanitized


def test_sanitize_dict_recursively():
    """Verify dictionary sanitization scrubs known sensitive keys."""
    data = {
        "status": "success",
        "api_key": "raw_sensitive_key",
        "nested": {
            "zerodha_access_token": "secret_token_123",
            "symbol": "INFY",
        },
    }
    sanitized = sanitize_dict(data)
    assert sanitized["api_key"] == "***REDACTED***"
    assert sanitized["nested"]["zerodha_access_token"] == "***REDACTED***"
    assert sanitized["nested"]["symbol"] == "INFY"


def test_security_log_filter():
    """Verify SecurityLogFilter redacts secrets in logging output."""
    record = logging.LogRecord(
        name="quantpilot.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Authenticated user with Bearer abcdef1234567890",
        args=(),
        exc_info=None,
    )
    log_filter = SecurityLogFilter()
    log_filter.filter(record)

    assert "Bearer ***REDACTED***" in record.msg
    assert "abcdef1234567890" not in record.msg
