"""Domain models and provenance representations for quantitative evidence and indicators."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from quantpilot.market_data.models import Timeframe


class IndicatorStatus(str, Enum):
    """Execution status of an indicator point."""

    VALID = "VALID"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    INVALID = "INVALID"


class IndicatorProvenance(BaseModel):
    """Immutable, deterministic audit record of exact parameters, version, and input slice.

    Contains strictly deterministic information. Zero runtime timestamps or non-reproducible state.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    indicator_name: str = Field(..., min_length=1)
    indicator_version: str = Field(default="1.0.0")
    parameters: dict[str, Any] = Field(default_factory=dict)
    lookback_period: int = Field(..., ge=1)
    source_window_start: datetime | None = Field(
        default=None,
        description="UTC timestamp of the earliest candle in the calculation window",
    )
    source_window_end: datetime | None = Field(
        default=None,
        description="UTC timestamp of the terminal candle in the calculation window",
    )
    candles_analyzed: int = Field(..., ge=0)


class IndicatorValue(BaseModel):
    """Point-in-time quantitative evidence emitted for a specific candle."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    symbol: str = Field(..., min_length=1)
    exchange: str = Field(..., min_length=1)
    timeframe: Timeframe
    timestamp: datetime = Field(..., description="Timestamp of the candle evaluated (UTC)")
    value: float | dict[str, float] | None = Field(
        default=None,
        description="Scalar float value or component dictionary for multi-output indicators",
    )
    status: IndicatorStatus = Field(...)
    provenance: IndicatorProvenance


class IndicatorSeries(BaseModel):
    """Chronological series of indicator evaluations for a single asset/timeframe."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    symbol: str
    exchange: str
    timeframe: Timeframe
    indicator_name: str
    values: list[IndicatorValue]


class QuantRunContext(BaseModel):
    """Optional execution-level metadata decoupled from deterministic indicator values.

    NEVER embedded within IndicatorValue, IndicatorSeries, or IndicatorProvenance.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    run_id: str = Field(..., min_length=1)
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    execution_duration_ms: float = Field(..., ge=0.0)
    indicators_executed: list[str] = Field(default_factory=list)
