"""Canonical market data models for QuantPilot.

All models are strictly typed using Pydantic v2 and enforce timezone awareness,
positive price constraints, valid volume metrics, and provider-independent representations.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Timeframe(str, Enum):
    """Supported standard candle timeframes."""

    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


class MarketSession(str, Enum):
    """Trading session lifecycle states."""

    PRE_MARKET = "PRE_MARKET"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    POST_MARKET = "POST_MARKET"
    UNKNOWN = "UNKNOWN"


class DataQualityStatus(str, Enum):
    """Status outcomes for market data quality audits."""

    VALID = "VALID"
    INVALID = "INVALID"
    WARNING = "WARNING"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    STALE = "STALE"


def _validate_and_normalize_timestamp(v: datetime) -> datetime:
    """Ensure timestamp is timezone-aware and normalize to UTC.

    Rejects naive datetimes to eliminate ambiguity.
    """
    if not isinstance(v, datetime):
        raise ValueError("Timestamp must be a datetime instance")
    if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
        raise ValueError("Naive datetimes are rejected. Timestamps must be timezone-aware.")
    return v.astimezone(timezone.utc)


class Instrument(BaseModel):
    """Provider-independent instrument definition."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    symbol: str = Field(..., min_length=1, description="Ticker or trading symbol")
    exchange: str = Field(..., min_length=1, description="Exchange code, e.g., NSE, BSE")
    instrument_token: str | int | None = Field(
        default=None, description="Optional provider identifier"
    )
    lot_size: int | None = Field(default=None, gt=0, description="Trading lot size if applicable")
    tick_size: float | None = Field(
        default=None, gt=0.0, description="Minimum price movement increment"
    )
    is_active: bool = Field(
        default=True, description="Whether the instrument is currently tradable"
    )

    @field_validator("symbol", "exchange")
    @classmethod
    def check_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field cannot be empty or whitespace only")
        return stripped


class Candle(BaseModel):
    """Canonical OHLCV candle model."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    symbol: str = Field(..., min_length=1)
    exchange: str = Field(..., min_length=1)
    timestamp: datetime = Field(..., description="Candle open or bar timestamp, timezone-aware")
    timeframe: Timeframe = Field(...)
    open: float = Field(..., gt=0.0, description="Opening price, strictly positive")
    high: float = Field(..., gt=0.0, description="High price, strictly positive")
    low: float = Field(..., gt=0.0, description="Low price, strictly positive")
    close: float = Field(..., gt=0.0, description="Closing price, strictly positive")
    volume: float = Field(..., ge=0.0, description="Traded volume, non-negative")

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_tz(cls, v: datetime) -> datetime:
        return _validate_and_normalize_timestamp(v)

    @field_validator("symbol", "exchange")
    @classmethod
    def check_identity(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Identifier cannot be empty")
        return stripped

    @model_validator(mode="after")
    def validate_ohlc_relationships(self) -> "Candle":
        """Validate logical OHLC price bounds."""
        if self.high < self.open:
            raise ValueError(f"High ({self.high}) cannot be less than Open ({self.open})")
        if self.high < self.close:
            raise ValueError(f"High ({self.high}) cannot be less than Close ({self.close})")
        if self.high < self.low:
            raise ValueError(f"High ({self.high}) cannot be less than Low ({self.low})")
        if self.low > self.open:
            raise ValueError(f"Low ({self.low}) cannot be greater than Open ({self.open})")
        if self.low > self.close:
            raise ValueError(f"Low ({self.low}) cannot be greater than Close ({self.close})")
        return self


class Quote(BaseModel):
    """Provider-independent market quote / Level 1 snapshot."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    symbol: str = Field(..., min_length=1)
    exchange: str = Field(..., min_length=1)
    timestamp: datetime = Field(...)
    last_price: float = Field(..., gt=0.0, description="Last traded price, strictly positive")
    bid: float | None = Field(default=None, gt=0.0, description="Best bid price")
    ask: float | None = Field(default=None, gt=0.0, description="Best ask price")
    bid_qty: float | None = Field(default=None, ge=0.0, description="Best bid quantity")
    ask_qty: float | None = Field(default=None, ge=0.0, description="Best ask quantity")
    volume: float = Field(default=0.0, ge=0.0, description="Day cumulative volume")

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_tz(cls, v: datetime) -> datetime:
        return _validate_and_normalize_timestamp(v)

    @field_validator("symbol", "exchange")
    @classmethod
    def check_identity(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Identifier cannot be empty")
        return stripped

    @model_validator(mode="after")
    def validate_bid_ask_spread(self) -> "Quote":
        """Validate that bid <= ask when both quotes are available."""
        if self.bid is not None and self.ask is not None:
            if self.bid > self.ask:
                raise ValueError(f"Bid ({self.bid}) cannot exceed Ask ({self.ask})")
        return self


class Tick(BaseModel):
    """Canonical normalized market tick."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    symbol: str = Field(..., min_length=1)
    exchange: str = Field(..., min_length=1)
    timestamp: datetime = Field(...)
    last_price: float = Field(..., gt=0.0, description="Last trade price, strictly positive")
    last_quantity: float = Field(..., ge=0.0, description="Last trade quantity")
    total_volume: float = Field(..., ge=0.0, description="Total cumulative volume")

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_tz(cls, v: datetime) -> datetime:
        return _validate_and_normalize_timestamp(v)

    @field_validator("symbol", "exchange")
    @classmethod
    def check_identity(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Identifier cannot be empty")
        return stripped


class DataQualityReport(BaseModel):
    """Structured, serializable report summarizing dataset quality validation."""

    model_config = ConfigDict(frozen=True)

    status: DataQualityStatus
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checks_run: list[str] = Field(default_factory=list)
    validated_at: Annotated[
        datetime,
        Field(default_factory=lambda: datetime.now(timezone.utc)),
    ]
    record_count: int = Field(default=0, ge=0)

    @field_validator("validated_at", mode="before")
    @classmethod
    def validate_tz(cls, v: datetime) -> datetime:
        return _validate_and_normalize_timestamp(v)
