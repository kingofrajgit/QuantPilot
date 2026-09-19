"""Independent reference tests and precedence safety for volatility indicators."""

import math
from datetime import datetime, timedelta, timezone

from quantpilot.quant.models import IndicatorStatus
from quantpilot.quant.volatility import (
    ATRIndicator,
    BollingerBandsIndicator,
    NATRIndicator,
    RollingStdDevIndicator,
    TrueRangeIndicator,
)
from tests.unit.quant.conftest import make_candle


def test_true_range_reference_and_gap_cases() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # Candle 0: H=105, L=95, C=100 -> TR = 10.0
    # Candle 1 (gap up): H=120, L=115, C=118 -> max(120-115=5, |120-100|=20, |115-100|=15) = 20.0
    # Candle 2 (gap down): H=90, L=85, C=88 -> max(90-85=5, |90-118|=28, |85-118|=33) = 33.0
    candles = [
        make_candle(timestamp=start, open_=100.0, high=105.0, low=95.0, close=100.0),
        make_candle(
            timestamp=start + timedelta(days=1), open_=116.0, high=120.0, low=115.0, close=118.0
        ),
        make_candle(
            timestamp=start + timedelta(days=2), open_=89.0, high=90.0, low=85.0, close=88.0
        ),
    ]

    tr = TrueRangeIndicator()
    series = tr.calculate_series(candles)

    assert series.values[0].status == IndicatorStatus.VALID
    assert math.isclose(float(series.values[0].value), 10.0, abs_tol=1e-9)  # type: ignore[arg-type]

    assert series.values[1].status == IndicatorStatus.VALID
    assert math.isclose(float(series.values[1].value), 20.0, abs_tol=1e-9)  # type: ignore[arg-type]

    assert series.values[2].status == IndicatorStatus.VALID
    assert math.isclose(float(series.values[2].value), 33.0, abs_tol=1e-9)  # type: ignore[arg-type]


def test_atr_and_natr_independent_reference() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # 3 bars with TRs: 10.0, 20.0, 30.0
    candles = [
        make_candle(timestamp=start, open_=100.0, high=105.0, low=95.0, close=100.0),  # TR=10
        make_candle(
            timestamp=start + timedelta(days=1), open_=110.0, high=120.0, low=100.0, close=115.0
        ),  # TR=max(20, 20, 0)=20
        make_candle(
            timestamp=start + timedelta(days=2), open_=120.0, high=145.0, low=115.0, close=140.0
        ),  # TR=max(30, 30, 0)=30
    ]

    atr = ATRIndicator(period=3)
    series = atr.calculate_series(candles)

    assert series.values[0].status == IndicatorStatus.INSUFFICIENT_DATA
    assert series.values[1].status == IndicatorStatus.INSUFFICIENT_DATA

    # t=2 (3rd bar): seed ATR = (10 + 20 + 30) / 3 = 20.0
    assert series.values[2].status == IndicatorStatus.VALID
    assert math.isclose(float(series.values[2].value), 20.0, abs_tol=1e-6)  # type: ignore[arg-type]

    # NATR at t=2: (ATR / Close) * 100 = (20.0 / 140.0) * 100 = 14.2857142857%
    natr = NATRIndicator(period=3)
    natr_series = natr.calculate_series(candles)
    expected_natr = (20.0 / 140.0) * 100.0
    assert natr_series.values[2].status == IndicatorStatus.VALID
    assert math.isclose(float(natr_series.values[2].value), expected_natr, abs_tol=1e-6)  # type: ignore[arg-type]


def test_rolling_std_independent_reference() -> None:
    """Hand-calculated sample standard deviation reference test.

    Dataset: [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
    N = 8
    Mean = (2+4+4+4+5+5+7+9)/8 = 40/8 = 5.0
    Devs from 5: [-3, -1, -1, -1, 0, 0, 2, 4]
    Sq devs: [9, 1, 1, 1, 0, 0, 4, 16] -> Sum = 32.0
    Sample Variance (N-1 = 7) = 32.0 / 7 = 4.571428571428571
    Sample StdDev = sqrt(32/7) = 2.138089935299395
    """
    prices = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = [
        make_candle(timestamp=start + timedelta(days=i), close=p) for i, p in enumerate(prices)
    ]

    r_std = RollingStdDevIndicator(period=8)
    series = r_std.calculate_series(candles)

    for i in range(7):
        assert series.values[i].status == IndicatorStatus.INSUFFICIENT_DATA

    expected_std = math.sqrt(32.0 / 7.0)
    assert series.values[7].status == IndicatorStatus.VALID
    assert math.isclose(float(series.values[7].value), expected_std, abs_tol=1e-9)  # type: ignore[arg-type]


def test_bollinger_bands_deterministic_precedence() -> None:
    """Verify Bollinger Bands deterministic edge-case precedence:

    1. IF middle <= 0 -> INVALID, value = None
    2. ELSE IF sigma == 0 -> VALID, upper=lower=middle, bandwidth=0.0, percent_b=0.5
    3. ELSE -> regular calculation
    """
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    # Precedence 1: Non-positive middle price -> INVALID
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
        for i in range(3)
    ]
    bb = BollingerBandsIndicator(period=3, std_multiplier=2.0)
    z_series = bb.calculate_series(zero_candles)
    # Middle is 0.0 <= 0 -> INVALID even though sigma is 0!
    assert z_series.values[2].status == IndicatorStatus.INVALID
    assert z_series.values[2].value is None

    # Precedence 2: Positive middle price, but sigma == 0 (flat price)
    flat_prices = [100.0, 100.0, 100.0]
    flat_candles = [
        make_candle(timestamp=start + timedelta(days=i), close=p) for i, p in enumerate(flat_prices)
    ]
    flat_series = bb.calculate_series(flat_candles)
    assert flat_series.values[2].status == IndicatorStatus.VALID
    val = flat_series.values[2].value
    assert isinstance(val, dict)
    assert val["middle"] == 100.0
    assert val["upper"] == 100.0
    assert val["lower"] == 100.0
    assert val["bandwidth"] == 0.0
    assert val["percent_b"] == 0.5

    # Regular case: Positive middle, non-zero sigma
    reg_prices = [10.0, 12.0, 14.0]  # mean = 12.0, std = sqrt(2.0 * 4.0 / 2) = 2.0
    reg_candles = [
        make_candle(timestamp=start + timedelta(days=i), close=p) for i, p in enumerate(reg_prices)
    ]
    reg_series = bb.calculate_series(reg_candles)
    assert reg_series.values[2].status == IndicatorStatus.VALID
    r_val = reg_series.values[2].value
    assert isinstance(r_val, dict)
    assert math.isclose(r_val["middle"], 12.0, abs_tol=1e-9)
    assert math.isclose(r_val["upper"], 12.0 + 2.0 * 2.0, abs_tol=1e-9)  # 16.0
    assert math.isclose(r_val["lower"], 12.0 - 2.0 * 2.0, abs_tol=1e-9)  # 8.0
    assert math.isclose(r_val["bandwidth"], (16.0 - 8.0) / 12.0, abs_tol=1e-9)  # 8/12 = 0.6666667
    assert math.isclose(r_val["percent_b"], (14.0 - 8.0) / (16.0 - 8.0), abs_tol=1e-9)  # 6/8 = 0.75
