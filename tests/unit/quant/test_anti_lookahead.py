"""Strict anti-lookahead invariant regression tests across all 21 catalog indicators."""

import copy

import pytest

from quantpilot.market_data.models import Candle
from quantpilot.quant.registry import default_registry
from quantpilot.quant.relative_strength import RelativeStrengthIndicator
from tests.unit.quant.conftest import make_candle_sequence


@pytest.mark.parametrize(
    "indicator_name",
    [entry["name"] for entry in default_registry.list_available()],
)
def test_all_21_indicators_anti_lookahead_invariant(indicator_name: str) -> None:
    """Invariant: Indicator value at t must NOT depend on any future candle t+k.

    1. Generate 100 deterministic synthetic candles.
    2. Compute indicator series on prefix C0..C49.
    3. Compute indicator series on full sequence C0..C99.
    4. Assert that for all t in 0..49, status and value are identical.
    5. Inject extreme price/volume spike at candle 50, compute on C0..C50.
    6. Assert that for all t in 0..49, status and value remain 100% unchanged.
    """
    full_candles = make_candle_sequence(100)
    prefix_candles = full_candles[:50]

    # Benchmark candles for relative_strength
    bench_candles_full = make_candle_sequence(100, base_price=2000.0, symbol="NIFTY50")
    bench_candles_prefix = bench_candles_full[:50]

    ind = default_registry.get(indicator_name)
    if isinstance(ind, RelativeStrengthIndicator):
        ind.set_benchmark_candles(bench_candles_prefix)

    prefix_series = ind.calculate_series(prefix_candles)

    # Re-instantiate or re-run on full series
    ind_full = default_registry.get(indicator_name)
    if isinstance(ind_full, RelativeStrengthIndicator):
        ind_full.set_benchmark_candles(bench_candles_full)

    full_series = ind_full.calculate_series(full_candles)

    # 1. Compare prefix vs full for t in 0..49
    for t in range(50):
        p_val = prefix_series.values[t]
        f_val = full_series.values[t]
        assert p_val.status == f_val.status, (
            f"Status mismatch at t={t} for {indicator_name}: {p_val.status} != {f_val.status}"
        )
        assert p_val.value == f_val.value, (
            f"Value mismatch at t={t} for {indicator_name}: {p_val.value} != {f_val.value}"
        )

    # 2. Inject anomalous extreme future spike at candle 50
    spike_candles = copy.deepcopy(full_candles[:51])
    spike_candle_50 = spike_candles[50]
    # Extreme 100x price spike and 100x volume spike at candle 50
    spike_candles[50] = Candle(
        symbol=spike_candle_50.symbol,
        exchange=spike_candle_50.exchange,
        timeframe=spike_candle_50.timeframe,
        timestamp=spike_candle_50.timestamp,
        open=spike_candle_50.open * 50.0,
        high=spike_candle_50.high * 100.0,
        low=spike_candle_50.low * 50.0,
        close=spike_candle_50.close * 100.0,
        volume=spike_candle_50.volume * 100.0,
    )

    ind_spike = default_registry.get(indicator_name)
    if isinstance(ind_spike, RelativeStrengthIndicator):
        ind_spike.set_benchmark_candles(bench_candles_full[:51])

    spike_series = ind_spike.calculate_series(spike_candles)

    for t in range(50):
        p_val = prefix_series.values[t]
        s_val = spike_series.values[t]
        assert p_val.status == s_val.status, f"Spike corrupted status at t={t} for {indicator_name}"
        assert p_val.value == s_val.value, f"Spike corrupted value at t={t} for {indicator_name}"
