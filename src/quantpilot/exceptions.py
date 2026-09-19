"""Centralized exception hierarchy for QuantPilot."""


class QuantPilotError(Exception):
    """Base exception for all QuantPilot errors."""

    pass


class ConfigurationError(QuantPilotError):
    """Raised when configuration is invalid, missing, or improperly structured."""

    pass


class SecurityError(QuantPilotError):
    """Raised when a security boundary or unauthorized live trading violation occurs."""

    pass


class BrokerError(QuantPilotError):
    """Base exception for broker-related errors."""

    pass


class OrderError(BrokerError):
    """Raised when an order cannot be placed, validated, or executed."""

    pass
