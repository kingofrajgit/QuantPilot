"""Shared fixtures and synthetic candle helpers for quant engine tests."""

from datetime import datetime, timedelta, timezone

import pytest

from quantpilot.market_data.models import Candle, Timeframe


def make_candle(
    timestamp: datetime,
    close: float,
    open_: float | None = None,
    high: float | None = None,
    low: float | None = None,
    volume: float = 1000.0,
    symbol: str = "RELIANCE",
    exchange: str = "NSE",
    timeframe: Timeframe = Timeframe.D1,
) -> Candle:
    """Create a deterministic valid Candle fixture."""
    close_val = float(close)
    open_val = float(open_ if open_ is not None else close_val)
    high_val = float(high if high is not None else max(open_val, close_val))
    low_val = float(low if low is not None else min(open_val, close_val))
    return Candle(
        symbol=symbol,
        exchange=exchange,
        timeframe=timeframe,
        timestamp=timestamp,
        open=open_val,
        high=high_val,
        low=low_val,
        close=close_val,
        volume=float(volume),
    )


def make_candle_sequence(
    n: int,
    start_time: datetime | None = None,
    base_price: float = 100.0,
    symbol: str = "RELIANCE",
    exchange: str = "NSE",
    timeframe: Timeframe = Timeframe.D1,
    volume: float = 1000.0,
) -> list[Candle]:
    """Create a strictly increasing chronological candle sequence."""
    start = start_time or datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    candles = []
    for i in range(n):
        ts = start + timedelta(days=i)
        p = base_price + (i * 0.5)
        candles.append(
            make_candle(
                timestamp=ts,
                open_=p - 0.2,
                high=p + 1.0,
                low=p - 1.0,
                close=p,
                volume=volume,
                symbol=symbol,
                exchange=exchange,
                timeframe=timeframe,
            )
        )
    return candles


@pytest.fixture
def synthetic_candles_100() -> list[Candle]:
    return make_candle_sequence(100)
