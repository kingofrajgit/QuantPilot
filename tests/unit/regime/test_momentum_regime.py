"""Unit tests and boundary checks for MomentumClassifier."""

from datetime import datetime, timezone

import pytest

from quantpilot.quant.models import IndicatorStatus
from quantpilot.regime.models import MomentumRegime
from quantpilot.regime.momentum_regime import MomentumClassifier
from tests.unit.regime.conftest import (
    make_candle,
    make_dict_indicator_series,
    make_indicator_series,
)


def test_momentum_positive_and_exact_boundaries() -> None:
    """Verify POSITIVE state and exact boundary thresholds."""
    ts = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    candle = make_candle(ts)
    clf = MomentumClassifier(rsi_bullish_bound=55.0, rsi_bearish_bound=45.0)

    # 1. Clear Positive
    indicators = {
        "rsi": make_indicator_series("rsi", [60.0], [ts]),
        "roc": make_indicator_series("roc", [1.5], [ts]),
        "macd": make_dict_indicator_series(
            "macd", [{"macd": 1.0, "signal": 0.5, "histogram": 0.5}], [ts]
        ),
    }
    state, ev = clf.classify(0, [candle], indicators)
    assert state == MomentumRegime.POSITIVE
    assert ev.dimension == "momentum"
    assert ev.contributing_metrics["rsi"] == 60.0

    # 2. RSI Boundary: exactly 55.0 (>= 55.0 is POSITIVE)
    ind_rsi_exact = {
        "rsi": make_indicator_series("rsi", [55.0], [ts]),
        "roc": make_indicator_series("roc", [0.1], [ts]),
        "macd": make_dict_indicator_series(
            "macd", [{"macd": 1.0, "signal": 0.5, "histogram": 0.1}], [ts]
        ),
    }
    state, _ = clf.classify(0, [candle], ind_rsi_exact)
    assert state == MomentumRegime.POSITIVE

    # 3. RSI Boundary: 54.999 (< 55.0 is NEUTRAL)
    ind_rsi_below = {
        "rsi": make_indicator_series("rsi", [54.999], [ts]),
        "roc": make_indicator_series("roc", [0.1], [ts]),
        "macd": make_dict_indicator_series(
            "macd", [{"macd": 1.0, "signal": 0.5, "histogram": 0.1}], [ts]
        ),
    }
    state, _ = clf.classify(0, [candle], ind_rsi_below)
    assert state == MomentumRegime.NEUTRAL

    # 4. ROC Boundary: exactly 0.0 (not strictly > 0.0, so NEUTRAL)
    ind_roc_exact = {
        "rsi": make_indicator_series("rsi", [60.0], [ts]),
        "roc": make_indicator_series("roc", [0.0], [ts]),
        "macd": make_dict_indicator_series(
            "macd", [{"macd": 1.0, "signal": 0.5, "histogram": 0.1}], [ts]
        ),
    }
    state, _ = clf.classify(0, [candle], ind_roc_exact)
    assert state == MomentumRegime.NEUTRAL

    # 5. Histogram Boundary: exactly 0.0 (not strictly > 0.0, so NEUTRAL)
    ind_hist_exact = {
        "rsi": make_indicator_series("rsi", [60.0], [ts]),
        "roc": make_indicator_series("roc", [0.5], [ts]),
        "macd": make_dict_indicator_series(
            "macd", [{"macd": 1.0, "signal": 1.0, "histogram": 0.0}], [ts]
        ),
    }
    state, _ = clf.classify(0, [candle], ind_hist_exact)
    assert state == MomentumRegime.NEUTRAL


def test_momentum_negative_and_exact_boundaries() -> None:
    """Verify NEGATIVE state and exact lower boundary thresholds."""
    ts = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    candle = make_candle(ts)
    clf = MomentumClassifier(rsi_bullish_bound=55.0, rsi_bearish_bound=45.0)

    # 1. Clear Negative
    indicators = {
        "rsi": make_indicator_series("rsi", [40.0], [ts]),
        "roc": make_indicator_series("roc", [-1.5], [ts]),
        "macd": make_dict_indicator_series(
            "macd", [{"macd": -1.0, "signal": -0.5, "histogram": -0.5}], [ts]
        ),
    }
    state, ev = clf.classify(0, [candle], indicators)
    assert state == MomentumRegime.NEGATIVE

    # 2. RSI Boundary: exactly 45.0 (<= 45.0 is NEGATIVE)
    ind_rsi_exact = {
        "rsi": make_indicator_series("rsi", [45.0], [ts]),
        "roc": make_indicator_series("roc", [-0.1], [ts]),
        "macd": make_dict_indicator_series(
            "macd", [{"macd": -1.0, "signal": -0.5, "histogram": -0.1}], [ts]
        ),
    }
    state, _ = clf.classify(0, [candle], ind_rsi_exact)
    assert state == MomentumRegime.NEGATIVE

    # 3. RSI Boundary: 45.001 (> 45.0 is NEUTRAL)
    ind_rsi_above = {
        "rsi": make_indicator_series("rsi", [45.001], [ts]),
        "roc": make_indicator_series("roc", [-0.1], [ts]),
        "macd": make_dict_indicator_series(
            "macd", [{"macd": -1.0, "signal": -0.5, "histogram": -0.1}], [ts]
        ),
    }
    state, _ = clf.classify(0, [candle], ind_rsi_above)
    assert state == MomentumRegime.NEUTRAL


def test_momentum_neutral_on_conflicts() -> None:
    """Verify NEUTRAL state when momentum indicators have conflicting signs."""
    ts = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    candle = make_candle(ts)
    clf = MomentumClassifier()

    # Bullish RSI, but negative ROC
    indicators = {
        "rsi": make_indicator_series("rsi", [65.0], [ts]),
        "roc": make_indicator_series("roc", [-0.5], [ts]),
        "macd": make_dict_indicator_series(
            "macd", [{"macd": 1.0, "signal": 0.5, "histogram": 0.5}], [ts]
        ),
    }
    state, ev = clf.classify(0, [candle], indicators)
    assert state == MomentumRegime.NEUTRAL
    assert "do not demonstrate unified directional velocity" in ev.rationale


def test_momentum_insufficient_data() -> None:
    """Verify INSUFFICIENT_DATA when indicators are non-valid, None, or malformed."""
    ts = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    candle = make_candle(ts)
    clf = MomentumClassifier()

    # 1. Non-VALID status
    indicators_insufficient = {
        "rsi": make_indicator_series("rsi", [60.0], [ts], status=IndicatorStatus.INSUFFICIENT_DATA),
        "roc": make_indicator_series("roc", [1.0], [ts]),
        "macd": make_dict_indicator_series(
            "macd", [{"macd": 1.0, "signal": 0.5, "histogram": 0.5}], [ts]
        ),
    }
    state, _ = clf.classify(0, [candle], indicators_insufficient)
    assert state == MomentumRegime.INSUFFICIENT_DATA

    # 2. Missing histogram key in MACD dict
    indicators_malformed = {
        "rsi": make_indicator_series("rsi", [60.0], [ts]),
        "roc": make_indicator_series("roc", [1.0], [ts]),
        "macd": make_dict_indicator_series("macd", [{"macd": 1.0}], [ts]),
    }
    state, _ = clf.classify(0, [candle], indicators_malformed)
    assert state == MomentumRegime.INSUFFICIENT_DATA

    # 3. Missing indicator series
    state, ev = clf.classify(0, [candle], {"rsi": make_indicator_series("rsi", [60.0], [ts])})
    assert state == MomentumRegime.INSUFFICIENT_DATA
    assert "Missing required indicator" in ev.rationale

    # 4. Out of bounds index
    with pytest.raises(IndexError):
        clf.classify(
            1,
            [candle],
            {
                "rsi": make_indicator_series("rsi", [60.0], [ts]),
                "roc": make_indicator_series("roc", [1.0], [ts]),
                "macd": make_dict_indicator_series(
                    "macd", [{"macd": 1.0, "signal": 0.5, "histogram": 0.5}], [ts]
                ),
            },
        )
