"""Zerodha historical market data provider architectural boundary."""

from datetime import datetime

from quantpilot.config.settings import Settings, get_settings
from quantpilot.market_data.historical_base import HistoricalDataProvider
from quantpilot.market_data.models import Candle, Timeframe


class ZerodhaHistoricalDataProvider(HistoricalDataProvider):
    """Adapter boundary for future Zerodha Kite historical candle retrieval.

    Phase 2B Security & Scope Constraint:
    Does NOT require credentials on import or instantiation.
    Does NOT perform network calls or connect to KiteConnect.
    Retrieval raises NotImplementedError.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize adapter boundary without requiring active credentials or network access."""
        self.settings = settings or get_settings()

    def get_historical_candles(
        self,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        """Fetch historical candles from Zerodha Kite (deferred to future phase)."""
        raise NotImplementedError(
            "Live Zerodha historical data retrieval is strictly deferred "
            "to a future approved phase."
        )
