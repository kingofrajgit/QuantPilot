"""High-level query and repository interface for historical market data."""

from datetime import datetime
from pathlib import Path

from quantpilot.market_data.historical_base import (
    HistoricalDataProvider,
    HistoricalDataStore,
    validate_historical_range,
)
from quantpilot.market_data.historical_models import HistoricalDatasetMetadata
from quantpilot.market_data.local_provider import LocalHistoricalDataProvider
from quantpilot.market_data.models import Candle, Timeframe
from quantpilot.market_data.parquet_store import ParquetHistoricalDataStore


class HistoricalDataRepository:
    """Unified query layer decoupling future backtest/quant engines from physical storage."""

    def __init__(
        self,
        store: HistoricalDataStore | None = None,
        provider: HistoricalDataProvider | None = None,
        base_path: Path | str | None = None,
    ) -> None:
        """Initialize repository with storage and optional historical provider."""
        self.store = store or ParquetHistoricalDataStore(base_path=base_path)
        self.provider = provider or LocalHistoricalDataProvider(store=self.store)

    def get_candles(
        self,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Candle]:
        """Query canonical historical candles across an optional date window.

        Args:
            symbol: Ticker symbol.
            exchange: Exchange code.
            timeframe: Aggregation timeframe.
            start: Optional starting datetime (must be timezone-aware).
            end: Optional ending datetime (must be timezone-aware).

        Returns:
            Chronologically sorted list of canonical Candle objects.
        """
        if start is not None and end is not None:
            validate_historical_range(start, end)
        elif start is not None and (start.tzinfo is None or start.tzinfo.utcoffset(start) is None):
            raise ValueError("start timestamp must be timezone-aware")
        elif end is not None and (end.tzinfo is None or end.tzinfo.utcoffset(end) is None):
            raise ValueError("end timestamp must be timezone-aware")

        return self.store.read(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            start=start,
            end=end,
        )

    def has_data(
        self,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> bool:
        """Check whether historical data is available for a series and window."""
        candles = self.get_candles(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            start=start,
            end=end,
        )
        return len(candles) > 0

    def get_metadata(
        self,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
    ) -> HistoricalDatasetMetadata | None:
        """Retrieve dataset metadata for a series."""
        return self.store.get_metadata(symbol=symbol, exchange=exchange, timeframe=timeframe)

    def list_datasets(self) -> list[HistoricalDatasetMetadata]:
        """List all datasets available in historical storage."""
        return self.store.list_datasets()

    def store_candles(self, candles: list[Candle]) -> HistoricalDatasetMetadata:
        """Ingest and validate historical candles into underlying storage."""
        return self.store.write(candles)
