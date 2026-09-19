"""Deterministic momentum indicators: ROC, RSI (Wilder's), MACD."""

from typing import Any

from quantpilot.market_data.models import Candle
from quantpilot.quant.base import BaseIndicator
from quantpilot.quant.models import (
    IndicatorProvenance,
    IndicatorSeries,
    IndicatorStatus,
    IndicatorValue,
)
from quantpilot.quant.trend import EMAIndicator


class ROCIndicator(BaseIndicator):
    """Rate of Change indicator: (Close[t] - Close[t-period]) / Close[t-period] * 100."""

    def __init__(self, period: int = 14) -> None:
        if period < 1:
            raise ValueError(f"ROC period must be >= 1, got {period}")
        self._period = period

    @property
    def name(self) -> str:
        return "roc"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_fields(self) -> list[str]:
        return ["close"]

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
                lookback_period=self._period,
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
                prev_close = candles[idx - self._period].close
                if prev_close <= 0.0:
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
                    roc_val = ((candle.close - prev_close) / prev_close) * 100.0
                    values.append(
                        IndicatorValue(
                            symbol=candle.symbol,
                            exchange=candle.exchange,
                            timeframe=candle.timeframe,
                            timestamp=candle.timestamp,
                            value=float(roc_val),
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


class RSIIndicator(BaseIndicator):
    """Relative Strength Index using Wilder's smoothing."""

    def __init__(self, period: int = 14) -> None:
        if period < 1:
            raise ValueError(f"RSI period must be >= 1, got {period}")
        self._period = period

    @property
    def name(self) -> str:
        return "rsi"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_fields(self) -> list[str]:
        return ["close"]

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
        avg_gain: float | None = None
        avg_loss: float | None = None

        initial_gains: list[float] = []
        initial_losses: list[float] = []

        for idx, candle in enumerate(candles):
            lookback_start = max(0, idx - self._period)
            prov = IndicatorProvenance(
                indicator_name=self.name,
                indicator_version=self.version,
                parameters=self.parameters,
                lookback_period=self._period,
                source_window_start=candles[lookback_start].timestamp,
                source_window_end=candle.timestamp,
                candles_analyzed=idx + 1,
            )

            if idx == 0:
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
                continue

            delta = candle.close - candles[idx - 1].close
            gain = max(delta, 0.0)
            loss = max(-delta, 0.0)

            if idx < self._period:
                initial_gains.append(gain)
                initial_losses.append(loss)
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
            elif idx == self._period:
                initial_gains.append(gain)
                initial_losses.append(loss)
                avg_gain = sum(initial_gains) / self._period
                avg_loss = sum(initial_losses) / self._period

                rsi_val = self._compute_rsi(avg_gain, avg_loss)
                values.append(
                    IndicatorValue(
                        symbol=candle.symbol,
                        exchange=candle.exchange,
                        timeframe=candle.timeframe,
                        timestamp=candle.timestamp,
                        value=float(rsi_val),
                        status=IndicatorStatus.VALID,
                        provenance=prov,
                    )
                )
            else:
                assert avg_gain is not None and avg_loss is not None
                avg_gain = ((avg_gain * (self._period - 1)) + gain) / self._period
                avg_loss = ((avg_loss * (self._period - 1)) + loss) / self._period

                rsi_val = self._compute_rsi(avg_gain, avg_loss)
                values.append(
                    IndicatorValue(
                        symbol=candle.symbol,
                        exchange=candle.exchange,
                        timeframe=candle.timeframe,
                        timestamp=candle.timestamp,
                        value=float(rsi_val),
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

    def _compute_rsi(self, avg_gain: float, avg_loss: float) -> float:
        if avg_loss == 0.0:
            if avg_gain > 0.0:
                return 100.0
            return 50.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def calculate_point(self, candles: list[Candle]) -> IndicatorValue:
        series = self.calculate_series(candles)
        return series.values[-1]


class MACDIndicator(BaseIndicator):
    """Moving Average Convergence Divergence with Signal Line and Histogram."""

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> None:
        if fast_period < 1:
            raise ValueError(f"MACD fast_period must be >= 1, got {fast_period}")
        if slow_period <= fast_period:
            raise ValueError(
                f"MACD slow_period ({slow_period}) must be > fast_period ({fast_period})"
            )
        if signal_period < 1:
            raise ValueError(f"MACD signal_period must be >= 1, got {signal_period}")

        self._fast_period = fast_period
        self._slow_period = slow_period
        self._signal_period = signal_period

        self._fast_ema = EMAIndicator(period=fast_period)
        self._slow_ema = EMAIndicator(period=slow_period)
        self._signal_alpha = 2.0 / (signal_period + 1)

    @property
    def name(self) -> str:
        return "macd"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_fields(self) -> list[str]:
        return ["close"]

    @property
    def minimum_observations(self) -> int:
        return self._slow_period + self._signal_period - 1

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "fast_period": self._fast_period,
            "slow_period": self._slow_period,
            "signal_period": self._signal_period,
        }

    def calculate_series(self, candles: list[Candle]) -> IndicatorSeries:
        if not candles:
            raise ValueError("Candles list cannot be empty")

        fast_series = self._fast_ema.calculate_series(candles)
        slow_series = self._slow_ema.calculate_series(candles)

        values: list[IndicatorValue] = []

        macd_lines: list[float | None] = []
        for f_val, s_val in zip(fast_series.values, slow_series.values, strict=True):
            if (
                f_val.status == IndicatorStatus.VALID
                and s_val.status == IndicatorStatus.VALID
                and f_val.value is not None
                and s_val.value is not None
            ):
                macd_lines.append(float(f_val.value) - float(s_val.value))  # type: ignore[arg-type]
            else:
                macd_lines.append(None)

        current_signal: float | None = None
        initial_macd_segment: list[float] = []

        for idx, candle in enumerate(candles):
            lookback_start = max(0, idx - self.minimum_observations + 1)
            prov = IndicatorProvenance(
                indicator_name=self.name,
                indicator_version=self.version,
                parameters=self.parameters,
                lookback_period=self.minimum_observations,
                source_window_start=candles[lookback_start].timestamp,
                source_window_end=candle.timestamp,
                candles_analyzed=idx + 1,
            )

            if idx < self.minimum_observations - 1:
                if macd_lines[idx] is not None:
                    initial_macd_segment.append(macd_lines[idx])  # type: ignore[arg-type]

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
            elif idx == self.minimum_observations - 1:
                assert macd_lines[idx] is not None
                initial_macd_segment.append(macd_lines[idx])  # type: ignore[arg-type]
                current_signal = sum(initial_macd_segment) / self._signal_period
                macd_val = macd_lines[idx]
                assert macd_val is not None
                hist_val = macd_val - current_signal

                values.append(
                    IndicatorValue(
                        symbol=candle.symbol,
                        exchange=candle.exchange,
                        timeframe=candle.timeframe,
                        timestamp=candle.timestamp,
                        value={
                            "macd": float(macd_val),
                            "signal": float(current_signal),
                            "histogram": float(hist_val),
                        },
                        status=IndicatorStatus.VALID,
                        provenance=prov,
                    )
                )
            else:
                macd_val = macd_lines[idx]
                assert macd_val is not None
                assert current_signal is not None
                current_signal = (self._signal_alpha * macd_val) + (
                    (1.0 - self._signal_alpha) * current_signal
                )
                hist_val = macd_val - current_signal

                values.append(
                    IndicatorValue(
                        symbol=candle.symbol,
                        exchange=candle.exchange,
                        timeframe=candle.timeframe,
                        timestamp=candle.timestamp,
                        value={
                            "macd": float(macd_val),
                            "signal": float(current_signal),
                            "histogram": float(hist_val),
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
