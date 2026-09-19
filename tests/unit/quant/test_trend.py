"""Independent reference tests and edge cases for trend indicators."""

import math
from datetime import datetime, timedelta, timezone

from quantpilot.quant.models import IndicatorStatus
from quantpilot.quant.trend import (
    EMAIndicator,
    EMASlopeIndicator,
    PriceVsSMAIndicator,
    SMAIndicator,
    SMASlopeIndicator,
)
from tests.unit.quant.conftest import make_candle


def test_sma_independent_reference() -> None:
    """Independent hand-calculated reference test for SMA(5).

    Dataset: [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
    t=4: (10+11+12+13+14)/5 = 12.0
    t=5: (11+12+13+14+15)/5 = 13.0
    """
    prices = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = [
        make_candle(timestamp=start + timedelta(days=i), close=p) for i, p in enumerate(prices)
    ]

    sma = SMAIndicator(period=5)
    series = sma.calculate_series(candles)

    assert len(series.values) == 6
    # Insufficient data for first 4 bars
    for i in range(4):
        assert series.values[i].status == IndicatorStatus.INSUFFICIENT_DATA
        assert series.values[i].value is None

    # Expected reference values: direct finite tolerance 1e-9
    assert series.values[4].status == IndicatorStatus.VALID
    assert math.isclose(float(series.values[4].value), 12.0, abs_tol=1e-9)  # type: ignore[arg-type]

    assert series.values[5].status == IndicatorStatus.VALID
    assert math.isclose(float(series.values[5].value), 13.0, abs_tol=1e-9)  # type: ignore[arg-type]


def test_ema_independent_reference() -> None:
    """Independent hand-calculated reference test for EMA(3).

    alpha = 2 / (3 + 1) = 0.5
    Dataset: [10.0, 12.0, 14.0, 16.0]
    Seed at t=2: (10+12+14)/3 = 12.0
    t=3: 0.5*16.0 + (1-0.5)*12.0 = 14.0
    """
    prices = [10.0, 12.0, 14.0, 16.0]
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = [
        make_candle(timestamp=start + timedelta(days=i), close=p) for i, p in enumerate(prices)
    ]

    ema = EMAIndicator(period=3)
    series = ema.calculate_series(candles)

    assert len(series.values) == 4
    for i in range(2):
        assert series.values[i].status == IndicatorStatus.INSUFFICIENT_DATA
        assert series.values[i].value is None

    # Recursive smoother tolerance 1e-6
    assert series.values[2].status == IndicatorStatus.VALID
    assert math.isclose(float(series.values[2].value), 12.0, abs_tol=1e-6)  # type: ignore[arg-type]

    assert series.values[3].status == IndicatorStatus.VALID
    assert math.isclose(float(series.values[3].value), 14.0, abs_tol=1e-6)  # type: ignore[arg-type]


def test_price_vs_sma_reference_and_zero_division() -> None:
    prices = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = [
        make_candle(timestamp=start + timedelta(days=i), close=p) for i, p in enumerate(prices)
    ]

    p_vs_sma = PriceVsSMAIndicator(period=5)
    series = p_vs_sma.calculate_series(candles)

    # t=4: close=14.0, SMA=12.0 -> (14-12)/12 = 2/12 = 0.1666666667
    assert series.values[4].status == IndicatorStatus.VALID
    expected_ratio = (14.0 - 12.0) / 12.0
    assert math.isclose(float(series.values[4].value), expected_ratio, abs_tol=1e-9)  # type: ignore[arg-type]

    # Test SMA <= 0 handling
    from quantpilot.market_data.models import Candle, Timeframe

    zero_candles = [
        Candle.model_construct(
            symbol="RELIANCE",
            exchange="NSE",
            timeframe=Timeframe.D1,
            timestamp=start + timedelta(days=i),
            open=0.0,
            high=0.0,
            low=0.0,
            close=0.0,
            volume=100.0,
        )
        for i in range(5)
    ]
    zero_series = p_vs_sma.calculate_series(zero_candles)
    assert zero_series.values[4].status == IndicatorStatus.INVALID
    assert zero_series.values[4].value is None


def test_sma_slope_and_ema_slope_reference() -> None:
    prices = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = [
        make_candle(timestamp=start + timedelta(days=i), close=p) for i, p in enumerate(prices)
    ]

    # SMA slope with period 5, lag 1
    # SMA at t=4 is 12.0, SMA at t=5 is 13.0 -> slope = (13.0 - 12.0)/1 = 1.0
    sma_slope = SMASlopeIndicator(period=5, lag=1)
    s_series = sma_slope.calculate_series(candles)
    assert s_series.values[4].status == IndicatorStatus.INSUFFICIENT_DATA
    assert s_series.values[5].status == IndicatorStatus.VALID
    assert math.isclose(float(s_series.values[5].value), 1.0, abs_tol=1e-9)  # type: ignore[arg-type]

    # EMA slope with period 3, lag 1
    # EMA at t=2 is 12.0, EMA at t=3 is 14.0 on prices [10, 12, 14, 16]
    ema_prices = [10.0, 12.0, 14.0, 16.0]
    ema_candles = [
        make_candle(timestamp=start + timedelta(days=i), close=p) for i, p in enumerate(ema_prices)
    ]
    ema_slope = EMASlopeIndicator(period=3, lag=1)
    e_series = ema_slope.calculate_series(ema_candles)
    assert e_series.values[3].status == IndicatorStatus.VALID
    assert math.isclose(float(e_series.values[3].value), 2.0, abs_tol=1e-6)  # type: ignore[arg-type]
