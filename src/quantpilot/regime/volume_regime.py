"""Deterministic volume regime classification.

States: HIGH_VOLUME, NORMAL_VOLUME, LOW_VOLUME, ACCUMULATION, DISTRIBUTION.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from quantpilot.market_data.models import Candle
from quantpilot.quant.models import IndicatorSeries, IndicatorStatus
from quantpilot.regime.base import BaseClassifier
from quantpilot.regime.models import DimensionEvidence, VolumeRegime


class VolumeClassifier(BaseClassifier):
    """Deterministic classifier for independent volume context and participation behavior.

    Consumes strictly RVOL, OBV, and candle Open/Close.
    `volume_change` is completely removed.
    """

    def __init__(
        self,
        rvol_high_threshold: float = 1.20,
        rvol_low_threshold: float = 0.80,
    ) -> None:
        if rvol_high_threshold <= 1.0:
            raise ValueError(f"rvol_high_threshold must be > 1.0, got {rvol_high_threshold}")
        if not (0.0 < rvol_low_threshold < 1.0):
            raise ValueError(f"rvol_low_threshold must be in (0.0, 1.0), got {rvol_low_threshold}")

        self._rvol_high_threshold = float(rvol_high_threshold)
        self._rvol_low_threshold = float(rvol_low_threshold)

    @property
    def name(self) -> str:
        return "volume"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_indicators(self) -> list[str]:
        return ["rvol", "obv"]

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "rvol_high_threshold": self._rvol_high_threshold,
            "rvol_low_threshold": self._rvol_low_threshold,
        }

    def classify(
        self,
        index: int,
        candles: Sequence[Candle],
        indicators: Mapping[str, IndicatorSeries],
    ) -> tuple[VolumeRegime, DimensionEvidence]:
        """Classify volume state statelessly at index."""
        rvol_ind = indicators.get("rvol")
        obv_ind = indicators.get("obv")

        if rvol_ind is None or obv_ind is None:
            return VolumeRegime.INSUFFICIENT_DATA, DimensionEvidence(
                dimension=self.name,
                state=VolumeRegime.INSUFFICIENT_DATA.value,
                contributing_metrics={},
                rationale="Missing required indicator series ('rvol' or 'obv')",
            )

        if index < 0 or index >= len(candles):
            raise IndexError(f"Index {index} out of bounds for candles length {len(candles)}")

        rvol_val = rvol_ind.values[index]
        obv_val = obv_ind.values[index]

        # Indicator-driven sufficiency check (current bar)
        if (
            rvol_val.status != IndicatorStatus.VALID
            or obv_val.status != IndicatorStatus.VALID
            or rvol_val.value is None
            or obv_val.value is None
        ):
            return VolumeRegime.INSUFFICIENT_DATA, DimensionEvidence(
                dimension=self.name,
                state=VolumeRegime.INSUFFICIENT_DATA.value,
                contributing_metrics={
                    "rvol_status": rvol_val.status.value,
                    "obv_status": obv_val.status.value,
                },
                rationale=(
                    "One or more required volume indicators have non-VALID status or None value"
                ),
            )

        # Prior OBV check for delta calculation
        if index == 0:
            return VolumeRegime.INSUFFICIENT_DATA, DimensionEvidence(
                dimension=self.name,
                state=VolumeRegime.INSUFFICIENT_DATA.value,
                contributing_metrics={"index": 0},
                rationale="OBV delta requires at least one preceding observation",
            )

        prev_obv_val = obv_ind.values[index - 1]
        if prev_obv_val.status != IndicatorStatus.VALID or prev_obv_val.value is None:
            return VolumeRegime.INSUFFICIENT_DATA, DimensionEvidence(
                dimension=self.name,
                state=VolumeRegime.INSUFFICIENT_DATA.value,
                contributing_metrics={"prev_obv_status": prev_obv_val.status.value},
                rationale="Preceding OBV value is non-VALID or None",
            )

        rvol = float(rvol_val.value)  # type: ignore[arg-type]
        obv_curr = float(obv_val.value)  # type: ignore[arg-type]
        obv_prev = float(prev_obv_val.value)  # type: ignore[arg-type]
        candle = candles[index]
        c = float(candle.close)
        o = float(candle.open)

        metrics: dict[str, float | str | None] = {
            "rvol": rvol,
            "obv": obv_curr,
            "obv_prev": obv_prev,
            "close": c,
            "open": o,
            "rvol_high_threshold": self._rvol_high_threshold,
            "rvol_low_threshold": self._rvol_low_threshold,
        }

        # Exact boolean predicates
        if rvol >= self._rvol_high_threshold and c > o and obv_curr > obv_prev:
            return VolumeRegime.ACCUMULATION, DimensionEvidence(
                dimension=self.name,
                state=VolumeRegime.ACCUMULATION.value,
                contributing_metrics=metrics,
                rationale="High relative volume with bullish candle (C > O) and increasing OBV",
            )

        if rvol >= self._rvol_high_threshold and c < o and obv_curr < obv_prev:
            return VolumeRegime.DISTRIBUTION, DimensionEvidence(
                dimension=self.name,
                state=VolumeRegime.DISTRIBUTION.value,
                contributing_metrics=metrics,
                rationale="High relative volume with bearish candle (C < O) and decreasing OBV",
            )

        if rvol >= self._rvol_high_threshold:
            return VolumeRegime.HIGH_VOLUME, DimensionEvidence(
                dimension=self.name,
                state=VolumeRegime.HIGH_VOLUME.value,
                contributing_metrics=metrics,
                rationale=(
                    "High relative volume without aligned accumulation or distribution criteria"
                ),
            )

        if rvol < self._rvol_low_threshold:
            return VolumeRegime.LOW_VOLUME, DimensionEvidence(
                dimension=self.name,
                state=VolumeRegime.LOW_VOLUME.value,
                contributing_metrics=metrics,
                rationale=f"RVOL {rvol:.2f} < low threshold {self._rvol_low_threshold:.2f}",
            )

        return VolumeRegime.NORMAL_VOLUME, DimensionEvidence(
            dimension=self.name,
            state=VolumeRegime.NORMAL_VOLUME.value,
            contributing_metrics=metrics,
            rationale=(
                f"RVOL {rvol:.2f} within normal range "
                f"[{self._rvol_low_threshold:.2f}, {self._rvol_high_threshold:.2f})"
            ),
        )
