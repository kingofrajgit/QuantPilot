"""Deterministic price structure indicators: RollingHigh, RollingLow, StructureBreakoutDistance."""

from typing import Any

from quantpilot.market_data.models import Candle
from quantpilot.quant.base import BaseIndicator
from quantpilot.quant.models import (
    IndicatorProvenance,
    IndicatorSeries,
    IndicatorStatus,
    IndicatorValue,
)


class RollingHighIndicator(BaseIndicator):
    """Rolling High over lookback period."""

    def __init__(self, period: int = 20) -> None:
        if period < 1:
            raise ValueError(f"RollingHigh period must be >= 1, got {period}")
        self._period = period

    @property
    def name(self) -> str:
        return "rolling_high"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_fields(self) -> list[str]:
        return ["high"]

    @property
    def minimum_observations(self) -> int:
        return self._period

    @property
    def parameters(self) -> dict[str, Any]:
        return {"period": self._period}

    def calculate_series(self, candles: list[Candle]) -> IndicatorSeries:
        if not candles:
            raise ValueError("Candles list cannot be empty")

        values: list[IndicatorValue] = []

        for idx, candle in enumerate(candles):
            lookback_start = max(0, idx - self._period + 1)
            prov = IndicatorProvenance(
                indicator_name=self.name,
                indicator_version=self.version,
                parameters=self.parameters,
                lookback_period=self._period,
                source_window_start=candles[lookback_start].timestamp,
                source_window_end=candle.timestamp,
                candles_analyzed=idx + 1,
            )

            if idx < self._period - 1:
                values.append(
                    IndicatorValue(
                        symbol=candle.symbol,
                        exchange=candle.exchange,
                        timeframe=candle.timeframe,
                        timestamp=candle.timestamp,
                        value=None,
                        status=IndicatorStatus.INSUFFICIENT_DATA,
                        provenance=prov,
                    )
                )
            else:
                window_high = max(c.high for c in candles[idx - self._period + 1 : idx + 1])
                values.append(
                    IndicatorValue(
                        symbol=candle.symbol,
                        exchange=candle.exchange,
                        timeframe=candle.timeframe,
                        timestamp=candle.timestamp,
                        value=float(window_high),
                        status=IndicatorStatus.VALID,
                        provenance=prov,
                    )
                )

        return IndicatorSeries(
            symbol=candles[0].symbol,
            exchange=candles[0].exchange,
            timeframe=candles[0].timeframe,
            indicator_name=self.name,
            values=values,
        )

    def calculate_point(self, candles: list[Candle]) -> IndicatorValue:
        series = self.calculate_series(candles)
        return series.values[-1]


class RollingLowIndicator(BaseIndicator):
    """Rolling Low over lookback period."""

    def __init__(self, period: int = 20) -> None:
        if period < 1:
            raise ValueError(f"RollingLow period must be >= 1, got {period}")
        self._period = period

    @property
    def name(self) -> str:
        return "rolling_low"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_fields(self) -> list[str]:
        return ["low"]

    @property
    def minimum_observations(self) -> int:
        return self._period

    @property
    def parameters(self) -> dict[str, Any]:
        return {"period": self._period}

    def calculate_series(self, candles: list[Candle]) -> IndicatorSeries:
        if not candles:
            raise ValueError("Candles list cannot be empty")

        values: list[IndicatorValue] = []

        for idx, candle in enumerate(candles):
            lookback_start = max(0, idx - self._period + 1)
            prov = IndicatorProvenance(
                indicator_name=self.name,
                indicator_version=self.version,
                parameters=self.parameters,
                lookback_period=self._period,
                source_window_start=candles[lookback_start].timestamp,
                source_window_end=candle.timestamp,
                candles_analyzed=idx + 1,
            )

            if idx < self._period - 1:
                values.append(
                    IndicatorValue(
                        symbol=candle.symbol,
                        exchange=candle.exchange,
                        timeframe=candle.timeframe,
                        timestamp=candle.timestamp,
                        value=None,
                        status=IndicatorStatus.INSUFFICIENT_DATA,
                        provenance=prov,
                    )
                )
            else:
                window_low = min(c.low for c in candles[idx - self._period + 1 : idx + 1])
                values.append(
                    IndicatorValue(
                        symbol=candle.symbol,
                        exchange=candle.exchange,
                        timeframe=candle.timeframe,
                        timestamp=candle.timestamp,
                        value=float(window_low),
                        status=IndicatorStatus.VALID,
                        provenance=prov,
                    )
                )

        return IndicatorSeries(
            symbol=candles[0].symbol,
            exchange=candles[0].exchange,
            timeframe=candles[0].timeframe,
            indicator_name=self.name,
            values=values,
        )

    def calculate_point(self, candles: list[Candle]) -> IndicatorValue:
        series = self.calculate_series(candles)
        return series.values[-1]


class StructureBreakoutIndicator(BaseIndicator):
    """Distance from prior rolling high/low and breakout/breakdown feature flags.

    Strictly anti-lookahead: compares Candle[t] close against historical window ending at t-1.
    """

    def __init__(self, period: int = 20) -> None:
        if period < 1:
            raise ValueError(f"StructureBreakoutDistance period must be >= 1, got {period}")
        self._period = period

    @property
    def name(self) -> str:
        return "structure_breakout_distance"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_fields(self) -> list[str]:
        return ["high", "low", "close"]

    @property
    def minimum_observations(self) -> int:
        return self._period + 1

    @property
    def parameters(self) -> dict[str, Any]:
        return {"period": self._period}

    def calculate_series(self, candles: list[Candle]) -> IndicatorSeries:
        if not candles:
            raise ValueError("Candles list cannot be empty")

        values: list[IndicatorValue] = []

        for idx, candle in enumerate(candles):
            lookback_start = max(0, idx - self._period)
            prov = IndicatorProvenance(
                indicator_name=self.name,
                indicator_version=self.version,
                parameters=self.parameters,
                lookback_period=self._period + 1,
                source_window_start=candles[lookback_start].timestamp,
                source_window_end=candle.timestamp,
                candles_analyzed=idx + 1,
            )

            if idx < self._period:
                values.append(
                    IndicatorValue(
                        symbol=candle.symbol,
                        exchange=candle.exchange,
                        timeframe=candle.timeframe,
                        timestamp=candle.timestamp,
                        value=None,
                        status=IndicatorStatus.INSUFFICIENT_DATA,
                        provenance=prov,
                    )
                )
            else:
                prior_window = candles[idx - self._period : idx]
                prior_high = max(c.high for c in prior_window)
                prior_low = min(c.low for c in prior_window)

                if prior_high <= 0.0 or prior_low <= 0.0:
                    values.append(
                        IndicatorValue(
                            symbol=candle.symbol,
                            exchange=candle.exchange,
                            timeframe=candle.timeframe,
                            timestamp=candle.timestamp,
                            value=None,
                            status=IndicatorStatus.INVALID,
                            provenance=prov,
                        )
                    )
                else:
                    dist_high = ((candle.close - prior_high) / prior_high) * 100.0
                    dist_low = ((candle.close - prior_low) / prior_low) * 100.0
                    breakout_high = 1.0 if candle.close > prior_high else 0.0
                    breakdown_low = 1.0 if candle.close < prior_low else 0.0

                    values.append(
                        IndicatorValue(
                            symbol=candle.symbol,
                            exchange=candle.exchange,
                            timeframe=candle.timeframe,
                            timestamp=candle.timestamp,
                            value={
                                "dist_high": float(dist_high),
                                "dist_low": float(dist_low),
                                "breakout_high": float(breakout_high),
                                "breakdown_low": float(breakdown_low),
                            },
                            status=IndicatorStatus.VALID,
                            provenance=prov,
                        )
                    )

        return IndicatorSeries(
            symbol=candles[0].symbol,
            exchange=candles[0].exchange,
            timeframe=candles[0].timeframe,
            indicator_name=self.name,
            values=values,
        )

    def calculate_point(self, candles: list[Candle]) -> IndicatorValue:
        series = self.calculate_series(candles)
        return series.values[-1]
