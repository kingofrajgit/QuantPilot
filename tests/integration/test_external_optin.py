"""External integration tests demonstration.

All external tests must be explicitly marked with both:
@pytest.mark.external
@pytest.mark.integration

MANDATORY RULES:
1. They must check for actual environment variables.
2. If credentials are not present in the environment, the test must be SKIPPED via pytest.skip().
3. Never FAIL due to missing external credentials in CI/local runs.
4. Never fall back to hardcoded or default mock credentials as if they were real.
5. Never place real live orders.
"""

import os

import pytest


@pytest.mark.external
@pytest.mark.integration
def test_optin_zerodha_connection():
    """Demonstrates safe opt-in behavior for external Zerodha integration tests."""
    api_key = os.getenv("ZERODHA_API_KEY")
    api_secret = os.getenv("ZERODHA_API_SECRET")
    access_token = os.getenv("ZERODHA_ACCESS_TOKEN")

    if not api_key or not api_secret or not access_token:
        pytest.skip(
            "External Zerodha credentials missing. Test skipped cleanly. "
            "Never fallback to hardcoded secrets or fail on missing credentials."
        )

    # Note: Even when credentials are provided in a future phase, tests must never place live orders
    assert api_key is not None


@pytest.mark.external
@pytest.mark.integration
def test_optin_anthropic_connection():
    """Demonstrates safe opt-in behavior for external Anthropic Claude integration tests."""
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        pytest.skip(
            "External ANTHROPIC_API_KEY missing. Test skipped cleanly. "
            "Never fallback to hardcoded secrets or fail on missing credentials."
        )

    assert api_key is not None
