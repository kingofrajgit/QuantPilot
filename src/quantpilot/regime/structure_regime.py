"""Deterministic market structure classification.

States: BREAKOUT, BREAKDOWN, CONSOLIDATION, TRENDING, RANGING.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from quantpilot.market_data.models import Candle
from quantpilot.quant.models import IndicatorSeries, IndicatorStatus
from quantpilot.regime.base import BaseClassifier
from quantpilot.regime.models import DimensionEvidence, MarketStructure


class StructureClassifier(BaseClassifier):
    """Deterministic classifier for geometric price structure regimes.

    Preserves strict anti-lookahead current-candle exclusion via structure_breakout_distance.
    Decoupled from volume.
    """

    def __init__(
        self,
        trend_channel_proximity: float = 0.020,
        bbw_consolidation_threshold: float = 0.030,
    ) -> None:
        if trend_channel_proximity <= 0.0:
            raise ValueError(
                f"trend_channel_proximity must be > 0.0, got {trend_channel_proximity}"
            )
        if bbw_consolidation_threshold <= 0.0:
            raise ValueError(
                f"bbw_consolidation_threshold must be > 0.0, got {bbw_consolidation_threshold}"
            )

        self._trend_channel_proximity = float(trend_channel_proximity)
        self._bbw_consolidation_threshold = float(bbw_consolidation_threshold)

    @property
    def name(self) -> str:
        return "structure"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_indicators(self) -> list[str]:
        return [
            "structure_breakout_distance",
            "bollinger_bands",
            "sma",
            "sma_slope",
            "ema_slope",
        ]

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "trend_channel_proximity": self._trend_channel_proximity,
            "bbw_consolidation_threshold": self._bbw_consolidation_threshold,
        }

    def classify(
        self,
        index: int,
        candles: Sequence[Candle],
        indicators: Mapping[str, IndicatorSeries],
    ) -> tuple[MarketStructure, DimensionEvidence]:
        """Classify market structure state statelessly at index."""
        sbd_ind = indicators.get("structure_breakout_distance")
        bb_ind = indicators.get("bollinger_bands")
        sma_ind = indicators.get("sma")
        sma_slope_ind = indicators.get("sma_slope")
        ema_slope_ind = indicators.get("ema_slope")

        if (
            sbd_ind is None
            or bb_ind is None
            or sma_ind is None
            or sma_slope_ind is None
            or ema_slope_ind is None
        ):
            return MarketStructure.INSUFFICIENT_DATA, DimensionEvidence(
                dimension=self.name,
                state=MarketStructure.INSUFFICIENT_DATA.value,
                contributing_metrics={},
                rationale="Missing required indicator series for structure classification",
            )

        if index < 0 or index >= len(candles):
            raise IndexError(f"Index {index} out of bounds for candles length {len(candles)}")

        sbd_val = sbd_ind.values[index]
        bb_val = bb_ind.values[index]
        sma_val = sma_ind.values[index]
        sma_slope_val = sma_slope_ind.values[index]
        ema_slope_val = ema_slope_ind.values[index]

        # Indicator-driven sufficiency check
        if (
            sbd_val.status != IndicatorStatus.VALID
            or bb_val.status != IndicatorStatus.VALID
            or sma_val.status != IndicatorStatus.VALID
            or sma_slope_val.status != IndicatorStatus.VALID
            or ema_slope_val.status != IndicatorStatus.VALID
            or sbd_val.value is None
            or bb_val.value is None
            or sma_val.value is None
            or sma_slope_val.value is None
            or ema_slope_val.value is None
            or not isinstance(sbd_val.value, dict)
            or not isinstance(bb_val.value, dict)
            or "breakout_high" not in sbd_val.value
            or "breakdown_low" not in sbd_val.value
            or "dist_high" not in sbd_val.value
            or "dist_low" not in sbd_val.value
            or "bandwidth" not in bb_val.value
        ):
            return MarketStructure.INSUFFICIENT_DATA, DimensionEvidence(
                dimension=self.name,
                state=MarketStructure.INSUFFICIENT_DATA.value,
                contributing_metrics={
                    "structure_breakout_distance_status": sbd_val.status.value,
                    "bollinger_bands_status": bb_val.status.value,
                    "sma_status": sma_val.status.value,
                    "sma_slope_status": sma_slope_val.status.value,
                    "ema_slope_status": ema_slope_val.status.value,
                },
                rationale=(
                    "One or more required structure indicators have non-VALID status or None value"
                ),
            )

        breakout_high = float(sbd_val.value["breakout_high"])
        breakdown_low = float(sbd_val.value["breakdown_low"])
        dist_high = float(sbd_val.value["dist_high"])
        dist_low = float(sbd_val.value["dist_low"])
        bandwidth = float(bb_val.value["bandwidth"])
        sma_num = float(sma_val.value)  # type: ignore[arg-type]
        sma_slope_num = float(sma_slope_val.value)  # type: ignore[arg-type]
        ema_slope_num = float(ema_slope_val.value)  # type: ignore[arg-type]
        close = float(candles[index].close)

        metrics: dict[str, float | str | None] = {
            "breakout_high": breakout_high,
            "breakdown_low": breakdown_low,
            "dist_high": dist_high,
            "dist_low": dist_low,
            "bandwidth": bandwidth,
            "sma": sma_num,
            "sma_slope": sma_slope_num,
            "ema_slope": ema_slope_num,
            "close": close,
            "trend_channel_proximity": self._trend_channel_proximity,
            "bbw_consolidation_threshold": self._bbw_consolidation_threshold,
        }

        # Exact Precedence Sequence:
        # 1. BREAKOUT
        if breakout_high == 1.0:
            return MarketStructure.BREAKOUT, DimensionEvidence(
                dimension=self.name,
                state=MarketStructure.BREAKOUT.value,
                contributing_metrics=metrics,
                rationale="Close exceeded prior rolling high channel",
            )

        # 2. BREAKDOWN
        if breakdown_low == 1.0:
            return MarketStructure.BREAKDOWN, DimensionEvidence(
                dimension=self.name,
                state=MarketStructure.BREAKDOWN.value,
                contributing_metrics=metrics,
                rationale="Close broke below prior rolling low channel",
            )

        # 3. CONSOLIDATION
        if bandwidth <= self._bbw_consolidation_threshold:
            return MarketStructure.CONSOLIDATION, DimensionEvidence(
                dimension=self.name,
                state=MarketStructure.CONSOLIDATION.value,
                contributing_metrics=metrics,
                rationale=(
                    f"Bollinger bandwidth {bandwidth:.4f} <= consolidation "
                    f"threshold {self._bbw_consolidation_threshold:.4f}"
                ),
            )

        # 4. TRENDING
        bullish_trending = (
            dist_high >= (-self._trend_channel_proximity * 100.0)
            and close > sma_num
            and sma_slope_num > 0.0
            and ema_slope_num > 0.0
        )
        bearish_trending = (
            dist_low <= (self._trend_channel_proximity * 100.0)
            and close < sma_num
            and sma_slope_num < 0.0
            and ema_slope_num < 0.0
        )

        if bullish_trending or bearish_trending:
            rationale = (
                "Bullish channel proximity with positive moving average alignment"
                if bullish_trending
                else "Bearish channel proximity with negative moving average alignment"
            )
            return MarketStructure.TRENDING, DimensionEvidence(
                dimension=self.name,
                state=MarketStructure.TRENDING.value,
                contributing_metrics=metrics,
                rationale=rationale,
            )

        # 5. RANGING
        return MarketStructure.RANGING, DimensionEvidence(
            dimension=self.name,
            state=MarketStructure.RANGING.value,
            contributing_metrics=metrics,
            rationale=(
                "Price oscillating within structured range without breakout, "
                "consolidation compression, or directional trend expansion"
            ),
        )
