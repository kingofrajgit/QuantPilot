"""Unit tests for Relative Strength, timestamp alignment, and future-benchmark isolation."""

import math
from datetime import datetime, timedelta, timezone

import pytest

from quantpilot.market_data.models import Timeframe
from quantpilot.quant.models import IndicatorStatus
from quantpilot.quant.relative_strength import RelativeStrengthIndicator
from tests.unit.quant.conftest import make_candle


def test_relative_strength_exact_match_and_reference() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # Asset prices: 100, 110, 120 -> return over 2 bars = (120 - 100) / 100 = 0.20 (+20%)
    # Bench prices: 200, 210, 220 -> return over 2 bars = (220 - 200) / 200 = 0.10 (+10%)
    # Excess return = (0.20 - 0.10) * 100 = 10.0%
    # Outperformance ratio = (1.20 / 1.10) - 1.0 = (12/11) - 1.0 = 1/11 ≈ 0.09090909
    asset_candles = [
        make_candle(timestamp=start, close=100.0, symbol="INFY"),
        make_candle(timestamp=start + timedelta(days=1), close=110.0, symbol="INFY"),
        make_candle(timestamp=start + timedelta(days=2), close=120.0, symbol="INFY"),
    ]
    bench_candles = [
        make_candle(timestamp=start, close=200.0, symbol="NIFTY50"),
        make_candle(timestamp=start + timedelta(days=1), close=210.0, symbol="NIFTY50"),
        make_candle(timestamp=start + timedelta(days=2), close=220.0, symbol="NIFTY50"),
    ]

    rs = RelativeStrengthIndicator(period=2, benchmark_candles=bench_candles)
    series = rs.calculate_series(asset_candles)

    assert series.values[0].status == IndicatorStatus.INSUFFICIENT_DATA
    assert series.values[1].status == IndicatorStatus.INSUFFICIENT_DATA

    assert series.values[2].status == IndicatorStatus.VALID
    val = series.values[2].value
    assert isinstance(val, dict)
    assert math.isclose(val["excess_return"], 10.0, abs_tol=1e-9)
    assert math.isclose(val["outperformance_ratio"], (1.20 / 1.10) - 1.0, abs_tol=1e-9)


def test_relative_strength_missing_benchmark_candle() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    asset_candles = [
        make_candle(timestamp=start, close=100.0),
        make_candle(timestamp=start + timedelta(days=1), close=110.0),
        make_candle(timestamp=start + timedelta(days=2), close=120.0),
    ]
    # Benchmark is missing candle at day 2
    bench_candles = [
        make_candle(timestamp=start, close=200.0),
        make_candle(timestamp=start + timedelta(days=1), close=210.0),
    ]

    rs = RelativeStrengthIndicator(period=2, benchmark_candles=bench_candles)
    series = rs.calculate_series(asset_candles)

    # Missing benchmark timestamp at day 2 -> INSUFFICIENT_DATA, value = None
    assert series.values[2].status == IndicatorStatus.INSUFFICIENT_DATA
    assert series.values[2].value is None


def test_relative_strength_future_benchmark_isolation() -> None:
    """Verify that adding future benchmark candles does not alter calculation at or before T."""
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    asset_candles = [
        make_candle(timestamp=start, close=100.0),
        make_candle(timestamp=start + timedelta(days=1), close=110.0),
        make_candle(timestamp=start + timedelta(days=2), close=120.0),
    ]
    # Baseline benchmark up to T (day 2)
    bench_base = [
        make_candle(timestamp=start, close=200.0),
        make_candle(timestamp=start + timedelta(days=1), close=210.0),
        make_candle(timestamp=start + timedelta(days=2), close=220.0),
    ]
    rs_base = RelativeStrengthIndicator(period=2, benchmark_candles=bench_base)
    series_base = rs_base.calculate_series(asset_candles)
    base_val = series_base.values[2]

    # Extended benchmark with future candles > T (with massive price spikes)
    bench_extended = list(bench_base) + [
        make_candle(timestamp=start + timedelta(days=3), close=9999.0),
        make_candle(timestamp=start + timedelta(days=4), close=1.0),
    ]
    rs_extended = RelativeStrengthIndicator(period=2, benchmark_candles=bench_extended)
    series_extended = rs_extended.calculate_series(asset_candles)
    extended_val = series_extended.values[2]

    assert extended_val.status == base_val.status
    assert extended_val.value == base_val.value


def test_relative_strength_mismatched_timeframe_rejected() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    asset = [make_candle(timestamp=start, close=100.0, timeframe=Timeframe.D1)]
    bench = [make_candle(timestamp=start, close=200.0, timeframe=Timeframe.M15)]

    rs = RelativeStrengthIndicator(period=1, benchmark_candles=bench)
    with pytest.raises(ValueError, match="Timeframe mismatch"):
        rs.calculate_series(asset)


def test_relative_strength_unsorted_benchmark_rejected() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    asset = [
        make_candle(timestamp=start, close=100.0),
        make_candle(timestamp=start + timedelta(days=1), close=110.0),
    ]
    # Benchmark unsorted
    bench = [
        make_candle(timestamp=start + timedelta(days=1), close=210.0),
        make_candle(timestamp=start, close=200.0),
    ]

    rs = RelativeStrengthIndicator(period=1, benchmark_candles=bench)
    with pytest.raises(ValueError, match="strictly ascending"):
        rs.calculate_series(asset)
