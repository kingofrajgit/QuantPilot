"""Unit tests for quant domain models, immutability, and deterministic serialization."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from quantpilot.market_data.models import Timeframe
from quantpilot.quant.models import (
    IndicatorProvenance,
    IndicatorSeries,
    IndicatorStatus,
    IndicatorValue,
    QuantRunContext,
)


def test_indicator_provenance_strictly_deterministic() -> None:
    """Verify IndicatorProvenance does not contain non-deterministic runtime timestamps."""
    field_names = IndicatorProvenance.model_fields.keys()
    assert "calculation_timestamp" not in field_names
    assert "runtime_timestamp" not in field_names
    assert "execution_duration_ms" not in field_names

    prov = IndicatorProvenance(
        indicator_name="sma",
        indicator_version="1.0.0",
        parameters={"period": 20},
        lookback_period=20,
        source_window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source_window_end=datetime(2026, 1, 20, tzinfo=timezone.utc),
        candles_analyzed=20,
    )
    assert prov.indicator_name == "sma"
    assert prov.candles_analyzed == 20


def test_indicator_models_immutability() -> None:
    """Verify IndicatorProvenance, IndicatorValue, and IndicatorSeries are frozen."""
    prov = IndicatorProvenance(
        indicator_name="rsi",
        parameters={"period": 14},
        lookback_period=14,
        candles_analyzed=15,
    )
    with pytest.raises(ValidationError):
        prov.indicator_name = "ema"  # type: ignore[misc]

    val = IndicatorValue(
        symbol="INFY",
        exchange="NSE",
        timeframe=Timeframe.D1,
        timestamp=datetime(2026, 1, 15, tzinfo=timezone.utc),
        value=55.4,
        status=IndicatorStatus.VALID,
        provenance=prov,
    )
    with pytest.raises(ValidationError):
        val.value = 60.0  # type: ignore[misc]

    series = IndicatorSeries(
        symbol="INFY",
        exchange="NSE",
        timeframe=Timeframe.D1,
        indicator_name="rsi",
        values=[val],
    )
    with pytest.raises(ValidationError):
        series.indicator_name = "sma"  # type: ignore[misc]


def test_quant_run_context_isolation() -> None:
    """Verify QuantRunContext is completely decoupled from indicator models."""
    ctx = QuantRunContext(
        run_id="run-12345",
        execution_duration_ms=4.2,
        indicators_executed=["sma", "rsi"],
    )
    assert ctx.run_id == "run-12345"
    assert ctx.execution_duration_ms == 4.2
    assert "sma" in ctx.indicators_executed

    # Ensure QuantRunContext is NOT part of IndicatorValue or IndicatorProvenance schemas
    assert "context" not in IndicatorValue.model_fields
    assert "context" not in IndicatorProvenance.model_fields
    assert "context" not in IndicatorSeries.model_fields


def test_deterministic_serialization_equality() -> None:
    """Verify same candles + parameters + implementation produces bit-for-bit identical JSON."""
    prov1 = IndicatorProvenance(
        indicator_name="sma",
        parameters={"period": 20},
        lookback_period=20,
        source_window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source_window_end=datetime(2026, 1, 20, tzinfo=timezone.utc),
        candles_analyzed=20,
    )
    val1 = IndicatorValue(
        symbol="TCS",
        exchange="NSE",
        timeframe=Timeframe.D1,
        timestamp=datetime(2026, 1, 20, tzinfo=timezone.utc),
        value=3500.25,
        status=IndicatorStatus.VALID,
        provenance=prov1,
    )
    series1 = IndicatorSeries(
        symbol="TCS",
        exchange="NSE",
        timeframe=Timeframe.D1,
        indicator_name="sma",
        values=[val1],
    )

    prov2 = IndicatorProvenance(
        indicator_name="sma",
        parameters={"period": 20},
        lookback_period=20,
        source_window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source_window_end=datetime(2026, 1, 20, tzinfo=timezone.utc),
        candles_analyzed=20,
    )
    val2 = IndicatorValue(
        symbol="TCS",
        exchange="NSE",
        timeframe=Timeframe.D1,
        timestamp=datetime(2026, 1, 20, tzinfo=timezone.utc),
        value=3500.25,
        status=IndicatorStatus.VALID,
        provenance=prov2,
    )
    series2 = IndicatorSeries(
        symbol="TCS",
        exchange="NSE",
        timeframe=Timeframe.D1,
        indicator_name="sma",
        values=[val2],
    )

    # Bit-for-bit identical JSON serialization
    json1 = series1.model_dump_json()
    json2 = series2.model_dump_json()
    assert json1 == json2
