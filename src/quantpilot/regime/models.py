"""Domain models, enums, evidence, and provenance representations for market regimes."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from quantpilot.market_data.models import Timeframe


class TrendRegime(str, Enum):
    """Directional trend classification."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    SIDEWAYS = "SIDEWAYS"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class MomentumRegime(str, Enum):
    """Velocity and momentum agreement."""

    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class VolatilityRegime(str, Enum):
    """Volatility dispersion state."""

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class VolumeRegime(str, Enum):
    """Independent volume context and participation behavior."""

    HIGH_VOLUME = "HIGH_VOLUME"
    NORMAL_VOLUME = "NORMAL_VOLUME"
    LOW_VOLUME = "LOW_VOLUME"
    ACCUMULATION = "ACCUMULATION"
    DISTRIBUTION = "DISTRIBUTION"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class MarketStructure(str, Enum):
    """Geometric price structure state."""

    BREAKOUT = "BREAKOUT"
    BREAKDOWN = "BREAKDOWN"
    CONSOLIDATION = "CONSOLIDATION"
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class CompositeRegime(str, Enum):
    """Raw point-in-time synthesized market regime."""

    BULLISH_TRENDING_EXPANSION = "BULLISH_TRENDING_EXPANSION"
    BEARISH_TRENDING_EXPANSION = "BEARISH_TRENDING_EXPANSION"
    BULLISH_CONSOLIDATION = "BULLISH_CONSOLIDATION"
    BEARISH_CONSOLIDATION = "BEARISH_CONSOLIDATION"
    SIDEWAYS_RANGE = "SIDEWAYS_RANGE"
    COMPRESSION = "COMPRESSION"
    VOLATILE_UNSTRUCTURED = "VOLATILE_UNSTRUCTURED"
    DIVERGENT = "DIVERGENT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    UNKNOWN = "UNKNOWN"


class RegimeProvenance(BaseModel):
    """Audit trail detailing parameters and indicator versions used in classification."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    engine_version: str = Field(default="1.0.0")
    parameters: dict[str, Any] = Field(default_factory=dict)
    indicators_used: list[str] = Field(default_factory=list)
    source_window_start: datetime | None = None
    source_window_end: datetime | None = None
    candles_evaluated: int = Field(..., ge=0)


class DimensionEvidence(BaseModel):
    """Underlying quantitative values supporting a dimension classification."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    dimension: str
    state: str
    contributing_metrics: dict[str, float | str | None] = Field(default_factory=dict)
    rationale: str


class MarketRegimeContext(BaseModel):
    """Point-in-time stateless regime evaluation for a single candle at timestamp T."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    symbol: str
    exchange: str
    timeframe: Timeframe
    timestamp: datetime  # UTC

    composite_regime: CompositeRegime  # Raw deterministic classification at T
    trend: TrendRegime
    momentum: MomentumRegime
    volatility: VolatilityRegime
    volume: VolumeRegime  # Independent context dimension
    structure: MarketStructure

    evidence: dict[str, DimensionEvidence] = Field(default_factory=dict)
    provenance: RegimeProvenance


class RegimeContextSeries(BaseModel):
    """Chronological series of stateless regime evaluations."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    symbol: str
    exchange: str
    timeframe: Timeframe
    values: list[MarketRegimeContext]
