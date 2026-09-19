"""Empirical performance scaling benchmarks across candle series workloads (informational only)."""

import time

import pytest

from quantpilot.quant.registry import default_registry
from quantpilot.quant.relative_strength import RelativeStrengthIndicator
from tests.unit.quant.conftest import make_candle_sequence


@pytest.mark.benchmark
@pytest.mark.parametrize("n_candles", [1000, 5000, 10000, 50000])
def test_full_catalog_scaling_benchmark(n_candles: int) -> None:
    """Informational scaling benchmark across candle volumes."""
    candles = make_candle_sequence(n_candles)
    bench_candles = make_candle_sequence(n_candles, base_price=2000.0, symbol="NIFTY50")

    start_time = time.perf_counter()

    for entry in default_registry.list_available():
        ind = default_registry.get(entry["name"])
        if isinstance(ind, RelativeStrengthIndicator):
            ind.set_benchmark_candles(bench_candles)
        ind.calculate_series(candles)

    elapsed_s = time.perf_counter() - start_time
    elapsed_ms = elapsed_s * 1000.0
    latency_per_1k_ms = (elapsed_ms / n_candles) * 1000.0

    print(
        f"\n[BENCHMARK] Workload: {n_candles:6d} candles | "
        f"Elapsed: {elapsed_ms:8.2f} ms | "
        f"Latency per 1k: {latency_per_1k_ms:6.2f} ms"
    )

    # Informational assertion: must successfully complete without crashing
    assert elapsed_ms > 0.0
