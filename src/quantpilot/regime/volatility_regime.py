"""Deterministic volatility regime classification: LOW, NORMAL, HIGH."""

from collections.abc import Mapping, Sequence
from typing import Any

from quantpilot.market_data.models import Candle
from quantpilot.quant.models import IndicatorSeries, IndicatorStatus
from quantpilot.regime.base import BaseClassifier
from quantpilot.regime.models import DimensionEvidence, VolatilityRegime


class VolatilityClassifier(BaseClassifier):
    """Deterministic classifier for volatility regimes using Bollinger Bandwidth.

    NATR is completely removed. Volatility classification is purely based on bandwidth.
    """

    def __init__(
        self,
        bbw_low_threshold: float = 0.030,
        bbw_high_threshold: float = 0.080,
    ) -> None:
        if bbw_low_threshold <= 0.0:
            raise ValueError(f"bbw_low_threshold must be > 0.0, got {bbw_low_threshold}")
        if bbw_high_threshold <= bbw_low_threshold:
            raise ValueError(
                f"bbw_high_threshold ({bbw_high_threshold}) must be > "
                f"bbw_low_threshold ({bbw_low_threshold})"
            )

        self._bbw_low_threshold = float(bbw_low_threshold)
        self._bbw_high_threshold = float(bbw_high_threshold)

    @property
    def name(self) -> str:
        return "volatility"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_indicators(self) -> list[str]:
        return ["bollinger_bands"]

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "bbw_low_threshold": self._bbw_low_threshold,
            "bbw_high_threshold": self._bbw_high_threshold,
        }

    def classify(
        self,
        index: int,
        candles: Sequence[Candle],
        indicators: Mapping[str, IndicatorSeries],
    ) -> tuple[VolatilityRegime, DimensionEvidence]:
        """Classify volatility state statelessly at index."""
        bb_ind = indicators.get("bollinger_bands")

        if bb_ind is None:
            return VolatilityRegime.INSUFFICIENT_DATA, DimensionEvidence(
                dimension=self.name,
                state=VolatilityRegime.INSUFFICIENT_DATA.value,
                contributing_metrics={},
                rationale="Missing required indicator series 'bollinger_bands'",
            )

        if index < 0 or index >= len(candles):
            raise IndexError(f"Index {index} out of bounds for candles length {len(candles)}")

        bb_val = bb_ind.values[index]

        # Indicator-driven sufficiency check
        if (
            bb_val.status != IndicatorStatus.VALID
            or bb_val.value is None
            or not isinstance(bb_val.value, dict)
            or "bandwidth" not in bb_val.value
        ):
            return VolatilityRegime.INSUFFICIENT_DATA, DimensionEvidence(
                dimension=self.name,
                state=VolatilityRegime.INSUFFICIENT_DATA.value,
                contributing_metrics={"bollinger_bands_status": bb_val.status.value},
                rationale="Bollinger bands indicator has non-VALID status or missing bandwidth",
            )

        b = float(bb_val.value["bandwidth"])

        metrics: dict[str, float | str | None] = {
            "bandwidth": b,
            "bbw_low_threshold": self._bbw_low_threshold,
            "bbw_high_threshold": self._bbw_high_threshold,
        }

        # Exact boolean predicates
        if b < self._bbw_low_threshold:
            return VolatilityRegime.LOW, DimensionEvidence(
                dimension=self.name,
                state=VolatilityRegime.LOW.value,
                contributing_metrics=metrics,
                rationale=(
                    f"Bollinger bandwidth {b:.4f} < low threshold {self._bbw_low_threshold:.4f}"
                ),
            )

        if b > self._bbw_high_threshold:
            return VolatilityRegime.HIGH, DimensionEvidence(
                dimension=self.name,
                state=VolatilityRegime.HIGH.value,
                contributing_metrics=metrics,
                rationale=(
                    f"Bollinger bandwidth {b:.4f} > high threshold {self._bbw_high_threshold:.4f}"
                ),
            )

        return VolatilityRegime.NORMAL, DimensionEvidence(
            dimension=self.name,
            state=VolatilityRegime.NORMAL.value,
            contributing_metrics=metrics,
            rationale=(
                f"Bollinger bandwidth {b:.4f} within normal range "
                f"[{self._bbw_low_threshold:.4f}, {self._bbw_high_threshold:.4f}]"
            ),
        )
