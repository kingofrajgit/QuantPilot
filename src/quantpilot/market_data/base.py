"""Provider-independent market data abstraction layer.

Exposes canonical abstractions for querying instruments, quotes, historical candles,
and market session states.
"""

from abc import ABC, abstractmethod
from datetime import datetime

from quantpilot.market_data.models import (
    Candle,
    Instrument,
    MarketSession,
    Quote,
    Timeframe,
)


class MarketDataProvider(ABC):
    """Abstract interface defining standard market data operations."""

    @abstractmethod
    def get_instrument(self, symbol: str, exchange: str) -> Instrument | None:
        """Fetch specification for a given instrument."""
        pass

    @abstractmethod
    def get_latest_quote(self, symbol: str, exchange: str) -> Quote:
        """Fetch the latest Level 1 quote / price snapshot."""
        pass

    @abstractmethod
    def get_historical_candles(
        self,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        """Fetch historical OHLCV bars for a symbol and timeframe."""
        pass

    @abstractmethod
    def get_market_session(self, exchange: str, timestamp: datetime | None = None) -> MarketSession:
        """Retrieve market trading session status for an exchange."""
        pass
