"""Independent reference tests and zero-denominator safety for volume indicators."""

import math
from datetime import datetime, timedelta, timezone

from quantpilot.quant.models import IndicatorStatus
from quantpilot.quant.volume import (
    OBVIndicator,
    RVOLIndicator,
    VolumeChangeIndicator,
    VolumeSMAIndicator,
)
from tests.unit.quant.conftest import make_candle


def test_volume_sma_reference() -> None:
    volumes = [100.0, 200.0, 300.0, 400.0]
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = [
        make_candle(timestamp=start + timedelta(days=i), close=100.0, volume=v)
        for i, v in enumerate(volumes)
    ]

    vol_sma = VolumeSMAIndicator(period=3)
    series = vol_sma.calculate_series(candles)

    assert series.values[0].status == IndicatorStatus.INSUFFICIENT_DATA
    assert series.values[1].status == IndicatorStatus.INSUFFICIENT_DATA

    # t=2: (100+200+300)/3 = 200.0
    assert series.values[2].status == IndicatorStatus.VALID
    assert math.isclose(float(series.values[2].value), 200.0, abs_tol=1e-9)  # type: ignore[arg-type]

    # t=3: (200+300+400)/3 = 300.0
    assert series.values[3].status == IndicatorStatus.VALID
    assert math.isclose(float(series.values[3].value), 300.0, abs_tol=1e-9)  # type: ignore[arg-type]


def test_rvol_zero_denominator_precedence() -> None:
    """RVOL zero-denominator rules:

    1. 0 / 0 -> INVALID, value = None
    2. positive / 0 -> INVALID, value = None
    3. positive / positive -> VALID, exact ratio
    """
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    # 1. 0 / 0 case: zero volume throughout
    zero_candles = [
        make_candle(timestamp=start + timedelta(days=i), close=100.0, volume=0.0) for i in range(4)
    ]
    rvol = RVOLIndicator(period=3)
    z_series = rvol.calculate_series(zero_candles)
    # At t=2, VolSMA = 0.0, V = 0.0 -> INVALID
    assert z_series.values[2].status == IndicatorStatus.INVALID
    assert z_series.values[2].value is None

    # 2. positive / 0 case: VolSMA = 0, current V = 500
    pos_zero_candles = [
        make_candle(timestamp=start, close=100.0, volume=0.0),
        make_candle(timestamp=start + timedelta(days=1), close=100.0, volume=0.0),
        make_candle(timestamp=start + timedelta(days=2), close=100.0, volume=500.0),
    ]
    # VolSMA for window of size 2 ending at t=1 is 0.0
    rvol2 = RVOLIndicator(period=2)
    # VolSMA at t=1 is (0+0)/2 = 0.0
    pz_series = rvol2.calculate_series(pos_zero_candles)
    assert pz_series.values[1].status == IndicatorStatus.INVALID
    assert pz_series.values[1].value is None

    # 3. Valid positive case: VolSMA = 200, V = 300 -> ratio = 1.5
    valid_candles = [
        make_candle(timestamp=start, close=100.0, volume=100.0),
        make_candle(timestamp=start + timedelta(days=1), close=100.0, volume=200.0),
        make_candle(timestamp=start + timedelta(days=2), close=100.0, volume=300.0),
    ]
    val_series = rvol.calculate_series(valid_candles)
    # VolSMA at t=2 is 200, V=300 -> RVOL = 300 / 200 = 1.5
    assert val_series.values[2].status == IndicatorStatus.VALID
    assert math.isclose(float(val_series.values[2].value), 1.5, abs_tol=1e-9)  # type: ignore[arg-type]


def test_volume_change_zero_denominator_and_reference() -> None:
    """VolumeChange:

    - V_prev == 0 -> INVALID, value = None
    - V_prev > 0 -> VALID
    """
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = [
        make_candle(timestamp=start, close=100.0, volume=0.0),
        make_candle(timestamp=start + timedelta(days=1), close=100.0, volume=100.0),
        make_candle(timestamp=start + timedelta(days=2), close=100.0, volume=150.0),
    ]
    vc = VolumeChangeIndicator(lag=1)
    series = vc.calculate_series(candles)

    assert series.values[0].status == IndicatorStatus.INSUFFICIENT_DATA

    # t=1: V_prev = 0 -> INVALID
    assert series.values[1].status == IndicatorStatus.INVALID
    assert series.values[1].value is None

    # t=2: V_prev = 100, V_curr = 150 -> (150 - 100) / 100 * 100 = 50.0%
    assert series.values[2].status == IndicatorStatus.VALID
    assert math.isclose(float(series.values[2].value), 50.0, abs_tol=1e-9)  # type: ignore[arg-type]


def test_obv_reference_and_monotonicity() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = [
        make_candle(timestamp=start, close=100.0, volume=1000.0),  # t=0: OBV=0
        make_candle(timestamp=start + timedelta(days=1), close=102.0, volume=500.0),  # up: +500
        make_candle(
            timestamp=start + timedelta(days=2), close=102.0, volume=300.0
        ),  # flat: unchanged (500)
        make_candle(
            timestamp=start + timedelta(days=3), close=101.0, volume=400.0
        ),  # down: -400 (100)
    ]

    obv = OBVIndicator()
    series = obv.calculate_series(candles)

    assert series.values[0].status == IndicatorStatus.VALID
    assert math.isclose(float(series.values[0].value), 0.0, abs_tol=1e-9)  # type: ignore[arg-type]

    assert series.values[1].status == IndicatorStatus.VALID
    assert math.isclose(float(series.values[1].value), 500.0, abs_tol=1e-9)  # type: ignore[arg-type]

    assert series.values[2].status == IndicatorStatus.VALID
    assert math.isclose(float(series.values[2].value), 500.0, abs_tol=1e-9)  # type: ignore[arg-type]

    assert series.values[3].status == IndicatorStatus.VALID
    assert math.isclose(float(series.values[3].value), 100.0, abs_tol=1e-9)  # type: ignore[arg-type]
