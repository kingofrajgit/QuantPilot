"""Canonical Market Data package for QuantPilot."""

from quantpilot.market_data.base import MarketDataProvider
from quantpilot.market_data.mock import MockMarketDataProvider
from quantpilot.market_data.models import (
    Candle,
    DataQualityReport,
    DataQualityStatus,
    Instrument,
    MarketSession,
    Quote,
    Tick,
    Timeframe,
)
from quantpilot.market_data.validation import (
    check_staleness,
    detect_duplicates,
    detect_missing_candles,
    validate_candle,
    validate_candles,
)
from quantpilot.market_data.zerodha import ZerodhaMarketDataAdapter

__all__ = [
    "Candle",
    "DataQualityReport",
    "DataQualityStatus",
    "Instrument",
    "MarketDataProvider",
    "MarketSession",
    "MockMarketDataProvider",
    "Quote",
    "Tick",
    "Timeframe",
    "ZerodhaMarketDataAdapter",
    "check_staleness",
    "detect_duplicates",
    "detect_missing_candles",
    "validate_candle",
    "validate_candles",
]
