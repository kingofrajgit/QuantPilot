"""Provider and storage abstraction layer for historical market data."""

from abc import ABC, abstractmethod
from datetime import datetime

from quantpilot.market_data.historical_models import HistoricalDatasetMetadata
from quantpilot.market_data.models import Candle, Timeframe


def validate_historical_range(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    """Validate query timestamp bounds.

    Rejects naive datetimes and ensures start <= end.
    Returns normalized UTC timestamps.
    """
    if not isinstance(start, datetime) or not isinstance(end, datetime):
        raise ValueError("start and end must be datetime instances")

    if start.tzinfo is None or start.tzinfo.utcoffset(start) is None:
        raise ValueError("start timestamp must be timezone-aware")
    if end.tzinfo is None or end.tzinfo.utcoffset(end) is None:
        raise ValueError("end timestamp must be timezone-aware")

    if start > end:
        raise ValueError(
            f"start timestamp ({start.isoformat()}) must be less than or equal to "
            f"end timestamp ({end.isoformat()})"
        )

    return start, end


class HistoricalDataProvider(ABC):
    """Abstract interface for historical candle data providers."""

    @abstractmethod
    def get_historical_candles(
        self,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        """Fetch historical candles within [start, end] window.

        Args:
            symbol: Ticker symbol.
            exchange: Exchange code.
            timeframe: Bar aggregation period.
            start: Timezone-aware starting timestamp.
            end: Timezone-aware ending timestamp.

        Returns:
            Chronologically sorted list of canonical Candle objects.
            Returns empty list if no records exist in the range.

        Raises:
            ValueError: On naive timestamps or start > end.
            DataStorageError: On retrieval failures.
        """
        pass


class HistoricalDataStore(ABC):
    """Abstract interface for local historical market data persistence."""

    @abstractmethod
    def write(self, candles: list[Candle]) -> HistoricalDatasetMetadata:
        """Store a batch of validated historical candles.

        Must enforce Phase 2A data quality validation, idempotency for identical records,
        and conflict detection for differing values on the same canonical key.

        Returns:
            Updated HistoricalDatasetMetadata for the series.

        Raises:
            ValueError: If candle list is empty.
            DataValidationError: If candles fail Phase 2A validation.
            DataConflictError: If new candle conflicts with existing stored candle for the same key.
            DataStorageError: On I/O or filesystem failures.
        """
        pass

    @abstractmethod
    def read(
        self,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Candle]:
        """Read historical candles for a specific series and optional date range.

        Returns:
            Chronologically sorted list of canonical Candle objects.
        """
        pass

    @abstractmethod
    def exists(self, symbol: str, exchange: str, timeframe: Timeframe) -> bool:
        """Check whether historical data exists for the given series."""
        pass

    @abstractmethod
    def get_metadata(
        self, symbol: str, exchange: str, timeframe: Timeframe
    ) -> HistoricalDatasetMetadata | None:
        """Retrieve dataset metadata for a series if it exists."""
        pass

    @abstractmethod
    def list_datasets(self) -> list[HistoricalDatasetMetadata]:
        """List metadata for all stored historical datasets."""
        pass

    @abstractmethod
    def delete(self, symbol: str, exchange: str, timeframe: Timeframe) -> bool:
        """Delete stored historical dataset for a series. Returns True if deleted."""
        pass
