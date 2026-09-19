"""Unit tests and boundary checks for StructureClassifier."""

from datetime import datetime, timezone
from typing import Any

from quantpilot.regime.models import MarketStructure
from quantpilot.regime.structure_regime import StructureClassifier
from tests.unit.regime.conftest import (
    make_candle,
    make_dict_indicator_series,
    make_indicator_series,
)


def _build_structure_indicators(
    ts: datetime,
    breakout_high: float = 0.0,
    breakdown_low: float = 0.0,
    dist_high: float = -5.0,
    dist_low: float = 5.0,
    bandwidth: float = 0.05,
    sma: float = 100.0,
    sma_slope: float = 0.0,
    ema_slope: float = 0.0,
) -> dict[str, Any]:
    return {
        "structure_breakout_distance": make_dict_indicator_series(
            "structure_breakout_distance",
            [
                {
                    "breakout_high": breakout_high,
                    "breakdown_low": breakdown_low,
                    "dist_high": dist_high,
                    "dist_low": dist_low,
                }
            ],
            [ts],
        ),
        "bollinger_bands": make_dict_indicator_series(
            "bollinger_bands", [{"bandwidth": bandwidth}], [ts]
        ),
        "sma": make_indicator_series("sma", [sma], [ts]),
        "sma_slope": make_indicator_series("sma_slope", [sma_slope], [ts]),
        "ema_slope": make_indicator_series("ema_slope", [ema_slope], [ts]),
    }


def test_structure_breakout_and_breakdown_precedence() -> None:
    """Verify BREAKOUT and BREAKDOWN states and their absolute precedence."""
    ts = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    candle = make_candle(ts, close=110.0)
    clf = StructureClassifier()

    # 1. Clear BREAKOUT
    ind_breakout = _build_structure_indicators(
        ts, breakout_high=1.0, breakdown_low=0.0, bandwidth=0.02
    )
    state, ev = clf.classify(0, [candle], ind_breakout)
    assert state == MarketStructure.BREAKOUT
    assert ev.dimension == "structure"
    assert "Close exceeded prior rolling high channel" in ev.rationale

    # BREAKOUT takes precedence even when bandwidth <= 0.030 (consolidation)
    assert ind_breakout["bollinger_bands"].values[0].value["bandwidth"] == 0.02
    assert state == MarketStructure.BREAKOUT

    # 2. Clear BREAKDOWN
    candle_down = make_candle(ts, close=90.0)
    ind_breakdown = _build_structure_indicators(
        ts, breakout_high=0.0, breakdown_low=1.0, bandwidth=0.02
    )
    state_down, ev_down = clf.classify(0, [candle_down], ind_breakdown)
    assert state_down == MarketStructure.BREAKDOWN
    assert "Close broke below prior rolling low channel" in ev_down.rationale


def test_structure_consolidation() -> None:
    """Verify CONSOLIDATION state when bandwidth <= threshold without breakout."""
    ts = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    candle = make_candle(ts, close=100.0)
    clf = StructureClassifier(bbw_consolidation_threshold=0.030)

    # 1. Bandwidth <= 0.030
    ind_consolidation = _build_structure_indicators(
        ts, breakout_high=0.0, breakdown_low=0.0, bandwidth=0.028
    )
    state, ev = clf.classify(0, [candle], ind_consolidation)
    assert state == MarketStructure.CONSOLIDATION
    assert ev.contributing_metrics["bandwidth"] == 0.028

    # 2. Boundary exact: 0.030 is CONSOLIDATION
    ind_consolidation_exact = _build_structure_indicators(
        ts, breakout_high=0.0, breakdown_low=0.0, bandwidth=0.030
    )
    state_exact, _ = clf.classify(0, [candle], ind_consolidation_exact)
    assert state_exact == MarketStructure.CONSOLIDATION

    # 3. 0.0301 is not consolidation
    ind_consolidation_above = _build_structure_indicators(
        ts, breakout_high=0.0, breakdown_low=0.0, bandwidth=0.0301
    )
    state_above, _ = clf.classify(0, [candle], ind_consolidation_above)
    assert state_above != MarketStructure.CONSOLIDATION


def test_structure_trending_bullish_and_bearish() -> None:
    """Verify TRENDING state when proximity and directional moving average slopes align."""
    ts = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    clf = StructureClassifier(trend_channel_proximity=0.020, bbw_consolidation_threshold=0.030)

    # 1. Bullish Trending: dist_high >= -2.0, close > sma, slopes > 0
    candle_bull = make_candle(ts, close=105.0)
    ind_bull = _build_structure_indicators(
        ts,
        dist_high=-1.5,  # within 2% of rolling high
        bandwidth=0.05,  # above consolidation threshold
        sma=100.0,
        sma_slope=0.5,
        ema_slope=0.5,
    )
    state_bull, ev_bull = clf.classify(0, [candle_bull], ind_bull)
    assert state_bull == MarketStructure.TRENDING
    assert "Bullish channel proximity" in ev_bull.rationale

    # 2. Bearish Trending: dist_low <= 2.0, close < sma, slopes < 0
    candle_bear = make_candle(ts, close=95.0)
    ind_bear = _build_structure_indicators(
        ts,
        dist_low=1.2,  # within 2% of rolling low
        bandwidth=0.05,
        sma=100.0,
        sma_slope=-0.5,
        ema_slope=-0.5,
    )
    state_bear, ev_bear = clf.classify(0, [candle_bear], ind_bear)
    assert state_bear == MarketStructure.TRENDING
    assert "Bearish channel proximity" in ev_bear.rationale


def test_structure_ranging() -> None:
    """Verify RANGING state when price oscillates without breakout, consolidation, or trend."""
    ts = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    candle = make_candle(ts, close=100.0)
    clf = StructureClassifier()

    ind_ranging = _build_structure_indicators(
        ts,
        dist_high=-5.0,  # far from high
        dist_low=5.0,  # far from low
        bandwidth=0.05,  # normal bandwidth
        sma=100.0,
        sma_slope=0.0,
        ema_slope=0.0,
    )
    state, ev = clf.classify(0, [candle], ind_ranging)
    assert state == MarketStructure.RANGING
    assert "Price oscillating within structured range" in ev.rationale


def test_structure_volume_absence_verified() -> None:
    """Verify Volume is decoupled and completely absent from StructureClassifier dependencies."""
    clf = StructureClassifier()
    assert "volume" not in clf.required_indicators
    assert "rvol" not in clf.required_indicators
    assert "obv" not in clf.required_indicators
    assert clf.required_indicators == [
        "structure_breakout_distance",
        "bollinger_bands",
        "sma",
        "sma_slope",
        "ema_slope",
    ]
