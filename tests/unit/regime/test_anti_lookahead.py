"""Anti-lookahead invariant and future-shock regression tests for RegimeEngine."""

from datetime import datetime, timedelta, timezone

from quantpilot.regime.engine import RegimeEngine
from tests.unit.regime.conftest import make_candle
from tests.unit.regime.test_input_contract import _build_full_indicator_mapping


def test_anti_lookahead_prefix_invariant() -> None:
    """Verify that evaluate(C[0..49]) == evaluate(C[0..99])[0..50]."""
    t0 = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    total_candles = 100
    timestamps = [t0 + timedelta(minutes=i) for i in range(total_candles)]

    candles_100 = [make_candle(ts, close=100.0 + (i * 0.1)) for i, ts in enumerate(timestamps)]
    indicators_100 = _build_full_indicator_mapping(timestamps)

    engine = RegimeEngine()

    # Evaluate full 100
    result_100 = engine.evaluate(candles_100, indicators_100)

    # Evaluate prefix 50
    candles_50 = candles_100[:50]
    indicators_50 = _build_full_indicator_mapping(timestamps[:50])
    result_50 = engine.evaluate(candles_50, indicators_50)

    assert len(result_50.values) == 50
    assert len(result_100.values) == 100

    for idx in range(50):
        ctx_50 = result_50.values[idx]
        ctx_100 = result_100.values[idx]

        assert ctx_50.timestamp == ctx_100.timestamp
        assert ctx_50.composite_regime == ctx_100.composite_regime
        assert ctx_50.trend == ctx_100.trend
        assert ctx_50.momentum == ctx_100.momentum
        assert ctx_50.volatility == ctx_100.volatility
        assert ctx_50.volume == ctx_100.volume
        assert ctx_50.structure == ctx_100.structure
        assert ctx_50.evidence == ctx_100.evidence


def test_anti_lookahead_future_shock_invariant() -> None:
    """Inject extreme future shocks at t=50 and assert t in [0..49] remains unchanged."""
    t0 = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    total_candles = 60
    timestamps = [t0 + timedelta(minutes=i) for i in range(total_candles)]

    # Baseline
    candles_base = [make_candle(ts, close=100.0, volume=1000.0) for ts in timestamps]
    indicators_base = _build_full_indicator_mapping(timestamps)

    engine = RegimeEngine()
    result_base = engine.evaluate(candles_base, indicators_base)

    # Shocked series: indices 0..49 identical, index 50 receives 10x price, 100x volume, breakout
    candles_shocked = [make_candle(ts, close=100.0, volume=1000.0) for ts in timestamps]
    candles_shocked[50] = make_candle(
        timestamps[50], open=100.0, high=1000.0, low=90.0, close=950.0, volume=100000.0
    )

    indicators_shocked = _build_full_indicator_mapping(timestamps)
    # Inject shock into indicators at index 50
    indicators_shocked["rvol"].values[50] = (
        indicators_shocked["rvol"].values[50].model_copy(update={"value": 100.0})
    )
    indicators_shocked["structure_breakout_distance"].values[50] = (
        indicators_shocked["structure_breakout_distance"]
        .values[50]
        .model_copy(
            update={
                "value": {
                    "breakout_high": 1.0,
                    "breakdown_low": 0.0,
                    "dist_high": 850.0,
                    "dist_low": 900.0,
                }
            }
        )
    )
    indicators_shocked["bollinger_bands"].values[50] = (
        indicators_shocked["bollinger_bands"]
        .values[50]
        .model_copy(update={"value": {"bandwidth": 0.50}})
    )

    result_shocked = engine.evaluate(candles_shocked, indicators_shocked)

    # Assert that prior history (0..49) is identical
    for idx in range(50):
        ctx_base = result_base.values[idx]
        ctx_shock = result_shocked.values[idx]

        assert ctx_base.composite_regime == ctx_shock.composite_regime
        assert ctx_base.trend == ctx_shock.trend
        assert ctx_base.momentum == ctx_shock.momentum
        assert ctx_base.volatility == ctx_shock.volatility
        assert ctx_base.volume == ctx_shock.volume
        assert ctx_base.structure == ctx_shock.structure
        assert ctx_base.evidence == ctx_shock.evidence

    # And verify the shock at index 50 DID change index 50's classification
    assert result_shocked.values[50].structure != result_base.values[50].structure
