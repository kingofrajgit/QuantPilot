"""Base abstraction and protocol for market regime classifiers."""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any

from quantpilot.market_data.models import Candle
from quantpilot.quant.models import IndicatorSeries
from quantpilot.regime.models import DimensionEvidence


class BaseClassifier(ABC):
    """Abstract base class for all single-dimension market regime classifiers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the classifier dimension."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Version of the classifier logic."""
        ...

    @property
    @abstractmethod
    def required_indicators(self) -> list[str]:
        """List of required Phase 3 indicator names."""
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """Configured parameter dictionary for provenance."""
        ...

    @abstractmethod
    def classify(
        self,
        index: int,
        candles: Sequence[Candle],
        indicators: Mapping[str, IndicatorSeries],
    ) -> tuple[Any, DimensionEvidence]:
        """Statelessly evaluate the regime state and supporting evidence at index.

        Args:
            index: Current candle index in candles/indicators series.
            candles: Sequence of canonical candles.
            indicators: Pre-computed Phase 3 indicator series.

        Returns:
            Tuple of (TypedRegimeEnum, DimensionEvidence).
        """
        ...
