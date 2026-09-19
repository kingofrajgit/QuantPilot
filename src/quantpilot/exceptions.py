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


class DataStorageError(QuantPilotError):
    """Base exception for market data persistence and retrieval errors."""

    pass


class DataValidationError(DataStorageError):
    """Raised when a market dataset fails data quality validation before persistence."""

    pass


class DataConflictError(DataStorageError):
    """Raised when incoming market data conflicts with existing records for the same key."""

    pass
