"""Local historical market data provider backed by Parquet storage."""

from datetime import datetime
from pathlib import Path

from quantpilot.market_data.historical_base import (
    HistoricalDataProvider,
    HistoricalDataStore,
    validate_historical_range,
)
from quantpilot.market_data.models import Candle, Timeframe
from quantpilot.market_data.parquet_store import ParquetHistoricalDataStore


class LocalHistoricalDataProvider(HistoricalDataProvider):
    """Offline historical data provider loading canonical candles from local storage."""

    def __init__(
        self,
        store: HistoricalDataStore | None = None,
        base_path: Path | str | None = None,
    ) -> None:
        """Initialize local provider backed by an explicit or default Parquet store."""
        if store is not None:
            self.store = store
        else:
            self.store = ParquetHistoricalDataStore(base_path=base_path)

    def get_historical_candles(
        self,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        """Fetch historical candles from local storage within [start, end].

        Validates timestamp bounds, ensures UTC comparison, and returns canonical Candle objects.
        """
        validate_historical_range(start, end)
        return self.store.read(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            start=start,
            end=end,
        )
