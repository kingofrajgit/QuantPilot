"""Zerodha market data adapter boundary for QuantPilot.

CRITICAL ARCHITECTURAL BOUNDARY:
This class serves strictly as an architectural interface placeholder for future
Kite Connect integration.
No network calls, KiteConnect instantiations, REST endpoints, or WebSocket streams
are permitted in Phase 2A.
"""

from datetime import datetime

from quantpilot.config.settings import Settings, get_settings
from quantpilot.market_data.base import MarketDataProvider
from quantpilot.market_data.models import (
    Candle,
    Instrument,
    MarketSession,
    Quote,
    Timeframe,
)


class ZerodhaMarketDataAdapter(MarketDataProvider):
    """Adapter boundary for future Zerodha Kite market data ingestion.

    Phase 2A Constraint:
    Every retrieval operation raises NotImplementedError.
    Does not require Zerodha credentials on import or construction.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize adapter boundary without opening network sockets or validating keys."""
        self.settings = settings or get_settings()

    def get_instrument(self, symbol: str, exchange: str) -> Instrument | None:
        """Retrieve instrument definition from Zerodha."""
        raise NotImplementedError(
            "Live Zerodha market data ingestion is not implemented in Phase 2A."
        )

    def get_latest_quote(self, symbol: str, exchange: str) -> Quote:
        """Retrieve latest quote snapshot from Zerodha."""
        raise NotImplementedError(
            "Live Zerodha market data ingestion is not implemented in Phase 2A."
        )

    def get_historical_candles(
        self,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        """Retrieve historical candles from Zerodha Kite."""
        raise NotImplementedError(
            "Live Zerodha market data ingestion is not implemented in Phase 2A."
        )

    def get_market_session(self, exchange: str, timestamp: datetime | None = None) -> MarketSession:
        """Retrieve market session status from Zerodha."""
        raise NotImplementedError(
            "Live Zerodha market data ingestion is not implemented in Phase 2A."
        )
