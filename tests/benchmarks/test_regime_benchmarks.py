"""Empirical performance scaling benchmarks for RegimeEngine (informational only)."""

import time

import pytest

from quantpilot.quant.engine import QuantEngine
from quantpilot.regime.engine import RegimeEngine
from tests.unit.quant.conftest import make_candle_sequence


@pytest.mark.benchmark
@pytest.mark.parametrize("n_candles", [1000, 5000, 10000, 50000])
def test_regime_scaling_benchmark(n_candles: int) -> None:
    """Informational scaling benchmark across candle volumes for RegimeEngine."""
    candles = make_candle_sequence(n_candles)

    # Precompute indicators via QuantEngine
    # We pass repository=None because compute_from_candles does not touch repository
    quant_engine = QuantEngine(repository=None)  # type: ignore[arg-type]
    indicators = quant_engine.compute_from_candles(candles, list(RegimeEngine.REQUIRED_INDICATORS))

    regime_engine = RegimeEngine()

    start_time = time.perf_counter()
    result = regime_engine.evaluate(candles, indicators)
    elapsed_s = time.perf_counter() - start_time

    elapsed_ms = elapsed_s * 1000.0
    latency_per_1k_ms = (elapsed_ms / n_candles) * 1000.0

    print(
        f"\n[REGIME BENCHMARK] Workload: {n_candles:6d} candles | "
        f"Elapsed: {elapsed_ms:8.2f} ms | "
        f"Latency per 1k: {latency_per_1k_ms:6.2f} ms"
    )

    assert len(result.values) == n_candles
    assert elapsed_ms > 0.0
