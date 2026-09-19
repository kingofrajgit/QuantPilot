"""Unit tests and boundary checks for TrendClassifier."""

from datetime import datetime, timezone

import pytest

from quantpilot.quant.models import IndicatorStatus
from quantpilot.regime.models import TrendRegime
from quantpilot.regime.trend_regime import TrendClassifier
from tests.unit.regime.conftest import make_candle, make_indicator_series


def test_trend_bullish_and_exact_boundaries() -> None:
    """Verify BULLISH state and exact distance/slope boundary transitions."""
    ts = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    candle = make_candle(ts)
    clf = TrendClassifier(slope_threshold=0.0, distance_threshold=0.005)

    # 1. Clear Bullish
    indicators = {
        "price_vs_sma": make_indicator_series("price_vs_sma", [0.01], [ts]),
        "sma_slope": make_indicator_series("sma_slope", [0.1], [ts]),
        "ema_slope": make_indicator_series("ema_slope", [0.1], [ts]),
    }
    state, ev = clf.classify(0, [candle], indicators)
    assert state == TrendRegime.BULLISH
    assert ev.dimension == "trend"
    assert ev.contributing_metrics["price_vs_sma"] == 0.01

    # 2. Distance boundary: 0.005001 > 0.005 (BULLISH)
    ind_boundary_above = {
        "price_vs_sma": make_indicator_series("price_vs_sma", [0.005001], [ts]),
        "sma_slope": make_indicator_series("sma_slope", [0.001], [ts]),
        "ema_slope": make_indicator_series("ema_slope", [0.001], [ts]),
    }
    state, _ = clf.classify(0, [candle], ind_boundary_above)
    assert state == TrendRegime.BULLISH

    # 3. Distance boundary: exactly 0.005 (not strictly greater, so SIDEWAYS)
    ind_boundary_exact = {
        "price_vs_sma": make_indicator_series("price_vs_sma", [0.005], [ts]),
        "sma_slope": make_indicator_series("sma_slope", [0.001], [ts]),
        "ema_slope": make_indicator_series("ema_slope", [0.001], [ts]),
    }
    state, _ = clf.classify(0, [candle], ind_boundary_exact)
    assert state == TrendRegime.SIDEWAYS

    # 4. Slope boundary: exactly 0.0 (not strictly greater, so SIDEWAYS)
    ind_slope_exact = {
        "price_vs_sma": make_indicator_series("price_vs_sma", [0.01], [ts]),
        "sma_slope": make_indicator_series("sma_slope", [0.0], [ts]),
        "ema_slope": make_indicator_series("ema_slope", [0.001], [ts]),
    }
    state, _ = clf.classify(0, [candle], ind_slope_exact)
    assert state == TrendRegime.SIDEWAYS


def test_trend_bearish_and_exact_boundaries() -> None:
    """Verify BEARISH state and negative boundary transitions."""
    ts = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    candle = make_candle(ts)
    clf = TrendClassifier(slope_threshold=0.0, distance_threshold=0.005)

    # 1. Clear Bearish
    indicators = {
        "price_vs_sma": make_indicator_series("price_vs_sma", [-0.01], [ts]),
        "sma_slope": make_indicator_series("sma_slope", [-0.1], [ts]),
        "ema_slope": make_indicator_series("ema_slope", [-0.1], [ts]),
    }
    state, ev = clf.classify(0, [candle], indicators)
    assert state == TrendRegime.BEARISH

    # 2. Boundary: -0.005001 < -0.005 (BEARISH)
    ind_boundary_below = {
        "price_vs_sma": make_indicator_series("price_vs_sma", [-0.005001], [ts]),
        "sma_slope": make_indicator_series("sma_slope", [-0.001], [ts]),
        "ema_slope": make_indicator_series("ema_slope", [-0.001], [ts]),
    }
    state, _ = clf.classify(0, [candle], ind_boundary_below)
    assert state == TrendRegime.BEARISH

    # 3. Boundary: exactly -0.005 (SIDEWAYS)
    ind_boundary_exact = {
        "price_vs_sma": make_indicator_series("price_vs_sma", [-0.005], [ts]),
        "sma_slope": make_indicator_series("sma_slope", [-0.001], [ts]),
        "ema_slope": make_indicator_series("ema_slope", [-0.001], [ts]),
    }
    state, _ = clf.classify(0, [candle], ind_boundary_exact)
    assert state == TrendRegime.SIDEWAYS


def test_trend_conflicting_slopes_is_sideways() -> None:
    """Verify conflicting slope or position signals resolve to SIDEWAYS."""
    ts = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    candle = make_candle(ts)
    clf = TrendClassifier()

    indicators = {
        "price_vs_sma": make_indicator_series("price_vs_sma", [0.02], [ts]),
        "sma_slope": make_indicator_series("sma_slope", [0.05], [ts]),
        "ema_slope": make_indicator_series("ema_slope", [-0.05], [ts]),  # opposing slope
    }
    state, ev = clf.classify(0, [candle], indicators)
    assert state == TrendRegime.SIDEWAYS
    assert "do not satisfy" in ev.rationale


def test_trend_insufficient_data() -> None:
    """Verify INSUFFICIENT_DATA when indicator status is not VALID or value is None."""
    ts = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    candle = make_candle(ts)
    clf = TrendClassifier()

    # 1. Non-VALID status
    indicators_insufficient = {
        "price_vs_sma": make_indicator_series(
            "price_vs_sma", [0.01], [ts], status=IndicatorStatus.INSUFFICIENT_DATA
        ),
        "sma_slope": make_indicator_series("sma_slope", [0.05], [ts]),
        "ema_slope": make_indicator_series("ema_slope", [0.05], [ts]),
    }
    state, ev = clf.classify(0, [candle], indicators_insufficient)
    assert state == TrendRegime.INSUFFICIENT_DATA
    assert ev.contributing_metrics["price_vs_sma_status"] == "INSUFFICIENT_DATA"

    # 2. None value
    indicators_none = {
        "price_vs_sma": make_indicator_series("price_vs_sma", [None], [ts]),
        "sma_slope": make_indicator_series("sma_slope", [0.05], [ts]),
        "ema_slope": make_indicator_series("ema_slope", [0.05], [ts]),
    }
    state, _ = clf.classify(0, [candle], indicators_none)
    assert state == TrendRegime.INSUFFICIENT_DATA

    # 3. Missing indicator in mapping
    state, ev = clf.classify(
        0,
        [candle],
        {
            "price_vs_sma": make_indicator_series("price_vs_sma", [0.01], [ts]),
        },
    )
    assert state == TrendRegime.INSUFFICIENT_DATA
    assert "Missing required indicator" in ev.rationale

    # 4. Out of bounds index
    with pytest.raises(IndexError):
        clf.classify(
            5,
            [candle],
            {
                "price_vs_sma": make_indicator_series("price_vs_sma", [0.01], [ts]),
                "sma_slope": make_indicator_series("sma_slope", [0.05], [ts]),
                "ema_slope": make_indicator_series("ema_slope", [0.05], [ts]),
            },
        )
