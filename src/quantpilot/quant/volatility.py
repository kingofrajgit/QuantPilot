"""Deterministic volatility indicators: TrueRange, ATR, NATR, RollingStdDev, BollingerBands."""

import math
from typing import Any

from quantpilot.market_data.models import Candle
from quantpilot.quant.base import BaseIndicator
from quantpilot.quant.models import (
    IndicatorProvenance,
    IndicatorSeries,
    IndicatorStatus,
    IndicatorValue,
)
from quantpilot.quant.trend import SMAIndicator


class TrueRangeIndicator(BaseIndicator):
    """True Range: max(H - L, |H - C_prev|, |L - C_prev|)."""

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        return "true_range"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_fields(self) -> list[str]:
        return ["high", "low", "close"]

    @property
    def minimum_observations(self) -> int:
        return 1

    @property
    def parameters(self) -> dict[str, Any]:
        return {}

    def calculate_series(self, candles: list[Candle]) -> IndicatorSeries:
        if not candles:
            raise ValueError("Candles list cannot be empty")

        values: list[IndicatorValue] = []

        for idx, candle in enumerate(candles):
            prov = IndicatorProvenance(
                indicator_name=self.name,
                indicator_version=self.version,
                parameters=self.parameters,
                lookback_period=1 if idx == 0 else 2,
                source_window_start=candles[0 if idx == 0 else idx - 1].timestamp,
                source_window_end=candle.timestamp,
                candles_analyzed=idx + 1,
            )

            if idx == 0:
                tr_val = candle.high - candle.low
            else:
                prev_close = candles[idx - 1].close
                tr_val = max(
                    candle.high - candle.low,
                    abs(candle.high - prev_close),
                    abs(candle.low - prev_close),
                )

            values.append(
                IndicatorValue(
                    symbol=candle.symbol,
                    exchange=candle.exchange,
                    timeframe=candle.timeframe,
                    timestamp=candle.timestamp,
                    value=float(tr_val),
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


class ATRIndicator(BaseIndicator):
    """Average True Range using Wilder's smoothing."""

    def __init__(self, period: int = 14) -> None:
        if period < 1:
            raise ValueError(f"ATR period must be >= 1, got {period}")
        self._period = period
        self._tr = TrueRangeIndicator()

    @property
    def name(self) -> str:
        return "atr"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_fields(self) -> list[str]:
        return ["high", "low", "close"]

    @property
    def minimum_observations(self) -> int:
        return self._period

    @property
    def parameters(self) -> dict[str, Any]:
        return {"period": self._period}

    def calculate_series(self, candles: list[Candle]) -> IndicatorSeries:
        if not candles:
            raise ValueError("Candles list cannot be empty")

        tr_series = self._tr.calculate_series(candles)
        values: list[IndicatorValue] = []

        current_atr: float | None = None
        initial_tr_sum = 0.0

        for idx, (candle, tr_val) in enumerate(zip(candles, tr_series.values, strict=True)):
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

            tr_num = float(tr_val.value)  # type: ignore[arg-type]

            if idx < self._period - 1:
                initial_tr_sum += tr_num
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
            elif idx == self._period - 1:
                initial_tr_sum += tr_num
                current_atr = initial_tr_sum / self._period
                values.append(
                    IndicatorValue(
                        symbol=candle.symbol,
                        exchange=candle.exchange,
                        timeframe=candle.timeframe,
                        timestamp=candle.timestamp,
                        value=float(current_atr),
                        status=IndicatorStatus.VALID,
                        provenance=prov,
                    )
                )
            else:
                assert current_atr is not None
                current_atr = ((current_atr * (self._period - 1)) + tr_num) / self._period
                values.append(
                    IndicatorValue(
                        symbol=candle.symbol,
                        exchange=candle.exchange,
                        timeframe=candle.timeframe,
                        timestamp=candle.timestamp,
                        value=float(current_atr),
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


class NATRIndicator(BaseIndicator):
    """Normalized ATR (ATR as percentage of close): (ATR / Close) * 100."""

    def __init__(self, period: int = 14) -> None:
        if period < 1:
            raise ValueError(f"NATR period must be >= 1, got {period}")
        self._period = period
        self._atr = ATRIndicator(period=period)

    @property
    def name(self) -> str:
        return "natr"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_fields(self) -> list[str]:
        return ["high", "low", "close"]

    @property
    def minimum_observations(self) -> int:
        return self._period

    @property
    def parameters(self) -> dict[str, Any]:
        return {"period": self._period}

    def calculate_series(self, candles: list[Candle]) -> IndicatorSeries:
        atr_series = self._atr.calculate_series(candles)
        values: list[IndicatorValue] = []

        for idx, (candle, atr_val) in enumerate(zip(candles, atr_series.values, strict=True)):
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

            if atr_val.status != IndicatorStatus.VALID or atr_val.value is None:
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
                if candle.close <= 0.0:
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
                    natr_val = (float(atr_val.value) / candle.close) * 100.0  # type: ignore[arg-type]
                    values.append(
                        IndicatorValue(
                            symbol=candle.symbol,
                            exchange=candle.exchange,
                            timeframe=candle.timeframe,
                            timestamp=candle.timestamp,
                            value=float(natr_val),
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


class RollingStdDevIndicator(BaseIndicator):
    """Rolling Sample Standard Deviation (with N-1 degrees of freedom)."""

    def __init__(self, period: int = 20) -> None:
        if period < 2:
            raise ValueError(
                f"RollingStdDev period must be >= 2 for sample standard deviation, got {period}"
            )
        self._period = period

    @property
    def name(self) -> str:
        return "rolling_std"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_fields(self) -> list[str]:
        return ["close"]

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
        window: list[float] = []

        for idx, candle in enumerate(candles):
            window.append(candle.close)
            if len(window) > self._period:
                window.pop(0)

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
                mean = sum(window) / self._period
                sum_sq_diff = sum((x - mean) ** 2 for x in window)
                variance = sum_sq_diff / (self._period - 1)
                std_dev = math.sqrt(max(0.0, variance))

                values.append(
                    IndicatorValue(
                        symbol=candle.symbol,
                        exchange=candle.exchange,
                        timeframe=candle.timeframe,
                        timestamp=candle.timestamp,
                        value=float(std_dev),
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


class BollingerBandsIndicator(BaseIndicator):
    """Bollinger Bands with deterministic edge-case precedence."""

    def __init__(self, period: int = 20, std_multiplier: float = 2.0) -> None:
        if period < 2:
            raise ValueError(f"BollingerBands period must be >= 2, got {period}")
        if std_multiplier < 0.0:
            raise ValueError(f"BollingerBands std_multiplier must be >= 0.0, got {std_multiplier}")

        self._period = period
        self._std_multiplier = float(std_multiplier)
        self._sma = SMAIndicator(period=period)
        self._std = RollingStdDevIndicator(period=period)

    @property
    def name(self) -> str:
        return "bollinger_bands"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_fields(self) -> list[str]:
        return ["close"]

    @property
    def minimum_observations(self) -> int:
        return self._period

    @property
    def parameters(self) -> dict[str, Any]:
        return {"period": self._period, "std_multiplier": self._std_multiplier}

    def calculate_series(self, candles: list[Candle]) -> IndicatorSeries:
        sma_series = self._sma.calculate_series(candles)
        std_series = self._std.calculate_series(candles)

        values: list[IndicatorValue] = []

        for idx, (candle, sma_val, std_val) in enumerate(
            zip(candles, sma_series.values, std_series.values, strict=True)
        ):
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

            if (
                sma_val.status != IndicatorStatus.VALID
                or std_val.status != IndicatorStatus.VALID
                or sma_val.value is None
                or std_val.value is None
            ):
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
                middle = float(sma_val.value)  # type: ignore[arg-type]
                sigma = float(std_val.value)  # type: ignore[arg-type]

                # Deterministic Precedence Rule:
                # 1. IF middle <= 0 -> INVALID, value = None
                # 2. ELSE IF sigma == 0 -> VALID, upper=lower=middle, bandwidth=0.0, percent_b=0.5
                # 3. ELSE -> regular calculation
                if middle <= 0.0:
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
                elif sigma == 0.0:
                    values.append(
                        IndicatorValue(
                            symbol=candle.symbol,
                            exchange=candle.exchange,
                            timeframe=candle.timeframe,
                            timestamp=candle.timestamp,
                            value={
                                "middle": middle,
                                "upper": middle,
                                "lower": middle,
                                "bandwidth": 0.0,
                                "percent_b": 0.5,
                            },
                            status=IndicatorStatus.VALID,
                            provenance=prov,
                        )
                    )
                else:
                    upper = middle + (self._std_multiplier * sigma)
                    lower = middle - (self._std_multiplier * sigma)
                    bandwidth = (upper - lower) / middle
                    band_range = upper - lower
                    percent_b = (candle.close - lower) / band_range if band_range != 0.0 else 0.5

                    values.append(
                        IndicatorValue(
                            symbol=candle.symbol,
                            exchange=candle.exchange,
                            timeframe=candle.timeframe,
                            timestamp=candle.timestamp,
                            value={
                                "middle": float(middle),
                                "upper": float(upper),
                                "lower": float(lower),
                                "bandwidth": float(bandwidth),
                                "percent_b": float(percent_b),
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
