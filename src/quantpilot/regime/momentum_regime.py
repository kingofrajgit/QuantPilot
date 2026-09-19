"""Deterministic momentum regime classification: POSITIVE, NEGATIVE, NEUTRAL."""

from collections.abc import Mapping, Sequence
from typing import Any

from quantpilot.market_data.models import Candle
from quantpilot.quant.models import IndicatorSeries, IndicatorStatus
from quantpilot.regime.base import BaseClassifier
from quantpilot.regime.models import DimensionEvidence, MomentumRegime


class MomentumClassifier(BaseClassifier):
    """Deterministic classifier for momentum regimes.

    Evaluates agreement across RSI, ROC, and MACD Histogram.
    """

    def __init__(
        self,
        rsi_bullish_bound: float = 55.0,
        rsi_bearish_bound: float = 45.0,
    ) -> None:
        if not (50.0 < rsi_bullish_bound <= 100.0):
            raise ValueError(f"rsi_bullish_bound must be in (50.0, 100.0], got {rsi_bullish_bound}")
        if not (0.0 <= rsi_bearish_bound < 50.0):
            raise ValueError(f"rsi_bearish_bound must be in [0.0, 50.0), got {rsi_bearish_bound}")

        self._rsi_bullish_bound = float(rsi_bullish_bound)
        self._rsi_bearish_bound = float(rsi_bearish_bound)

    @property
    def name(self) -> str:
        return "momentum"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_indicators(self) -> list[str]:
        return ["rsi", "roc", "macd"]

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "rsi_bullish_bound": self._rsi_bullish_bound,
            "rsi_bearish_bound": self._rsi_bearish_bound,
        }

    def classify(
        self,
        index: int,
        candles: Sequence[Candle],
        indicators: Mapping[str, IndicatorSeries],
    ) -> tuple[MomentumRegime, DimensionEvidence]:
        """Classify momentum state statelessly at index."""
        rsi_ind = indicators.get("rsi")
        roc_ind = indicators.get("roc")
        macd_ind = indicators.get("macd")

        if rsi_ind is None or roc_ind is None or macd_ind is None:
            return MomentumRegime.INSUFFICIENT_DATA, DimensionEvidence(
                dimension=self.name,
                state=MomentumRegime.INSUFFICIENT_DATA.value,
                contributing_metrics={},
                rationale="Missing required indicator series for momentum classification",
            )

        if index < 0 or index >= len(candles):
            raise IndexError(f"Index {index} out of bounds for candles length {len(candles)}")

        rsi_val = rsi_ind.values[index]
        roc_val = roc_ind.values[index]
        macd_val = macd_ind.values[index]

        # Indicator-driven sufficiency check
        if (
            rsi_val.status != IndicatorStatus.VALID
            or roc_val.status != IndicatorStatus.VALID
            or macd_val.status != IndicatorStatus.VALID
            or rsi_val.value is None
            or roc_val.value is None
            or macd_val.value is None
            or not isinstance(macd_val.value, dict)
            or "histogram" not in macd_val.value
        ):
            return MomentumRegime.INSUFFICIENT_DATA, DimensionEvidence(
                dimension=self.name,
                state=MomentumRegime.INSUFFICIENT_DATA.value,
                contributing_metrics={
                    "rsi_status": rsi_val.status.value,
                    "roc_status": roc_val.status.value,
                    "macd_status": macd_val.status.value,
                },
                rationale=(
                    "One or more required momentum indicators have non-VALID status or None value"
                ),
            )

        r = float(rsi_val.value)  # type: ignore[arg-type]
        roc_num = float(roc_val.value)  # type: ignore[arg-type]
        h = float(macd_val.value["histogram"])

        metrics: dict[str, float | str | None] = {
            "rsi": r,
            "roc": roc_num,
            "macd_histogram": h,
            "rsi_bullish_bound": self._rsi_bullish_bound,
            "rsi_bearish_bound": self._rsi_bearish_bound,
        }

        # Exact boolean predicates
        if r >= self._rsi_bullish_bound and roc_num > 0.0 and h > 0.0:
            return MomentumRegime.POSITIVE, DimensionEvidence(
                dimension=self.name,
                state=MomentumRegime.POSITIVE.value,
                contributing_metrics=metrics,
                rationale="RSI above bullish bound, positive ROC, and positive MACD histogram",
            )

        if r <= self._rsi_bearish_bound and roc_num < 0.0 and h < 0.0:
            return MomentumRegime.NEGATIVE, DimensionEvidence(
                dimension=self.name,
                state=MomentumRegime.NEGATIVE.value,
                contributing_metrics=metrics,
                rationale="RSI below bearish bound, negative ROC, and negative MACD histogram",
            )

        return MomentumRegime.NEUTRAL, DimensionEvidence(
            dimension=self.name,
            state=MomentumRegime.NEUTRAL.value,
            contributing_metrics=metrics,
            rationale="Momentum indicators do not demonstrate unified directional velocity",
        )
