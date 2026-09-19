"""Shared test fixtures and synthetic series builders for regime testing."""

from datetime import datetime, timezone
from typing import Any

import pytest

from quantpilot.market_data.models import Candle, Timeframe
from quantpilot.quant.models import (
    IndicatorProvenance,
    IndicatorSeries,
    IndicatorStatus,
    IndicatorValue,
)


@pytest.fixture
def base_timestamp() -> datetime:
    return datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)


def make_candle(
    timestamp: datetime,
    open: float = 100.0,
    high: float | None = None,
    low: float | None = None,
    close: float = 102.0,
    volume: float = 1000.0,
    symbol: str = "TEST_SYM",
    exchange: str = "NSE",
    timeframe: Timeframe = Timeframe.M1,
) -> Candle:
    o = float(open)
    c = float(close)
    high_val = float(high if high is not None else max(o, c, 105.0))
    low_val = float(low if low is not None else min(o, c, 95.0))
    return Candle(
        symbol=symbol,
        exchange=exchange,
        timeframe=timeframe,
        timestamp=timestamp,
        open=o,
        high=high_val,
        low=low_val,
        close=c,
        volume=volume,
    )


def make_indicator_series(
    name: str,
    values: list[float | None],
    timestamps: list[datetime],
    status: IndicatorStatus = IndicatorStatus.VALID,
    symbol: str = "TEST_SYM",
    exchange: str = "NSE",
    timeframe: Timeframe = Timeframe.M1,
) -> IndicatorSeries:
    prov = IndicatorProvenance(
        indicator_name=name,
        indicator_version="1.0.0",
        lookback_period=14,
        source_window_start=timestamps[0] if timestamps else None,
        source_window_end=timestamps[-1] if timestamps else None,
        candles_analyzed=len(timestamps),
    )
    ind_vals = [
        IndicatorValue(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            timestamp=ts,
            value=val,
            status=status if val is not None else IndicatorStatus.INSUFFICIENT_DATA,
            provenance=prov,
        )
        for ts, val in zip(timestamps, values, strict=True)
    ]
    return IndicatorSeries(
        symbol=symbol,
        exchange=exchange,
        timeframe=timeframe,
        indicator_name=name,
        values=ind_vals,
    )


def make_dict_indicator_series(
    name: str,
    values: list[dict[str, Any] | None],
    timestamps: list[datetime],
    status: IndicatorStatus = IndicatorStatus.VALID,
    symbol: str = "TEST_SYM",
    exchange: str = "NSE",
    timeframe: Timeframe = Timeframe.M1,
) -> IndicatorSeries:
    prov = IndicatorProvenance(
        indicator_name=name,
        indicator_version="1.0.0",
        lookback_period=20,
        source_window_start=timestamps[0] if timestamps else None,
        source_window_end=timestamps[-1] if timestamps else None,
        candles_analyzed=len(timestamps),
    )
    ind_vals = [
        IndicatorValue(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            timestamp=ts,
            value=val,
            status=status if val is not None else IndicatorStatus.INSUFFICIENT_DATA,
            provenance=prov,
        )
        for ts, val in zip(timestamps, values, strict=True)
    ]
    return IndicatorSeries(
        symbol=symbol,
        exchange=exchange,
        timeframe=timeframe,
        indicator_name=name,
        values=ind_vals,
    )
