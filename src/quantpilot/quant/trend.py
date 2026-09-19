"""Deterministic trend indicators: SMA, EMA, PriceVsSMA, SMASlope, EMASlope."""

from typing import Any

from quantpilot.market_data.models import Candle
from quantpilot.quant.base import BaseIndicator
from quantpilot.quant.models import (
    IndicatorProvenance,
    IndicatorSeries,
    IndicatorStatus,
    IndicatorValue,
)


class SMAIndicator(BaseIndicator):
    """Simple Moving Average."""

    def __init__(self, period: int = 20) -> None:
        if period < 1:
            raise ValueError(f"SMA period must be >= 1, got {period}")
        self._period = period

    @property
    def name(self) -> str:
        return "sma"

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
        running_sum = 0.0

        for idx, candle in enumerate(candles):
            running_sum += candle.close
            if idx >= self._period:
                running_sum -= candles[idx - self._period].close

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
                sma_val = running_sum / self._period
                values.append(
                    IndicatorValue(
                        symbol=candle.symbol,
                        exchange=candle.exchange,
                        timeframe=candle.timeframe,
                        timestamp=candle.timestamp,
                        value=float(sma_val),
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


class EMAIndicator(BaseIndicator):
    """Exponential Moving Average with SMA seed."""

    def __init__(self, period: int = 20) -> None:
        if period < 1:
            raise ValueError(f"EMA period must be >= 1, got {period}")
        self._period = period
        self._alpha = 2.0 / (period + 1)

    @property
    def name(self) -> str:
        return "ema"

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
        running_sum = 0.0
        current_ema: float | None = None

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
                running_sum += candle.close
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
                running_sum += candle.close
                current_ema = running_sum / self._period
                values.append(
                    IndicatorValue(
                        symbol=candle.symbol,
                        exchange=candle.exchange,
                        timeframe=candle.timeframe,
                        timestamp=candle.timestamp,
                        value=float(current_ema),
                        status=IndicatorStatus.VALID,
                        provenance=prov,
                    )
                )
            else:
                assert current_ema is not None
                current_ema = (self._alpha * candle.close) + ((1.0 - self._alpha) * current_ema)
                values.append(
                    IndicatorValue(
                        symbol=candle.symbol,
                        exchange=candle.exchange,
                        timeframe=candle.timeframe,
                        timestamp=candle.timestamp,
                        value=float(current_ema),
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


class PriceVsSMAIndicator(BaseIndicator):
    """Price vs SMA ratio: (Close - SMA) / SMA."""

    def __init__(self, period: int = 20) -> None:
        if period < 1:
            raise ValueError(f"PriceVsSMA period must be >= 1, got {period}")
        self._period = period
        self._sma = SMAIndicator(period=period)

    @property
    def name(self) -> str:
        return "price_vs_sma"

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
        sma_series = self._sma.calculate_series(candles)
        values: list[IndicatorValue] = []

        for idx, (candle, sma_val) in enumerate(zip(candles, sma_series.values, strict=True)):
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

            if sma_val.status != IndicatorStatus.VALID or sma_val.value is None:
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
                sma_num = float(sma_val.value)  # type: ignore[arg-type]
                if sma_num <= 0.0:
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
                    ratio = (candle.close - sma_num) / sma_num
                    values.append(
                        IndicatorValue(
                            symbol=candle.symbol,
                            exchange=candle.exchange,
                            timeframe=candle.timeframe,
                            timestamp=candle.timestamp,
                            value=float(ratio),
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


class SMASlopeIndicator(BaseIndicator):
    """Slope of Simple Moving Average: (SMA[t] - SMA[t-lag]) / lag."""

    def __init__(self, period: int = 20, lag: int = 1) -> None:
        if period < 1:
            raise ValueError(f"SMASlope period must be >= 1, got {period}")
        if lag < 1:
            raise ValueError(f"SMASlope lag must be >= 1, got {lag}")
        self._period = period
        self._lag = lag
        self._sma = SMAIndicator(period=period)

    @property
    def name(self) -> str:
        return "sma_slope"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_fields(self) -> list[str]:
        return ["close"]

    @property
    def minimum_observations(self) -> int:
        return self._period + self._lag

    @property
    def parameters(self) -> dict[str, Any]:
        return {"period": self._period, "lag": self._lag}

    def calculate_series(self, candles: list[Candle]) -> IndicatorSeries:
        sma_series = self._sma.calculate_series(candles)
        values: list[IndicatorValue] = []

        for idx, candle in enumerate(candles):
            lookback_start = max(0, idx - (self._period + self._lag) + 1)
            prov = IndicatorProvenance(
                indicator_name=self.name,
                indicator_version=self.version,
                parameters=self.parameters,
                lookback_period=self._period + self._lag,
                source_window_start=candles[lookback_start].timestamp,
                source_window_end=candle.timestamp,
                candles_analyzed=idx + 1,
            )

            if idx < (self._period + self._lag - 1):
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
                curr_sma = sma_series.values[idx]
                prev_sma = sma_series.values[idx - self._lag]
                if (
                    curr_sma.status != IndicatorStatus.VALID
                    or prev_sma.status != IndicatorStatus.VALID
                    or curr_sma.value is None
                    or prev_sma.value is None
                ):
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
                    slope = (float(curr_sma.value) - float(prev_sma.value)) / float(self._lag)  # type: ignore[arg-type]
                    values.append(
                        IndicatorValue(
                            symbol=candle.symbol,
                            exchange=candle.exchange,
                            timeframe=candle.timeframe,
                            timestamp=candle.timestamp,
                            value=float(slope),
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


class EMASlopeIndicator(BaseIndicator):
    """Slope of Exponential Moving Average: (EMA[t] - EMA[t-lag]) / lag."""

    def __init__(self, period: int = 20, lag: int = 1) -> None:
        if period < 1:
            raise ValueError(f"EMASlope period must be >= 1, got {period}")
        if lag < 1:
            raise ValueError(f"EMASlope lag must be >= 1, got {lag}")
        self._period = period
        self._lag = lag
        self._ema = EMAIndicator(period=period)

    @property
    def name(self) -> str:
        return "ema_slope"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_fields(self) -> list[str]:
        return ["close"]

    @property
    def minimum_observations(self) -> int:
        return self._period + self._lag

    @property
    def parameters(self) -> dict[str, Any]:
        return {"period": self._period, "lag": self._lag}

    def calculate_series(self, candles: list[Candle]) -> IndicatorSeries:
        ema_series = self._ema.calculate_series(candles)
        values: list[IndicatorValue] = []

        for idx, candle in enumerate(candles):
            lookback_start = max(0, idx - (self._period + self._lag) + 1)
            prov = IndicatorProvenance(
                indicator_name=self.name,
                indicator_version=self.version,
                parameters=self.parameters,
                lookback_period=self._period + self._lag,
                source_window_start=candles[lookback_start].timestamp,
                source_window_end=candle.timestamp,
                candles_analyzed=idx + 1,
            )

            if idx < (self._period + self._lag - 1):
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
                curr_ema = ema_series.values[idx]
                prev_ema = ema_series.values[idx - self._lag]
                if (
                    curr_ema.status != IndicatorStatus.VALID
                    or prev_ema.status != IndicatorStatus.VALID
                    or curr_ema.value is None
                    or prev_ema.value is None
                ):
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
                    slope = (float(curr_ema.value) - float(prev_ema.value)) / float(self._lag)  # type: ignore[arg-type]
                    values.append(
                        IndicatorValue(
                            symbol=candle.symbol,
                            exchange=candle.exchange,
                            timeframe=candle.timeframe,
                            timestamp=candle.timestamp,
                            value=float(slope),
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
