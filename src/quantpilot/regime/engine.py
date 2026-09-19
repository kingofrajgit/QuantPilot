"""RegimeEngine orchestrator.

Validates input alignments and executes stateless regime classifications.
"""

from collections.abc import Mapping, Sequence

from quantpilot.market_data.models import Candle
from quantpilot.quant.models import IndicatorSeries
from quantpilot.regime.combiner import RegimeCombiner
from quantpilot.regime.models import (
    MarketRegimeContext,
    RegimeContextSeries,
    RegimeProvenance,
)
from quantpilot.regime.momentum_regime import MomentumClassifier
from quantpilot.regime.structure_regime import StructureClassifier
from quantpilot.regime.trend_regime import TrendClassifier
from quantpilot.regime.volatility_regime import VolatilityClassifier
from quantpilot.regime.volume_regime import VolumeClassifier


class RegimeEngine:
    """Stateless market regime and structure analysis engine.

    Evaluates canonical candles and Phase 3 quantitative indicator series into
    strictly deterministic, auditable market-context evidence.
    """

    REQUIRED_INDICATORS: tuple[str, ...] = (
        "price_vs_sma",
        "sma_slope",
        "ema_slope",
        "sma",
        "rsi",
        "roc",
        "macd",
        "bollinger_bands",
        "rvol",
        "obv",
        "structure_breakout_distance",
    )

    def __init__(
        self,
        trend_classifier: TrendClassifier | None = None,
        momentum_classifier: MomentumClassifier | None = None,
        volatility_classifier: VolatilityClassifier | None = None,
        volume_classifier: VolumeClassifier | None = None,
        structure_classifier: StructureClassifier | None = None,
        combiner: RegimeCombiner | None = None,
    ) -> None:
        self.trend_classifier = trend_classifier or TrendClassifier()
        self.momentum_classifier = momentum_classifier or MomentumClassifier()
        self.volatility_classifier = volatility_classifier or VolatilityClassifier()
        self.volume_classifier = volume_classifier or VolumeClassifier()
        self.structure_classifier = structure_classifier or StructureClassifier()
        self.combiner = combiner or RegimeCombiner()

    def validate_inputs(
        self,
        candles: Sequence[Candle],
        indicators: Mapping[str, IndicatorSeries],
    ) -> None:
        """Validate input candles and indicator series fail-closed before evaluation.

        Rejects:
        - Empty candle sequences
        - Missing required indicator series
        - Mismatched series lengths
        - Mismatched timestamps at any index t
        - Mixed symbols, exchanges, or timeframes
        """
        if not candles:
            raise ValueError("Candle sequence must not be empty")

        first_candle = candles[0]
        expected_symbol = first_candle.symbol
        expected_exchange = first_candle.exchange
        expected_timeframe = first_candle.timeframe
        n_candles = len(candles)

        # Check for missing required indicators
        missing = [ind for ind in self.REQUIRED_INDICATORS if ind not in indicators]
        if missing:
            raise ValueError(f"Missing required indicator series: {missing}")

        # Check candle internal uniformity
        for idx, candle in enumerate(candles):
            if candle.symbol != expected_symbol:
                raise ValueError(
                    f"Mixed candle symbols at index {idx}: '{candle.symbol}' != '{expected_symbol}'"
                )
            if candle.exchange != expected_exchange:
                raise ValueError(
                    f"Mixed candle exchanges at index {idx}: "
                    f"'{candle.exchange}' != '{expected_exchange}'"
                )
            if candle.timeframe != expected_timeframe:
                raise ValueError(
                    f"Mixed candle timeframes at index {idx}: "
                    f"'{candle.timeframe}' != '{expected_timeframe}'"
                )

        # Validate each required indicator series against candles
        for name in self.REQUIRED_INDICATORS:
            series = indicators[name]
            if series.symbol != expected_symbol:
                raise ValueError(
                    f"Indicator '{name}' symbol mismatch: '{series.symbol}' != '{expected_symbol}'"
                )
            if series.exchange != expected_exchange:
                raise ValueError(
                    f"Indicator '{name}' exchange mismatch: "
                    f"'{series.exchange}' != '{expected_exchange}'"
                )
            if series.timeframe != expected_timeframe:
                raise ValueError(
                    f"Indicator '{name}' timeframe mismatch: "
                    f"'{series.timeframe}' != '{expected_timeframe}'"
                )
            if len(series.values) != n_candles:
                raise ValueError(
                    f"Indicator '{name}' length mismatch: {len(series.values)} != {n_candles}"
                )

        # Validate timestamp alignment index-by-index fail-closed
        for idx, candle in enumerate(candles):
            c_ts = candle.timestamp
            for name in self.REQUIRED_INDICATORS:
                ind_ts = indicators[name].values[idx].timestamp
                if ind_ts != c_ts:
                    raise ValueError(
                        f"Timestamp alignment failure at index {idx} for indicator '{name}': "
                        f"indicator timestamp {ind_ts.isoformat()} != "
                        f"candle timestamp {c_ts.isoformat()}"
                    )

    def evaluate(
        self,
        candles: Sequence[Candle],
        indicators: Mapping[str, IndicatorSeries],
    ) -> RegimeContextSeries:
        """Evaluate chronological, stateless regime context series from candles and indicators."""
        self.validate_inputs(candles, indicators)

        first_candle = candles[0]
        expected_symbol = first_candle.symbol
        expected_exchange = first_candle.exchange
        expected_timeframe = first_candle.timeframe

        combined_parameters = {
            "trend": self.trend_classifier.parameters,
            "momentum": self.momentum_classifier.parameters,
            "volatility": self.volatility_classifier.parameters,
            "volume": self.volume_classifier.parameters,
            "structure": self.structure_classifier.parameters,
        }

        contexts: list[MarketRegimeContext] = []

        for idx, candle in enumerate(candles):
            # Classify all 5 dimensions statelessly
            trend_state, trend_ev = self.trend_classifier.classify(idx, candles, indicators)
            mom_state, mom_ev = self.momentum_classifier.classify(idx, candles, indicators)
            vol_state, vol_ev = self.volatility_classifier.classify(idx, candles, indicators)
            volume_state, volume_ev = self.volume_classifier.classify(idx, candles, indicators)
            struct_state, struct_ev = self.structure_classifier.classify(idx, candles, indicators)

            # Synthesize composite regime via 8-step priority precedence
            comp_state, comp_ev = self.combiner.combine(
                trend=trend_state,
                momentum=mom_state,
                volatility=vol_state,
                structure=struct_state,
            )

            provenance = RegimeProvenance(
                engine_version="1.0.0",
                parameters=combined_parameters,
                indicators_used=list(self.REQUIRED_INDICATORS),
                source_window_start=candles[0].timestamp,
                source_window_end=candle.timestamp,
                candles_evaluated=idx + 1,
            )

            context = MarketRegimeContext(
                symbol=expected_symbol,
                exchange=expected_exchange,
                timeframe=expected_timeframe,
                timestamp=candle.timestamp,
                composite_regime=comp_state,
                trend=trend_state,
                momentum=mom_state,
                volatility=vol_state,
                volume=volume_state,
                structure=struct_state,
                evidence={
                    "trend": trend_ev,
                    "momentum": mom_ev,
                    "volatility": vol_ev,
                    "volume": volume_ev,
                    "structure": struct_ev,
                    "composite": comp_ev,
                },
                provenance=provenance,
            )
            contexts.append(context)

        return RegimeContextSeries(
            symbol=expected_symbol,
            exchange=expected_exchange,
            timeframe=expected_timeframe,
            values=contexts,
        )
