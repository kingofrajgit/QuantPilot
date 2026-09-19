"""Deterministic volume indicators: VolumeSMA, RelativeVolume (RVOL), VolumeChange, OBV."""

from typing import Any

from quantpilot.market_data.models import Candle
from quantpilot.quant.base import BaseIndicator
from quantpilot.quant.models import (
    IndicatorProvenance,
    IndicatorSeries,
    IndicatorStatus,
    IndicatorValue,
)


class VolumeSMAIndicator(BaseIndicator):
    """Simple Moving Average of Volume."""

    def __init__(self, period: int = 20) -> None:
        if period < 1:
            raise ValueError(f"VolumeSMA period must be >= 1, got {period}")
        self._period = period

    @property
    def name(self) -> str:
        return "volume_sma"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_fields(self) -> list[str]:
        return ["volume"]

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
            running_sum += float(candle.volume)
            if idx >= self._period:
                running_sum -= float(candles[idx - self._period].volume)

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
                vol_sma = running_sum / self._period
                values.append(
                    IndicatorValue(
                        symbol=candle.symbol,
                        exchange=candle.exchange,
                        timeframe=candle.timeframe,
                        timestamp=candle.timestamp,
                        value=float(vol_sma),
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


class RVOLIndicator(BaseIndicator):
    """Relative Volume: Volume[t] / VolSMA[t]."""

    def __init__(self, period: int = 20) -> None:
        if period < 1:
            raise ValueError(f"RVOL period must be >= 1, got {period}")
        self._period = period
        self._vol_sma = VolumeSMAIndicator(period=period)

    @property
    def name(self) -> str:
        return "rvol"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_fields(self) -> list[str]:
        return ["volume"]

    @property
    def minimum_observations(self) -> int:
        return self._period

    @property
    def parameters(self) -> dict[str, Any]:
        return {"period": self._period}

    def calculate_series(self, candles: list[Candle]) -> IndicatorSeries:
        sma_series = self._vol_sma.calculate_series(candles)
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
                vol_sma_num = float(sma_val.value)  # type: ignore[arg-type]
                # Zero denominator: if VolSMA == 0 -> INVALID, value = None
                if vol_sma_num == 0.0:
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
                    ratio = float(candle.volume) / vol_sma_num
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


class VolumeChangeIndicator(BaseIndicator):
    """Volume Change: (Volume[t] - Volume[t-1]) / Volume[t-1] * 100."""

    def __init__(self, lag: int = 1) -> None:
        if lag < 1:
            raise ValueError(f"VolumeChange lag must be >= 1, got {lag}")
        self._lag = lag

    @property
    def name(self) -> str:
        return "volume_change"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_fields(self) -> list[str]:
        return ["volume"]

    @property
    def minimum_observations(self) -> int:
        return self._lag + 1

    @property
    def parameters(self) -> dict[str, Any]:
        return {"lag": self._lag}

    def calculate_series(self, candles: list[Candle]) -> IndicatorSeries:
        if not candles:
            raise ValueError("Candles list cannot be empty")

        values: list[IndicatorValue] = []

        for idx, candle in enumerate(candles):
            lookback_start = max(0, idx - self._lag)
            prov = IndicatorProvenance(
                indicator_name=self.name,
                indicator_version=self.version,
                parameters=self.parameters,
                lookback_period=self._lag + 1,
                source_window_start=candles[lookback_start].timestamp,
                source_window_end=candle.timestamp,
                candles_analyzed=idx + 1,
            )

            if idx < self._lag:
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
                prev_vol = float(candles[idx - self._lag].volume)
                curr_vol = float(candle.volume)

                # Zero denominator rule: if previous_volume == 0 -> INVALID, value = None
                if prev_vol == 0.0:
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
                    change_pct = ((curr_vol - prev_vol) / prev_vol) * 100.0
                    values.append(
                        IndicatorValue(
                            symbol=candle.symbol,
                            exchange=candle.exchange,
                            timeframe=candle.timeframe,
                            timestamp=candle.timestamp,
                            value=float(change_pct),
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


class OBVIndicator(BaseIndicator):
    """On-Balance Volume (OBV)."""

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        return "obv"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_fields(self) -> list[str]:
        return ["close", "volume"]

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
        current_obv = 0.0

        for idx, candle in enumerate(candles):
            prov = IndicatorProvenance(
                indicator_name=self.name,
                indicator_version=self.version,
                parameters=self.parameters,
                lookback_period=1,
                source_window_start=candles[0].timestamp,
                source_window_end=candle.timestamp,
                candles_analyzed=idx + 1,
            )

            if idx == 0:
                current_obv = 0.0
            else:
                prev_close = candles[idx - 1].close
                if candle.close > prev_close:
                    current_obv += float(candle.volume)
                elif candle.close < prev_close:
                    current_obv -= float(candle.volume)
                # if close == prev_close, current_obv remains unchanged

            values.append(
                IndicatorValue(
                    symbol=candle.symbol,
                    exchange=candle.exchange,
                    timeframe=candle.timeframe,
                    timestamp=candle.timestamp,
                    value=float(current_obv),
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
