"""Independent reference tests and lookahead-free structure features."""

import math
from datetime import datetime, timedelta, timezone

from quantpilot.quant.models import IndicatorStatus
from quantpilot.quant.structure import (
    RollingHighIndicator,
    RollingLowIndicator,
    StructureBreakoutIndicator,
)
from tests.unit.quant.conftest import make_candle


def test_rolling_high_and_low_reference() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    highs = [105.0, 110.0, 108.0, 112.0]
    lows = [95.0, 90.0, 92.0, 88.0]
    candles = [
        make_candle(
            timestamp=start + timedelta(days=i),
            open_=100.0,
            high=highs[i],
            low=lows[i],
            close=100.0,
        )
        for i in range(4)
    ]

    r_high = RollingHighIndicator(period=3)
    h_series = r_high.calculate_series(candles)

    assert h_series.values[0].status == IndicatorStatus.INSUFFICIENT_DATA
    assert h_series.values[1].status == IndicatorStatus.INSUFFICIENT_DATA
    assert h_series.values[2].status == IndicatorStatus.VALID
    assert math.isclose(float(h_series.values[2].value), 110.0, abs_tol=1e-9)  # type: ignore[arg-type]
    assert h_series.values[3].status == IndicatorStatus.VALID
    assert math.isclose(float(h_series.values[3].value), 112.0, abs_tol=1e-9)  # type: ignore[arg-type]

    r_low = RollingLowIndicator(period=3)
    l_series = r_low.calculate_series(candles)
    assert l_series.values[2].status == IndicatorStatus.VALID
    assert math.isclose(float(l_series.values[2].value), 90.0, abs_tol=1e-9)  # type: ignore[arg-type]
    assert l_series.values[3].status == IndicatorStatus.VALID
    assert math.isclose(float(l_series.values[3].value), 88.0, abs_tol=1e-9)  # type: ignore[arg-type]


def test_structure_breakout_distance_anti_lookahead() -> None:
    """Verify StructureBreakoutDistance compares C[t] against window ending strictly at t-1."""
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # 4 bars: period = 3
    # Bar 0: H=105, L=95, C=100
    # Bar 1: H=108, L=94, C=102
    # Bar 2: H=110, L=96, C=106
    # Prior window for bar 3 (index 3) is bars 0, 1, 2:
    # Prior High = 110.0, Prior Low = 94.0
    # Bar 3: H=125 (spike!), L=112, C=120
    # Close=120 > Prior High (110) -> breakout_high = 1.0, breakdown_low = 0.0
    # Dist High = (120 - 110) / 110 * 100 = 9.090909%
    candles = [
        make_candle(timestamp=start, open_=100.0, high=105.0, low=95.0, close=100.0),
        make_candle(
            timestamp=start + timedelta(days=1), open_=100.0, high=108.0, low=94.0, close=102.0
        ),
        make_candle(
            timestamp=start + timedelta(days=2), open_=102.0, high=110.0, low=96.0, close=106.0
        ),
        make_candle(
            timestamp=start + timedelta(days=3), open_=115.0, high=125.0, low=112.0, close=120.0
        ),
    ]

    sb = StructureBreakoutIndicator(period=3)
    series = sb.calculate_series(candles)

    assert series.values[0].status == IndicatorStatus.INSUFFICIENT_DATA
    assert series.values[1].status == IndicatorStatus.INSUFFICIENT_DATA
    assert series.values[2].status == IndicatorStatus.INSUFFICIENT_DATA

    assert series.values[3].status == IndicatorStatus.VALID
    val = series.values[3].value
    assert isinstance(val, dict)
    assert val["breakout_high"] == 1.0
    assert val["breakdown_low"] == 0.0
    expected_dist_high = ((120.0 - 110.0) / 110.0) * 100.0
    expected_dist_low = ((120.0 - 94.0) / 94.0) * 100.0
    assert math.isclose(val["dist_high"], expected_dist_high, abs_tol=1e-9)
    assert math.isclose(val["dist_low"], expected_dist_low, abs_tol=1e-9)
