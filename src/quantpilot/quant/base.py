"""Abstract base class interface for all deterministic technical indicators."""

from abc import ABC, abstractmethod
from typing import Any

from quantpilot.market_data.models import Candle
from quantpilot.quant.models import IndicatorSeries, IndicatorValue


class BaseIndicator(ABC):
    """Abstract contract for all deterministic technical indicator calculations."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Canonical registered identifier (e.g., 'sma', 'rsi')."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Indicator implementation version (e.g. '1.0.0')."""
        ...

    @property
    @abstractmethod
    def required_fields(self) -> list[str]:
        """Required Candle fields (e.g. ['close'], ['high', 'low', 'close'], ['volume'])."""
        ...

    @property
    @abstractmethod
    def minimum_observations(self) -> int:
        """Minimum candle count required to emit the first VALID output."""
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """Configured hyperparameters (e.g. {'period': 14})."""
        ...

    @abstractmethod
    def calculate_series(self, candles: list[Candle]) -> IndicatorSeries:
        """Compute indicator values across an entire chronological candle series."""
        ...

    @abstractmethod
    def calculate_point(self, candles: list[Candle]) -> IndicatorValue:
        """Compute indicator value strictly for the terminal (latest) candle."""
        ...
