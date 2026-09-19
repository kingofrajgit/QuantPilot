"""Integration tests connecting Parquet store, HistoricalDataRepository, and QuantEngine."""

from pathlib import Path

from quantpilot.market_data.models import Timeframe
from quantpilot.market_data.parquet_store import ParquetHistoricalDataStore
from quantpilot.market_data.repository import HistoricalDataRepository
from quantpilot.quant.engine import QuantEngine
from quantpilot.quant.models import IndicatorStatus
from tests.unit.quant.conftest import make_candle_sequence


def test_quant_engine_repository_integration(tmp_path: Path) -> None:
    """End-to-end integration: store in Parquet, query via repo, compute indicators."""
    store = ParquetHistoricalDataStore(base_path=tmp_path / "historical")
    repo = HistoricalDataRepository(store=store)
    engine = QuantEngine(repository=repo)

    candles = make_candle_sequence(50, symbol="INFY", exchange="NSE", timeframe=Timeframe.D1)
    store.write(candles)

    results = engine.compute(
        symbol="INFY",
        exchange="NSE",
        timeframe=Timeframe.D1,
        indicators=["sma", "rsi", "bollinger_bands", "atr"],
    )

    assert "sma" in results
    assert "rsi" in results
    assert "bollinger_bands" in results
    assert "atr" in results

    sma_series = results["sma"]
    assert len(sma_series.values) == 50
    assert sma_series.values[-1].status == IndicatorStatus.VALID
    assert sma_series.values[-1].value is not None
    assert sma_series.values[-1].provenance.indicator_name == "sma"
    assert sma_series.values[-1].provenance.candles_analyzed == 50

    bb_series = results["bollinger_bands"]
    assert bb_series.values[-1].status == IndicatorStatus.VALID
    bb_val = bb_series.values[-1].value
    assert isinstance(bb_val, dict)
    assert "middle" in bb_val
    assert "upper" in bb_val
    assert "lower" in bb_val
    assert "bandwidth" in bb_val
    assert "percent_b" in bb_val
