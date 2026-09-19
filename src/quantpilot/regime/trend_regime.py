"""Deterministic trend regime classification: BULLISH, BEARISH, SIDEWAYS."""

from collections.abc import Mapping, Sequence
from typing import Any

from quantpilot.market_data.models import Candle
from quantpilot.quant.models import IndicatorSeries, IndicatorStatus
from quantpilot.regime.base import BaseClassifier
from quantpilot.regime.models import DimensionEvidence, TrendRegime


class TrendClassifier(BaseClassifier):
    """Deterministic classifier for directional trend regimes.

    Evaluates price position relative to SMA and dual moving average slopes (SMA and EMA).
    """

    def __init__(
        self,
        slope_threshold: float = 0.0,
        distance_threshold: float = 0.005,
    ) -> None:
        if slope_threshold < 0.0:
            raise ValueError(f"slope_threshold must be >= 0.0, got {slope_threshold}")
        if distance_threshold <= 0.0:
            raise ValueError(f"distance_threshold must be > 0.0, got {distance_threshold}")

        self._slope_threshold = float(slope_threshold)
        self._distance_threshold = float(distance_threshold)

    @property
    def name(self) -> str:
        return "trend"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_indicators(self) -> list[str]:
        return ["price_vs_sma", "sma_slope", "ema_slope"]

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "slope_threshold": self._slope_threshold,
            "distance_threshold": self._distance_threshold,
        }

    def classify(
        self,
        index: int,
        candles: Sequence[Candle],
        indicators: Mapping[str, IndicatorSeries],
    ) -> tuple[TrendRegime, DimensionEvidence]:
        """Classify trend state statelessly at index."""
        p_ind = indicators.get("price_vs_sma")
        s_ind = indicators.get("sma_slope")
        e_ind = indicators.get("ema_slope")

        if p_ind is None or s_ind is None or e_ind is None:
            return TrendRegime.INSUFFICIENT_DATA, DimensionEvidence(
                dimension=self.name,
                state=TrendRegime.INSUFFICIENT_DATA.value,
                contributing_metrics={},
                rationale="Missing required indicator series for trend classification",
            )

        if index < 0 or index >= len(candles):
            raise IndexError(f"Index {index} out of bounds for candles length {len(candles)}")

        p_val = p_ind.values[index]
        s_val = s_ind.values[index]
        e_val = e_ind.values[index]

        # Indicator-driven sufficiency check
        if (
            p_val.status != IndicatorStatus.VALID
            or s_val.status != IndicatorStatus.VALID
            or e_val.status != IndicatorStatus.VALID
            or p_val.value is None
            or s_val.value is None
            or e_val.value is None
        ):
            return TrendRegime.INSUFFICIENT_DATA, DimensionEvidence(
                dimension=self.name,
                state=TrendRegime.INSUFFICIENT_DATA.value,
                contributing_metrics={
                    "price_vs_sma_status": p_val.status.value,
                    "sma_slope_status": s_val.status.value,
                    "ema_slope_status": e_val.status.value,
                },
                rationale=(
                    "One or more required trend indicators have non-VALID status or None value"
                ),
            )

        p = float(p_val.value)  # type: ignore[arg-type]
        s = float(s_val.value)  # type: ignore[arg-type]
        e = float(e_val.value)  # type: ignore[arg-type]

        metrics: dict[str, float | str | None] = {
            "price_vs_sma": p,
            "sma_slope": s,
            "ema_slope": e,
            "distance_threshold": self._distance_threshold,
            "slope_threshold": self._slope_threshold,
        }

        # Exact boolean predicates
        if p > self._distance_threshold and s > self._slope_threshold and e > self._slope_threshold:
            return TrendRegime.BULLISH, DimensionEvidence(
                dimension=self.name,
                state=TrendRegime.BULLISH.value,
                contributing_metrics=metrics,
                rationale="Price is above SMA threshold with positive SMA and EMA slopes",
            )

        if (
            p < -self._distance_threshold
            and s < -self._slope_threshold
            and e < -self._slope_threshold
        ):
            return TrendRegime.BEARISH, DimensionEvidence(
                dimension=self.name,
                state=TrendRegime.BEARISH.value,
                contributing_metrics=metrics,
                rationale="Price is below SMA threshold with negative SMA and EMA slopes",
            )

        return TrendRegime.SIDEWAYS, DimensionEvidence(
            dimension=self.name,
            state=TrendRegime.SIDEWAYS.value,
            contributing_metrics=metrics,
            rationale="Price or slopes do not satisfy directional bullish or bearish thresholds",
        )
