"""Canonical Market Data package for QuantPilot."""

from quantpilot.market_data.base import MarketDataProvider
from quantpilot.market_data.historical_base import (
    HistoricalDataProvider,
    HistoricalDataStore,
    validate_historical_range,
)
from quantpilot.market_data.historical_models import HistoricalDatasetMetadata
from quantpilot.market_data.local_provider import LocalHistoricalDataProvider
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
from quantpilot.market_data.parquet_store import ParquetHistoricalDataStore
from quantpilot.market_data.repository import HistoricalDataRepository
from quantpilot.market_data.validation import (
    check_staleness,
    detect_duplicates,
    detect_missing_candles,
    validate_candle,
    validate_candles,
)
from quantpilot.market_data.zerodha import ZerodhaMarketDataAdapter
from quantpilot.market_data.zerodha_historical import ZerodhaHistoricalDataProvider

__all__ = [
    "Candle",
    "DataQualityReport",
    "DataQualityStatus",
    "HistoricalDataProvider",
    "HistoricalDataRepository",
    "HistoricalDataStore",
    "HistoricalDatasetMetadata",
    "Instrument",
    "LocalHistoricalDataProvider",
    "MarketDataProvider",
    "MarketSession",
    "MockMarketDataProvider",
    "ParquetHistoricalDataStore",
    "Quote",
    "Tick",
    "Timeframe",
    "ZerodhaHistoricalDataProvider",
    "ZerodhaMarketDataAdapter",
    "check_staleness",
    "detect_duplicates",
    "detect_missing_candles",
    "validate_candle",
    "validate_candles",
    "validate_historical_range",
]
