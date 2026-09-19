"""Unit tests and boundary checks for VolumeClassifier."""

from datetime import datetime, timedelta, timezone

import pytest

from quantpilot.quant.models import IndicatorStatus
from quantpilot.regime.models import VolumeRegime
from quantpilot.regime.volume_regime import VolumeClassifier
from tests.unit.regime.conftest import make_candle, make_indicator_series


def test_volume_accumulation_and_distribution() -> None:
    """Verify ACCUMULATION, DISTRIBUTION, and HIGH_VOLUME states."""
    t0 = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=1)
    candles = [
        make_candle(t0, open=100.0, close=100.0),
        make_candle(t1, open=100.0, close=105.0),  # bullish candle
    ]
    clf = VolumeClassifier(rvol_high_threshold=1.20, rvol_low_threshold=0.80)

    # 1. ACCUMULATION: rvol >= 1.20, close > open, obv increasing
    indicators_acc = {
        "rvol": make_indicator_series("rvol", [1.0, 1.5], [t0, t1]),
        "obv": make_indicator_series("obv", [1000.0, 2500.0], [t0, t1]),
    }
    state, ev = clf.classify(1, candles, indicators_acc)
    assert state == VolumeRegime.ACCUMULATION
    assert ev.dimension == "volume"
    assert ev.contributing_metrics["rvol"] == 1.5

    # 2. DISTRIBUTION: rvol >= 1.20, close < open, obv decreasing
    candles_dist = [
        make_candle(t0, open=100.0, close=100.0),
        make_candle(t1, open=105.0, close=98.0),  # bearish candle
    ]
    indicators_dist = {
        "rvol": make_indicator_series("rvol", [1.0, 1.5], [t0, t1]),
        "obv": make_indicator_series("obv", [1000.0, 500.0], [t0, t1]),
    }
    state, ev = clf.classify(1, candles_dist, indicators_dist)
    assert state == VolumeRegime.DISTRIBUTION

    # 3. HIGH_VOLUME: rvol >= 1.20, but candle is flat (close == open)
    candles_flat = [
        make_candle(t0, open=100.0, close=100.0),
        make_candle(t1, open=100.0, close=100.0),  # flat doji
    ]
    indicators_high = {
        "rvol": make_indicator_series("rvol", [1.0, 1.5], [t0, t1]),
        "obv": make_indicator_series("obv", [1000.0, 1000.0], [t0, t1]),
    }
    state, ev = clf.classify(1, candles_flat, indicators_high)
    assert state == VolumeRegime.HIGH_VOLUME


def test_volume_low_and_normal_boundaries() -> None:
    """Verify LOW_VOLUME and NORMAL_VOLUME exact boundaries."""
    t0 = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=1)
    candles = [make_candle(t0), make_candle(t1)]
    clf = VolumeClassifier(rvol_high_threshold=1.20, rvol_low_threshold=0.80)

    # 1. LOW_VOLUME: 0.799 < 0.80
    ind_low = {
        "rvol": make_indicator_series("rvol", [1.0, 0.799], [t0, t1]),
        "obv": make_indicator_series("obv", [100.0, 100.0], [t0, t1]),
    }
    state, _ = clf.classify(1, candles, ind_low)
    assert state == VolumeRegime.LOW_VOLUME

    # 2. Lower boundary exact: 0.800 is NORMAL_VOLUME (0.80 <= rvol < 1.20)
    ind_lower_exact = {
        "rvol": make_indicator_series("rvol", [1.0, 0.800], [t0, t1]),
        "obv": make_indicator_series("obv", [100.0, 100.0], [t0, t1]),
    }
    state, _ = clf.classify(1, candles, ind_lower_exact)
    assert state == VolumeRegime.NORMAL_VOLUME

    # 3. Upper boundary: 1.199 is NORMAL_VOLUME (0.80 <= rvol < 1.20)
    ind_upper_normal = {
        "rvol": make_indicator_series("rvol", [1.0, 1.199], [t0, t1]),
        "obv": make_indicator_series("obv", [100.0, 100.0], [t0, t1]),
    }
    state, _ = clf.classify(1, candles, ind_upper_normal)
    assert state == VolumeRegime.NORMAL_VOLUME

    # 4. Upper boundary exact: 1.200 is HIGH_VOLUME (>= 1.20)
    ind_upper_high = {
        "rvol": make_indicator_series("rvol", [1.0, 1.200], [t0, t1]),
        "obv": make_indicator_series("obv", [100.0, 100.0], [t0, t1]),
    }
    state, _ = clf.classify(1, candles, ind_upper_high)
    assert state == VolumeRegime.HIGH_VOLUME


def test_volume_change_absence_verified() -> None:
    """Verify that volume_change is completely absent from VolumeClassifier."""
    clf = VolumeClassifier()
    assert "volume_change" not in clf.required_indicators
    assert clf.required_indicators == ["rvol", "obv"]


def test_volume_insufficient_data() -> None:
    """Verify INSUFFICIENT_DATA at index 0 (no prior OBV) and on non-valid data."""
    t0 = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=1)
    candles = [make_candle(t0), make_candle(t1)]
    clf = VolumeClassifier()

    indicators = {
        "rvol": make_indicator_series("rvol", [1.0, 1.0], [t0, t1]),
        "obv": make_indicator_series("obv", [100.0, 100.0], [t0, t1]),
    }

    # 1. Index 0 requires prior OBV
    state_0, ev_0 = clf.classify(0, candles, indicators)
    assert state_0 == VolumeRegime.INSUFFICIENT_DATA
    assert "OBV delta requires at least one preceding observation" in ev_0.rationale

    # 2. Prior OBV has non-VALID status
    ind_prior_insufficient = {
        "rvol": make_indicator_series("rvol", [1.0, 1.0], [t0, t1]),
        "obv": make_indicator_series(
            "obv", [100.0, 100.0], [t0, t1], status=IndicatorStatus.INSUFFICIENT_DATA
        ),
    }
    state_1, _ = clf.classify(1, candles, ind_prior_insufficient)
    assert state_1 == VolumeRegime.INSUFFICIENT_DATA

    # 3. Missing indicators in mapping
    state_miss, ev_miss = clf.classify(1, candles, {})
    assert state_miss == VolumeRegime.INSUFFICIENT_DATA
    assert "Missing required indicator" in ev_miss.rationale

    # 4. Out of bounds index
    with pytest.raises(IndexError):
        clf.classify(3, candles, indicators)
