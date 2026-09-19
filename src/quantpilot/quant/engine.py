"""QuantEngine orchestrator: validates input candle series and coordinates calculations."""

import math
from datetime import datetime, timezone

from quantpilot.market_data.models import Candle, Timeframe
from quantpilot.market_data.repository import HistoricalDataRepository
from quantpilot.quant.base import BaseIndicator
from quantpilot.quant.models import IndicatorSeries
from quantpilot.quant.registry import IndicatorRegistry, default_registry


class QuantEngine:
    """Orchestrates quantitative evidence extraction from HistoricalDataRepository."""

    def __init__(
        self,
        repository: HistoricalDataRepository,
        registry: IndicatorRegistry | None = None,
    ) -> None:
        self.repository = repository
        self.registry = registry or default_registry

    def validate_candles(self, candles: list[Candle]) -> None:
        """Validate candle series fail-closed before any indicator calculation.

        Rejects:
        - Empty candle sequences
        - Non-ascending timestamps
        - Duplicate timestamps
        - Non-UTC timestamps
        - Mixed symbols
        - Mixed exchanges
        - Mixed timeframes
        - Non-finite values (NaN, +Inf, -Inf)
        - Invalid OHLC relationships
        - Negative volume
        """
        if not candles:
            raise ValueError("Candle series must not be empty")

        first = candles[0]
        expected_symbol = first.symbol
        expected_exchange = first.exchange
        expected_timeframe = first.timeframe

        prev_timestamp: datetime | None = None

        for idx, candle in enumerate(candles):
            # UTC check
            if candle.timestamp.tzinfo != timezone.utc:
                raise ValueError(
                    f"Candle at index {idx} has non-UTC timezone: {candle.timestamp.tzinfo}"
                )

            # Strictly monotonic ascending timestamps (also rejects duplicates)
            if prev_timestamp is not None:
                if candle.timestamp <= prev_timestamp:
                    raise ValueError(
                        f"Candle timestamps must be strictly ascending with no duplicates. "
                        f"Index {idx} ({candle.timestamp}) <= previous ({prev_timestamp})"
                    )
            prev_timestamp = candle.timestamp

            # Series identity uniformity
            if candle.symbol != expected_symbol:
                raise ValueError(
                    f"Mixed symbols at index {idx}: '{candle.symbol}' != '{expected_symbol}'"
                )
            if candle.exchange != expected_exchange:
                raise ValueError(
                    f"Mixed exchanges at index {idx}: '{candle.exchange}' != '{expected_exchange}'"
                )
            if candle.timeframe != expected_timeframe:
                raise ValueError(
                    f"Mixed timeframes at index {idx}: "
                    f"'{candle.timeframe}' != '{expected_timeframe}'"
                )

            # Finite checks
            for field_name, val in [
                ("open", candle.open),
                ("high", candle.high),
                ("low", candle.low),
                ("close", candle.close),
                ("volume", candle.volume),
            ]:
                if not math.isfinite(val):
                    raise ValueError(
                        f"Non-finite value detected in candle {idx} field '{field_name}': {val}"
                    )

            # Canonical OHLC relationships
            if candle.high < candle.low:
                raise ValueError(
                    f"Invalid OHLC at index {idx}: high ({candle.high}) < low ({candle.low})"
                )
            if candle.high < candle.open or candle.high < candle.close:
                raise ValueError(
                    f"Invalid OHLC at index {idx}: high ({candle.high}) must be >= open and close"
                )
            if candle.low > candle.open or candle.low > candle.close:
                raise ValueError(
                    f"Invalid OHLC at index {idx}: low ({candle.low}) must be <= open and close"
                )
            if candle.volume < 0:
                raise ValueError(f"Negative volume detected at index {idx}: {candle.volume}")

    def compute_from_candles(
        self,
        candles: list[Candle],
        indicators: list[str | BaseIndicator],
    ) -> dict[str, IndicatorSeries]:
        """Compute indicator series from an in-memory candle sequence after strict validation."""
        self.validate_candles(candles)

        results: dict[str, IndicatorSeries] = {}

        for item in indicators:
            if isinstance(item, str):
                indicator = self.registry.get(item)
            elif isinstance(item, BaseIndicator):
                indicator = item
            else:
                raise TypeError(
                    f"Indicator specification must be str or BaseIndicator, got {type(item)}"
                )

            series = indicator.calculate_series(candles)
            results[indicator.name] = series

        return results

    def compute(
        self,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
        indicators: list[str | BaseIndicator],
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, IndicatorSeries]:
        """Fetch historical candles via repository and compute requested indicator series."""
        candles = self.repository.get_candles(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            start=start_time,
            end=end_time,
        )
        if not candles:
            raise ValueError(
                f"No candles found in repository for {symbol}:{exchange}:{timeframe.value}"
            )

        return self.compute_from_candles(candles, indicators)
