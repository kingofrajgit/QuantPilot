"""Deterministic relative strength indicator vs injectable benchmark."""

from datetime import timezone
from typing import Any

from quantpilot.market_data.models import Candle
from quantpilot.quant.base import BaseIndicator
from quantpilot.quant.models import (
    IndicatorProvenance,
    IndicatorSeries,
    IndicatorStatus,
    IndicatorValue,
)


class RelativeStrengthIndicator(BaseIndicator):
    """Asset return vs Benchmark return over lookback period.

    Strict timestamp alignment: requires exact matching UTC timestamps.
    Missing benchmark candle at T or T-N yields status = INSUFFICIENT_DATA, value = None.
    Zero imputation, forward-fill, or look-ahead.
    """

    def __init__(self, period: int = 20, benchmark_candles: list[Candle] | None = None) -> None:
        if period < 1:
            raise ValueError(f"RelativeStrength period must be >= 1, got {period}")
        self._period = period
        self._benchmark_candles = benchmark_candles

    @property
    def name(self) -> str:
        return "relative_strength"

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

    def set_benchmark_candles(self, benchmark_candles: list[Candle]) -> None:
        """Inject benchmark candles."""
        self._benchmark_candles = benchmark_candles

    def calculate_series(
        self,
        candles: list[Candle],
        benchmark_candles: list[Candle] | None = None,
    ) -> IndicatorSeries:
        if not candles:
            raise ValueError("Candles list cannot be empty")

        bench = benchmark_candles or self._benchmark_candles
        if not bench:
            raise ValueError("Benchmark candles must be provided for RelativeStrength calculation")

        # Validate benchmark timeframe
        if bench[0].timeframe != candles[0].timeframe:
            raise ValueError(
                f"Timeframe mismatch: asset={candles[0].timeframe.value} "
                f"!= benchmark={bench[0].timeframe.value}"
            )

        # Validate benchmark timestamps ascending and UTC without duplicates
        bench_map: dict[Any, Candle] = {}
        prev_ts = None
        for b_idx, b_candle in enumerate(bench):
            if b_candle.timestamp.tzinfo != timezone.utc:
                raise ValueError(
                    f"Benchmark index {b_idx} non-UTC timezone: {b_candle.timestamp.tzinfo}"
                )
            if prev_ts is not None and b_candle.timestamp <= prev_ts:
                raise ValueError(
                    f"Benchmark timestamps must be strictly ascending with no duplicates. "
                    f"Index {b_idx} ({b_candle.timestamp}) <= previous ({prev_ts})"
                )
            prev_ts = b_candle.timestamp
            bench_map[b_candle.timestamp] = b_candle

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
                ts_curr = candle.timestamp
                ts_past = candles[idx - self._period].timestamp

                # Exact timestamp lookup in benchmark: NO forward fill, NO interpolation
                bench_curr = bench_map.get(ts_curr)
                bench_past = bench_map.get(ts_past)

                if bench_curr is None or bench_past is None:
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
                    asset_curr = candle.close
                    asset_past = candles[idx - self._period].close
                    bench_c_close = bench_curr.close
                    bench_p_close = bench_past.close

                    if asset_past <= 0.0 or bench_p_close <= 0.0 or bench_c_close <= 0.0:
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
                        asset_ret = (asset_curr - asset_past) / asset_past
                        bench_ret = (bench_c_close - bench_p_close) / bench_p_close
                        excess_return = (asset_ret - bench_ret) * 100.0
                        outperformance_ratio = (
                            (asset_curr / asset_past) / (bench_c_close / bench_p_close)
                        ) - 1.0

                        values.append(
                            IndicatorValue(
                                symbol=candle.symbol,
                                exchange=candle.exchange,
                                timeframe=candle.timeframe,
                                timestamp=candle.timestamp,
                                value={
                                    "excess_return": float(excess_return),
                                    "outperformance_ratio": float(outperformance_ratio),
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
