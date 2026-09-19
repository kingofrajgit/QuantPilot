"""Tests for RegimeEngine input validation and fail-closed contract enforcement."""

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from quantpilot.market_data.models import Timeframe
from quantpilot.regime.engine import RegimeEngine
from tests.unit.regime.conftest import (
    make_candle,
    make_dict_indicator_series,
    make_indicator_series,
)


def _build_full_indicator_mapping(
    timestamps: list[datetime],
    symbol: str = "TEST_SYM",
    exchange: str = "NSE",
    timeframe: Timeframe = Timeframe.M1,
) -> dict[str, Any]:
    n = len(timestamps)
    return {
        "price_vs_sma": make_indicator_series(
            "price_vs_sma",
            [0.01] * n,
            timestamps,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
        ),
        "sma_slope": make_indicator_series(
            "sma_slope",
            [0.1] * n,
            timestamps,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
        ),
        "ema_slope": make_indicator_series(
            "ema_slope",
            [0.1] * n,
            timestamps,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
        ),
        "sma": make_indicator_series(
            "sma",
            [100.0] * n,
            timestamps,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
        ),
        "rsi": make_indicator_series(
            "rsi",
            [60.0] * n,
            timestamps,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
        ),
        "roc": make_indicator_series(
            "roc",
            [1.0] * n,
            timestamps,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
        ),
        "macd": make_dict_indicator_series(
            "macd",
            [{"macd": 1.0, "signal": 0.5, "histogram": 0.5}] * n,
            timestamps,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
        ),
        "bollinger_bands": make_dict_indicator_series(
            "bollinger_bands",
            [{"bandwidth": 0.05}] * n,
            timestamps,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
        ),
        "rvol": make_indicator_series(
            "rvol", [1.0] * n, timestamps, symbol=symbol, exchange=exchange, timeframe=timeframe
        ),
        "obv": make_indicator_series(
            "obv", [1000.0] * n, timestamps, symbol=symbol, exchange=exchange, timeframe=timeframe
        ),
        "structure_breakout_distance": make_dict_indicator_series(
            "structure_breakout_distance",
            [
                {
                    "breakout_high": 0.0,
                    "breakdown_low": 0.0,
                    "dist_high": -1.0,
                    "dist_low": 1.0,
                }
            ]
            * n,
            timestamps,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
        ),
    }


def test_input_contract_empty_candles_raises() -> None:
    """Verify empty candles sequence raises ValueError."""
    engine = RegimeEngine()
    with pytest.raises(ValueError, match="Candle sequence must not be empty"):
        engine.evaluate([], {})


def test_input_contract_missing_required_indicators_raises() -> None:
    """Verify missing any required indicator series raises ValueError."""
    ts = [datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)]
    candles = [make_candle(ts[0])]
    engine = RegimeEngine()

    for required_name in RegimeEngine.REQUIRED_INDICATORS:
        full_mapping = _build_full_indicator_mapping(ts)
        del full_mapping[required_name]
        with pytest.raises(ValueError, match="Missing required indicator series"):
            engine.evaluate(candles, full_mapping)


def test_input_contract_length_mismatch_raises() -> None:
    """Verify indicator length mismatch against candles raises ValueError."""
    t0 = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=1)
    candles = [make_candle(t0), make_candle(t1)]  # 2 candles

    indicators_short = _build_full_indicator_mapping([t0])  # only 1 indicator point
    engine = RegimeEngine()
    with pytest.raises(ValueError, match="length mismatch"):
        engine.evaluate(candles, indicators_short)


def test_input_contract_timestamp_alignment_mismatch_raises() -> None:
    """Verify timestamp mismatch between candle and indicator at index t raises ValueError."""
    t0 = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=1)
    t1_wrong = t0 + timedelta(minutes=2)

    candles = [make_candle(t0), make_candle(t1)]
    indicators = _build_full_indicator_mapping([t0, t1_wrong])

    engine = RegimeEngine()
    with pytest.raises(ValueError, match="Timestamp alignment failure"):
        engine.evaluate(candles, indicators)


def test_input_contract_mixed_symbol_exchange_timeframe_raises() -> None:
    """Verify mixed symbol, exchange, or timeframe across inputs raises ValueError."""
    t0 = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    engine = RegimeEngine()

    # Mixed candle symbols
    c1 = make_candle(t0, symbol="SYM_A")
    c2 = make_candle(t0 + timedelta(minutes=1), symbol="SYM_B")
    mapping_a = _build_full_indicator_mapping([t0, t0 + timedelta(minutes=1)], symbol="SYM_A")
    with pytest.raises(ValueError, match="Mixed candle symbols"):
        engine.evaluate([c1, c2], mapping_a)

    # Indicator symbol mismatch
    c_valid = [make_candle(t0, symbol="SYM_A")]
    ind_wrong_sym = _build_full_indicator_mapping([t0], symbol="SYM_B")
    with pytest.raises(ValueError, match="symbol mismatch"):
        engine.evaluate(c_valid, ind_wrong_sym)
