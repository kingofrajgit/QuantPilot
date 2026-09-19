"""Integration test connecting:

ParquetStore -> HistoricalDataRepository -> QuantEngine -> RegimeEngine.
"""

from pathlib import Path

from quantpilot.market_data.models import Timeframe
from quantpilot.market_data.parquet_store import ParquetHistoricalDataStore
from quantpilot.market_data.repository import HistoricalDataRepository
from quantpilot.quant.engine import QuantEngine
from quantpilot.regime.engine import RegimeEngine
from quantpilot.regime.models import CompositeRegime
from tests.unit.quant.conftest import make_candle_sequence


def test_regime_pipeline_integration(tmp_path: Path) -> None:
    """End-to-end pipeline: persist candles, compute quant indicators, evaluate market regimes."""
    store = ParquetHistoricalDataStore(base_path=tmp_path / "historical")
    repo = HistoricalDataRepository(store=store)
    quant_engine = QuantEngine(repository=repo)
    regime_engine = RegimeEngine()

    candles = make_candle_sequence(
        60,
        symbol="TCS",
        exchange="NSE",
        timeframe=Timeframe.D1,
        base_price=3000.0,
        volume=50000.0,
    )
    store.write(candles)

    # 1. Fetch candles via repository
    fetched_candles = repo.get_candles(symbol="TCS", exchange="NSE", timeframe=Timeframe.D1)
    assert len(fetched_candles) == 60

    # 2. Compute all 11 indicators required by RegimeEngine via QuantEngine
    indicators = quant_engine.compute(
        symbol="TCS",
        exchange="NSE",
        timeframe=Timeframe.D1,
        indicators=list(RegimeEngine.REQUIRED_INDICATORS),
    )

    for req in RegimeEngine.REQUIRED_INDICATORS:
        assert req in indicators
        assert len(indicators[req].values) == 60

    # 3. Evaluate market regimes statelessly via RegimeEngine
    context_series = regime_engine.evaluate(fetched_candles, indicators)

    assert context_series.symbol == "TCS"
    assert context_series.exchange == "NSE"
    assert context_series.timeframe == Timeframe.D1
    assert len(context_series.values) == 60

    # Verify warmup vs valid behavior:
    # First candle has index 0 (OBV delta, SMA 20, etc are insufficient)
    first_ctx = context_series.values[0]
    assert first_ctx.composite_regime == CompositeRegime.INSUFFICIENT_DATA

    # Terminal candle has 60 observations (well past lookbacks of 20 and 34)
    last_ctx = context_series.values[-1]
    assert last_ctx.composite_regime != CompositeRegime.INSUFFICIENT_DATA
    assert last_ctx.evidence["trend"].state in ("BULLISH", "BEARISH", "SIDEWAYS")
    assert last_ctx.evidence["momentum"].state in ("POSITIVE", "NEGATIVE", "NEUTRAL")
    assert last_ctx.evidence["volatility"].state in ("LOW", "NORMAL", "HIGH")
    assert last_ctx.evidence["volume"].state in (
        "HIGH_VOLUME",
        "NORMAL_VOLUME",
        "LOW_VOLUME",
        "ACCUMULATION",
        "DISTRIBUTION",
    )
    assert last_ctx.evidence["structure"].state in (
        "BREAKOUT",
        "BREAKDOWN",
        "CONSOLIDATION",
        "TRENDING",
        "RANGING",
    )
    assert len(last_ctx.evidence) == 6
    assert last_ctx.provenance.candles_evaluated == 60
