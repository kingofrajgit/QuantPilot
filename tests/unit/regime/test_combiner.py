"""Unit tests for RegimeCombiner precedence matrix (Steps 1 through 8)."""

from quantpilot.regime.combiner import RegimeCombiner
from quantpilot.regime.models import (
    CompositeRegime,
    MarketStructure,
    MomentumRegime,
    TrendRegime,
    VolatilityRegime,
)


def test_combiner_step_1_insufficient_data() -> None:
    """Step 1: If any composite dimension is INSUFFICIENT_DATA -> Composite is INSUFFICIENT_DATA."""
    combiner = RegimeCombiner()

    # Trend insufficient
    state, ev = combiner.combine(
        trend=TrendRegime.INSUFFICIENT_DATA,
        momentum=MomentumRegime.POSITIVE,
        volatility=VolatilityRegime.NORMAL,
        structure=MarketStructure.TRENDING,
    )
    assert state == CompositeRegime.INSUFFICIENT_DATA
    assert "INSUFFICIENT_DATA" in ev.rationale

    # Momentum insufficient
    state_m, _ = combiner.combine(
        trend=TrendRegime.BULLISH,
        momentum=MomentumRegime.INSUFFICIENT_DATA,
        volatility=VolatilityRegime.NORMAL,
        structure=MarketStructure.TRENDING,
    )
    assert state_m == CompositeRegime.INSUFFICIENT_DATA

    # Volatility insufficient
    state_v, _ = combiner.combine(
        trend=TrendRegime.BULLISH,
        momentum=MomentumRegime.POSITIVE,
        volatility=VolatilityRegime.INSUFFICIENT_DATA,
        structure=MarketStructure.TRENDING,
    )
    assert state_v == CompositeRegime.INSUFFICIENT_DATA

    # Structure insufficient
    state_s, _ = combiner.combine(
        trend=TrendRegime.BULLISH,
        momentum=MomentumRegime.POSITIVE,
        volatility=VolatilityRegime.NORMAL,
        structure=MarketStructure.INSUFFICIENT_DATA,
    )
    assert state_s == CompositeRegime.INSUFFICIENT_DATA


def test_combiner_step_2_divergent() -> None:
    """Step 2: Directional divergence overrides lower-priority structures."""
    combiner = RegimeCombiner()

    # Bullish Trend + Negative Momentum
    state_bull_div, ev_bull_div = combiner.combine(
        trend=TrendRegime.BULLISH,
        momentum=MomentumRegime.NEGATIVE,
        volatility=VolatilityRegime.LOW,
        structure=MarketStructure.CONSOLIDATION,  # would match step 5 or 6, but step 2 wins
    )
    assert state_bull_div == CompositeRegime.DIVERGENT
    assert "Directional divergence detected" in ev_bull_div.rationale

    # Bearish Trend + Positive Momentum
    state_bear_div, ev_bear_div = combiner.combine(
        trend=TrendRegime.BEARISH,
        momentum=MomentumRegime.POSITIVE,
        volatility=VolatilityRegime.HIGH,
        structure=MarketStructure.RANGING,
    )
    assert state_bear_div == CompositeRegime.DIVERGENT


def test_combiner_step_3_volatile_unstructured() -> None:
    """Step 3: High Volatility + Ranging Structure -> VOLATILE_UNSTRUCTURED."""
    combiner = RegimeCombiner()

    state, ev = combiner.combine(
        trend=TrendRegime.SIDEWAYS,
        momentum=MomentumRegime.POSITIVE,
        volatility=VolatilityRegime.HIGH,
        structure=MarketStructure.RANGING,
    )
    assert state == CompositeRegime.VOLATILE_UNSTRUCTURED
    assert "High volatility observed" in ev.rationale


def test_combiner_step_4_directional_trending_expansion() -> None:
    """Step 4: Directional alignment with BREAKOUT or TRENDING structure."""
    combiner = RegimeCombiner()

    # Bullish Trend + Positive Momentum + Breakout
    state_bull_bo, _ = combiner.combine(
        trend=TrendRegime.BULLISH,
        momentum=MomentumRegime.POSITIVE,
        volatility=VolatilityRegime.HIGH,
        structure=MarketStructure.BREAKOUT,
    )
    assert state_bull_bo == CompositeRegime.BULLISH_TRENDING_EXPANSION

    # Bullish Trend + Positive Momentum + Trending
    state_bull_tr, _ = combiner.combine(
        trend=TrendRegime.BULLISH,
        momentum=MomentumRegime.POSITIVE,
        volatility=VolatilityRegime.NORMAL,
        structure=MarketStructure.TRENDING,
    )
    assert state_bull_tr == CompositeRegime.BULLISH_TRENDING_EXPANSION

    # Bearish Trend + Negative Momentum + Breakdown
    state_bear_bd, _ = combiner.combine(
        trend=TrendRegime.BEARISH,
        momentum=MomentumRegime.NEGATIVE,
        volatility=VolatilityRegime.HIGH,
        structure=MarketStructure.BREAKDOWN,
    )
    assert state_bear_bd == CompositeRegime.BEARISH_TRENDING_EXPANSION

    # Bearish Trend + Negative Momentum + Trending
    state_bear_tr, _ = combiner.combine(
        trend=TrendRegime.BEARISH,
        momentum=MomentumRegime.NEGATIVE,
        volatility=VolatilityRegime.NORMAL,
        structure=MarketStructure.TRENDING,
    )
    assert state_bear_tr == CompositeRegime.BEARISH_TRENDING_EXPANSION


def test_combiner_step_5_directional_consolidation() -> None:
    """Step 5: Directional trend paused in structural consolidation."""
    combiner = RegimeCombiner()

    # Bullish Trend + Neutral Momentum + Normal Volatility + Consolidation
    state_bull_c, _ = combiner.combine(
        trend=TrendRegime.BULLISH,
        momentum=MomentumRegime.NEUTRAL,
        volatility=VolatilityRegime.NORMAL,
        structure=MarketStructure.CONSOLIDATION,
    )
    assert state_bull_c == CompositeRegime.BULLISH_CONSOLIDATION

    # Bearish Trend + Neutral Momentum + Normal Volatility + Consolidation
    state_bear_c, _ = combiner.combine(
        trend=TrendRegime.BEARISH,
        momentum=MomentumRegime.NEUTRAL,
        volatility=VolatilityRegime.NORMAL,
        structure=MarketStructure.CONSOLIDATION,
    )
    assert state_bear_c == CompositeRegime.BEARISH_CONSOLIDATION


def test_combiner_step_6_compression() -> None:
    """Step 6: Directionless compression (Low Volatility + Consolidation)."""
    combiner = RegimeCombiner()

    state, ev = combiner.combine(
        trend=TrendRegime.SIDEWAYS,
        momentum=MomentumRegime.NEUTRAL,
        volatility=VolatilityRegime.LOW,
        structure=MarketStructure.CONSOLIDATION,
    )
    assert state == CompositeRegime.COMPRESSION
    assert "compression" in ev.rationale.lower()


def test_combiner_step_7_sideways_range() -> None:
    """Step 7: Sideways Trend + (Ranging or Consolidation with Normal/High vol)."""
    combiner = RegimeCombiner()

    state_range, _ = combiner.combine(
        trend=TrendRegime.SIDEWAYS,
        momentum=MomentumRegime.NEUTRAL,
        volatility=VolatilityRegime.NORMAL,
        structure=MarketStructure.RANGING,
    )
    assert state_range == CompositeRegime.SIDEWAYS_RANGE

    state_consol, _ = combiner.combine(
        trend=TrendRegime.SIDEWAYS,
        momentum=MomentumRegime.NEUTRAL,
        volatility=VolatilityRegime.NORMAL,
        structure=MarketStructure.CONSOLIDATION,
    )
    assert state_consol == CompositeRegime.SIDEWAYS_RANGE


def test_combiner_step_8_unknown_fallback() -> None:
    """Step 8: Valid dimensions that do not match canonical patterns fallback to UNKNOWN."""
    combiner = RegimeCombiner()

    # Bullish Trend, Neutral Momentum, Normal Volatility, Ranging Structure
    state, ev = combiner.combine(
        trend=TrendRegime.BULLISH,
        momentum=MomentumRegime.NEUTRAL,
        volatility=VolatilityRegime.NORMAL,
        structure=MarketStructure.RANGING,
    )
    assert state == CompositeRegime.UNKNOWN
    assert "does not match any predefined canonical composite taxonomy rule" in ev.rationale
