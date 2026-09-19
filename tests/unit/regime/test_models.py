"""Tests for regime domain models, enums, immutability, and serialization."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from quantpilot.market_data.models import Timeframe
from quantpilot.regime.models import (
    CompositeRegime,
    DimensionEvidence,
    MarketRegimeContext,
    MarketStructure,
    MomentumRegime,
    RegimeContextSeries,
    RegimeProvenance,
    TrendRegime,
    VolatilityRegime,
    VolumeRegime,
)


def test_enum_members_and_values() -> None:
    """Verify all domain enums have exact canonical members and values."""
    assert TrendRegime.BULLISH.value == "BULLISH"
    assert TrendRegime.BEARISH.value == "BEARISH"
    assert TrendRegime.SIDEWAYS.value == "SIDEWAYS"
    assert TrendRegime.INSUFFICIENT_DATA.value == "INSUFFICIENT_DATA"

    assert MomentumRegime.POSITIVE.value == "POSITIVE"
    assert MomentumRegime.NEGATIVE.value == "NEGATIVE"
    assert MomentumRegime.NEUTRAL.value == "NEUTRAL"
    assert MomentumRegime.INSUFFICIENT_DATA.value == "INSUFFICIENT_DATA"

    assert VolatilityRegime.LOW.value == "LOW"
    assert VolatilityRegime.NORMAL.value == "NORMAL"
    assert VolatilityRegime.HIGH.value == "HIGH"
    assert VolatilityRegime.INSUFFICIENT_DATA.value == "INSUFFICIENT_DATA"

    assert VolumeRegime.HIGH_VOLUME.value == "HIGH_VOLUME"
    assert VolumeRegime.NORMAL_VOLUME.value == "NORMAL_VOLUME"
    assert VolumeRegime.LOW_VOLUME.value == "LOW_VOLUME"
    assert VolumeRegime.ACCUMULATION.value == "ACCUMULATION"
    assert VolumeRegime.DISTRIBUTION.value == "DISTRIBUTION"
    assert VolumeRegime.INSUFFICIENT_DATA.value == "INSUFFICIENT_DATA"

    assert MarketStructure.BREAKOUT.value == "BREAKOUT"
    assert MarketStructure.BREAKDOWN.value == "BREAKDOWN"
    assert MarketStructure.CONSOLIDATION.value == "CONSOLIDATION"
    assert MarketStructure.TRENDING.value == "TRENDING"
    assert MarketStructure.RANGING.value == "RANGING"
    assert MarketStructure.INSUFFICIENT_DATA.value == "INSUFFICIENT_DATA"

    assert CompositeRegime.BULLISH_TRENDING_EXPANSION.value == "BULLISH_TRENDING_EXPANSION"
    assert CompositeRegime.BEARISH_TRENDING_EXPANSION.value == "BEARISH_TRENDING_EXPANSION"
    assert CompositeRegime.BULLISH_CONSOLIDATION.value == "BULLISH_CONSOLIDATION"
    assert CompositeRegime.BEARISH_CONSOLIDATION.value == "BEARISH_CONSOLIDATION"
    assert CompositeRegime.SIDEWAYS_RANGE.value == "SIDEWAYS_RANGE"
    assert CompositeRegime.COMPRESSION.value == "COMPRESSION"
    assert CompositeRegime.VOLATILE_UNSTRUCTURED.value == "VOLATILE_UNSTRUCTURED"
    assert CompositeRegime.DIVERGENT.value == "DIVERGENT"
    assert CompositeRegime.INSUFFICIENT_DATA.value == "INSUFFICIENT_DATA"
    assert CompositeRegime.UNKNOWN.value == "UNKNOWN"


def test_models_frozen_immutability() -> None:
    """Verify that domain models are frozen and cannot be mutated."""
    prov = RegimeProvenance(
        engine_version="1.0.0",
        parameters={"threshold": 1.0},
        indicators_used=["sma"],
        source_window_start=datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc),
        source_window_end=datetime(2026, 1, 1, 15, 30, tzinfo=timezone.utc),
        candles_evaluated=25,
    )
    with pytest.raises(ValidationError):
        prov.engine_version = "2.0.0"  # type: ignore[misc]

    ev = DimensionEvidence(
        dimension="trend",
        state="BULLISH",
        contributing_metrics={"slope": 0.5},
        rationale="test rationale",
    )
    with pytest.raises(ValidationError):
        ev.state = "BEARISH"  # type: ignore[misc]

    context = MarketRegimeContext(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe=Timeframe.M1,
        timestamp=datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc),
        composite_regime=CompositeRegime.BULLISH_TRENDING_EXPANSION,
        trend=TrendRegime.BULLISH,
        momentum=MomentumRegime.POSITIVE,
        volatility=VolatilityRegime.NORMAL,
        volume=VolumeRegime.NORMAL_VOLUME,
        structure=MarketStructure.TRENDING,
        evidence={"trend": ev},
        provenance=prov,
    )
    with pytest.raises(ValidationError):
        context.composite_regime = CompositeRegime.UNKNOWN  # type: ignore[misc]


def test_model_serialization_round_trip() -> None:
    """Verify JSON serialization and deserialization round-trip preserves equality."""
    ts = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    prov = RegimeProvenance(
        engine_version="1.0.0",
        parameters={"test": 123},
        indicators_used=["sma", "rsi"],
        source_window_start=ts,
        source_window_end=ts,
        candles_evaluated=10,
    )
    ev = DimensionEvidence(
        dimension="momentum",
        state="POSITIVE",
        contributing_metrics={"rsi": 60.0},
        rationale="Strong momentum",
    )
    ctx = MarketRegimeContext(
        symbol="INFY",
        exchange="NSE",
        timeframe=Timeframe.D1,
        timestamp=ts,
        composite_regime=CompositeRegime.BULLISH_TRENDING_EXPANSION,
        trend=TrendRegime.BULLISH,
        momentum=MomentumRegime.POSITIVE,
        volatility=VolatilityRegime.NORMAL,
        volume=VolumeRegime.ACCUMULATION,
        structure=MarketStructure.BREAKOUT,
        evidence={"momentum": ev},
        provenance=prov,
    )
    series = RegimeContextSeries(
        symbol="INFY",
        exchange="NSE",
        timeframe=Timeframe.D1,
        values=[ctx],
    )

    json_str = series.model_dump_json()
    reloaded = RegimeContextSeries.model_validate_json(json_str)
    assert reloaded == series
    assert reloaded.values[0].composite_regime == CompositeRegime.BULLISH_TRENDING_EXPANSION
    assert reloaded.values[0].volume == VolumeRegime.ACCUMULATION
