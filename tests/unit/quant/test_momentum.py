"""Independent reference tests and edge cases for momentum indicators."""

import math
from datetime import datetime, timedelta, timezone

from quantpilot.quant.models import IndicatorStatus
from quantpilot.quant.momentum import MACDIndicator, ROCIndicator, RSIIndicator
from tests.unit.quant.conftest import make_candle


def test_roc_independent_reference() -> None:
    """Independent hand-calculated reference test for ROC(3).

    Dataset: [100.0, 105.0, 110.0, 120.0]
    t=3: (120 - 100)/100 * 100 = 20.0%
    """
    prices = [100.0, 105.0, 110.0, 120.0]
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = [
        make_candle(timestamp=start + timedelta(days=i), close=p) for i, p in enumerate(prices)
    ]

    roc = ROCIndicator(period=3)
    series = roc.calculate_series(candles)

    assert series.values[0].status == IndicatorStatus.INSUFFICIENT_DATA
    assert series.values[1].status == IndicatorStatus.INSUFFICIENT_DATA
    assert series.values[2].status == IndicatorStatus.INSUFFICIENT_DATA

    assert series.values[3].status == IndicatorStatus.VALID
    assert math.isclose(float(series.values[3].value), 20.0, abs_tol=1e-9)  # type: ignore[arg-type]


def test_rsi_independent_reference() -> None:
    """Independent hand-calculated reference test for RSI(3) using Wilder's smoothing.

    Dataset: [44.34, 44.09, 44.15, 43.61, 44.33]
    Changes:
    i=1: -0.25 (G=0.00, L=0.25)
    i=2: +0.06 (G=0.06, L=0.00)
    i=3: -0.54 (G=0.00, L=0.54)
    AvgGain_3 = (0.00 + 0.06 + 0.00) / 3 = 0.02
    AvgLoss_3 = (0.25 + 0.00 + 0.54) / 3 = 0.79 / 3
    RS_3 = 0.02 / (0.79 / 3) = 0.06 / 0.79
    RSI_3 = 100 - (100 / (1 + 0.06/0.79)) = 6 / 0.85 = 7.058823529411768

    i=4: +0.72 (G=0.72, L=0.00)
    AvgGain_4 = (0.02 * 2 + 0.72) / 3 = 0.76 / 3
    AvgLoss_4 = (0.79 / 3 * 2 + 0.00) / 3 = 1.58 / 9
    RS_4 = (0.76 / 3) / (1.58 / 9) = 2.28 / 1.58
    RSI_4 = 100 - (100 / (1 + 2.28/1.58)) = 2.28 / 3.86 * 100 = 59.06735751295337
    """
    prices = [44.34, 44.09, 44.15, 43.61, 44.33]
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = [
        make_candle(timestamp=start + timedelta(days=i), close=p) for i, p in enumerate(prices)
    ]

    rsi = RSIIndicator(period=3)
    series = rsi.calculate_series(candles)

    # Initial bars insufficient
    assert series.values[0].status == IndicatorStatus.INSUFFICIENT_DATA
    assert series.values[1].status == IndicatorStatus.INSUFFICIENT_DATA
    assert series.values[2].status == IndicatorStatus.INSUFFICIENT_DATA

    # Bar 3 verification
    expected_rsi_3 = 100.0 - (100.0 / (1.0 + (0.06 / 0.79)))
    assert series.values[3].status == IndicatorStatus.VALID
    assert math.isclose(float(series.values[3].value), expected_rsi_3, abs_tol=1e-6)  # type: ignore[arg-type]

    # Bar 4 verification
    expected_rsi_4 = 100.0 - (100.0 / (1.0 + (2.28 / 1.58)))
    assert series.values[4].status == IndicatorStatus.VALID
    assert math.isclose(float(series.values[4].value), expected_rsi_4, abs_tol=1e-6)  # type: ignore[arg-type]


def test_rsi_bounds_and_flat_price() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    # Monotonically increasing prices -> RSI must be 100.0
    up_prices = [10.0, 11.0, 12.0, 13.0, 14.0]
    up_candles = [
        make_candle(timestamp=start + timedelta(days=i), close=p) for i, p in enumerate(up_prices)
    ]
    rsi_up = RSIIndicator(period=3)
    up_series = rsi_up.calculate_series(up_candles)
    assert up_series.values[3].status == IndicatorStatus.VALID
    assert math.isclose(float(up_series.values[3].value), 100.0, abs_tol=1e-9)  # type: ignore[arg-type]

    # Completely flat prices -> RSI must be 50.0
    flat_prices = [10.0, 10.0, 10.0, 10.0, 10.0]
    flat_candles = [
        make_candle(timestamp=start + timedelta(days=i), close=p) for i, p in enumerate(flat_prices)
    ]
    flat_series = rsi_up.calculate_series(flat_candles)
    assert flat_series.values[3].status == IndicatorStatus.VALID
    assert math.isclose(float(flat_series.values[3].value), 50.0, abs_tol=1e-9)  # type: ignore[arg-type]


def test_macd_independent_reference() -> None:
    """Test MACD calculation with fast=2, slow=4, signal=2."""
    # Min observations = slow (4) + signal (2) - 1 = 5 candles
    prices = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0]
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = [
        make_candle(timestamp=start + timedelta(days=i), close=p) for i, p in enumerate(prices)
    ]

    macd = MACDIndicator(fast_period=2, slow_period=4, signal_period=2)
    series = macd.calculate_series(candles)

    assert len(series.values) == 6
    # Insufficient for bars 0..3
    for i in range(4):
        assert series.values[i].status == IndicatorStatus.INSUFFICIENT_DATA
        assert series.values[i].value is None

    # Bar 4 is minimum observations (5th candle)
    assert series.values[4].status == IndicatorStatus.VALID
    val4 = series.values[4].value
    assert isinstance(val4, dict)
    assert "macd" in val4 and "signal" in val4 and "histogram" in val4
    assert math.isclose(val4["histogram"], val4["macd"] - val4["signal"], abs_tol=1e-9)
