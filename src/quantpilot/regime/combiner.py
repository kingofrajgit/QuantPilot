"""Deterministic composite regime synthesis using the approved Revision 3 precedence matrix."""

from quantpilot.regime.models import (
    CompositeRegime,
    DimensionEvidence,
    MarketStructure,
    MomentumRegime,
    TrendRegime,
    VolatilityRegime,
)


class RegimeCombiner:
    """Evaluates multi-dimensional evidence into a single raw CompositeRegime.

    Precedence is strictly sequential (Steps 1 through 8). Zero weights, zero hidden scoring.
    """

    def combine(
        self,
        trend: TrendRegime,
        momentum: MomentumRegime,
        volatility: VolatilityRegime,
        structure: MarketStructure,
    ) -> tuple[CompositeRegime, DimensionEvidence]:
        """Synthesize composite regime according to the strict 8-step precedence matrix."""
        metrics: dict[str, float | str | None] = {
            "trend": trend.value,
            "momentum": momentum.value,
            "volatility": volatility.value,
            "structure": structure.value,
        }

        # Step 1: Insufficient Evidence
        if (
            trend == TrendRegime.INSUFFICIENT_DATA
            or momentum == MomentumRegime.INSUFFICIENT_DATA
            or volatility == VolatilityRegime.INSUFFICIENT_DATA
            or structure == MarketStructure.INSUFFICIENT_DATA
        ):
            return CompositeRegime.INSUFFICIENT_DATA, DimensionEvidence(
                dimension="composite",
                state=CompositeRegime.INSUFFICIENT_DATA.value,
                contributing_metrics=metrics,
                rationale="One or more required composite dimensions have INSUFFICIENT_DATA",
            )

        # Step 2: Directional Divergence (Conflict Detection)
        if (trend == TrendRegime.BULLISH and momentum == MomentumRegime.NEGATIVE) or (
            trend == TrendRegime.BEARISH and momentum == MomentumRegime.POSITIVE
        ):
            return CompositeRegime.DIVERGENT, DimensionEvidence(
                dimension="composite",
                state=CompositeRegime.DIVERGENT.value,
                contributing_metrics=metrics,
                rationale=(
                    f"Directional divergence detected: Trend is {trend.value} "
                    f"while Momentum is {momentum.value}"
                ),
            )

        # Step 3: Volatile Unstructured
        if volatility == VolatilityRegime.HIGH and structure == MarketStructure.RANGING:
            return CompositeRegime.VOLATILE_UNSTRUCTURED, DimensionEvidence(
                dimension="composite",
                state=CompositeRegime.VOLATILE_UNSTRUCTURED.value,
                contributing_metrics=metrics,
                rationale="High volatility observed within unstructured ranging price action",
            )

        # Step 4: Directional Trending Expansion
        if (
            trend == TrendRegime.BULLISH
            and momentum == MomentumRegime.POSITIVE
            and structure in (MarketStructure.BREAKOUT, MarketStructure.TRENDING)
        ):
            return CompositeRegime.BULLISH_TRENDING_EXPANSION, DimensionEvidence(
                dimension="composite",
                state=CompositeRegime.BULLISH_TRENDING_EXPANSION.value,
                contributing_metrics=metrics,
                rationale=(
                    f"Bullish trend and positive momentum aligned with {structure.value} structure"
                ),
            )

        if (
            trend == TrendRegime.BEARISH
            and momentum == MomentumRegime.NEGATIVE
            and structure in (MarketStructure.BREAKDOWN, MarketStructure.TRENDING)
        ):
            return CompositeRegime.BEARISH_TRENDING_EXPANSION, DimensionEvidence(
                dimension="composite",
                state=CompositeRegime.BEARISH_TRENDING_EXPANSION.value,
                contributing_metrics=metrics,
                rationale=(
                    f"Bearish trend and negative momentum aligned with {structure.value} structure"
                ),
            )

        # Step 5: Directional Consolidation
        if trend == TrendRegime.BULLISH and structure == MarketStructure.CONSOLIDATION:
            return CompositeRegime.BULLISH_CONSOLIDATION, DimensionEvidence(
                dimension="composite",
                state=CompositeRegime.BULLISH_CONSOLIDATION.value,
                contributing_metrics=metrics,
                rationale="Bullish directional trend paused in structural consolidation",
            )

        if trend == TrendRegime.BEARISH and structure == MarketStructure.CONSOLIDATION:
            return CompositeRegime.BEARISH_CONSOLIDATION, DimensionEvidence(
                dimension="composite",
                state=CompositeRegime.BEARISH_CONSOLIDATION.value,
                contributing_metrics=metrics,
                rationale="Bearish directional trend paused in structural consolidation",
            )

        # Step 6: Directionless Compression
        if volatility == VolatilityRegime.LOW and structure == MarketStructure.CONSOLIDATION:
            return CompositeRegime.COMPRESSION, DimensionEvidence(
                dimension="composite",
                state=CompositeRegime.COMPRESSION.value,
                contributing_metrics=metrics,
                rationale="Low volatility bandwidth compression within structural consolidation",
            )

        # Step 7: Sideways Range
        if trend == TrendRegime.SIDEWAYS and structure in (
            MarketStructure.RANGING,
            MarketStructure.CONSOLIDATION,
        ):
            return CompositeRegime.SIDEWAYS_RANGE, DimensionEvidence(
                dimension="composite",
                state=CompositeRegime.SIDEWAYS_RANGE.value,
                contributing_metrics=metrics,
                rationale=f"Sideways trend aligned with {structure.value} structure",
            )

        # Step 8: Exhaustive Unmatched Fallback
        return CompositeRegime.UNKNOWN, DimensionEvidence(
            dimension="composite",
            state=CompositeRegime.UNKNOWN.value,
            contributing_metrics=metrics,
            rationale=(
                "Valid dimension evidence does not match any predefined canonical "
                "composite taxonomy rule"
            ),
        )
