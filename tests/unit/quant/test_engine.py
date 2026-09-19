"""Unit tests for QuantEngine fail-closed validation and coordination."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from quantpilot.market_data.models import Candle, Timeframe
from quantpilot.quant.engine import QuantEngine
from quantpilot.quant.models import IndicatorStatus
from tests.unit.quant.conftest import make_candle, make_candle_sequence


def test_engine_rejects_empty_candles() -> None:
    engine = QuantEngine(repository=MagicMock())
    with pytest.raises(ValueError, match="must not be empty"):
        engine.validate_candles([])


def test_engine_rejects_non_utc_timestamps() -> None:
    engine = QuantEngine(repository=MagicMock())
    bad_ts = datetime(2026, 1, 1, 10, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    candle = Candle.model_construct(
        symbol="INFY",
        exchange="NSE",
        timeframe=Timeframe.D1,
        timestamp=bad_ts,
        open=100.0,
        high=105.0,
        low=95.0,
        close=100.0,
        volume=100.0,
    )
    with pytest.raises(ValueError, match="non-UTC"):
        engine.validate_candles([candle])


def test_engine_rejects_unsorted_timestamps() -> None:
    engine = QuantEngine(repository=MagicMock())
    t1 = datetime(2026, 1, 2, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    c1 = make_candle(timestamp=t1, close=100.0)
    c2 = make_candle(timestamp=t2, close=101.0)
    with pytest.raises(ValueError, match="strictly ascending"):
        engine.validate_candles([c1, c2])


def test_engine_rejects_duplicate_timestamps() -> None:
    engine = QuantEngine(repository=MagicMock())
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    c1 = make_candle(timestamp=t1, close=100.0)
    c2 = make_candle(timestamp=t1, close=100.0)
    with pytest.raises(ValueError, match="strictly ascending with no duplicates"):
        engine.validate_candles([c1, c2])


def test_engine_rejects_mixed_series_identity() -> None:
    engine = QuantEngine(repository=MagicMock())
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 2, tzinfo=timezone.utc)

    # Mixed symbol
    c1 = make_candle(timestamp=t1, close=100.0, symbol="INFY")
    c2 = make_candle(timestamp=t2, close=101.0, symbol="TCS")
    with pytest.raises(ValueError, match="Mixed symbols"):
        engine.validate_candles([c1, c2])

    # Mixed exchange
    c3 = make_candle(timestamp=t2, close=101.0, symbol="INFY", exchange="BSE")
    with pytest.raises(ValueError, match="Mixed exchanges"):
        engine.validate_candles([c1, c3])

    # Mixed timeframe
    c4 = make_candle(
        timestamp=t2, close=101.0, symbol="INFY", exchange="NSE", timeframe=Timeframe.M15
    )
    with pytest.raises(ValueError, match="Mixed timeframes"):
        engine.validate_candles([c1, c4])


def test_engine_rejects_invalid_ohlcv() -> None:
    engine = QuantEngine(repository=MagicMock())
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)

    # high < low
    with pytest.raises(ValueError, match="high .* < low"):
        c = Candle.model_construct(
            symbol="INFY",
            exchange="NSE",
            timeframe=Timeframe.D1,
            timestamp=t,
            open=100.0,
            high=90.0,
            low=95.0,
            close=100.0,
            volume=100.0,
        )
        engine.validate_candles([c])

    # negative volume
    with pytest.raises(ValueError, match="Negative volume"):
        c = Candle.model_construct(
            symbol="INFY",
            exchange="NSE",
            timeframe=Timeframe.D1,
            timestamp=t,
            open=100.0,
            high=105.0,
            low=95.0,
            close=100.0,
            volume=-10.0,
        )
        engine.validate_candles([c])

    # non-finite value (NaN)
    with pytest.raises(ValueError, match="Non-finite value"):
        c = Candle.model_construct(
            symbol="INFY",
            exchange="NSE",
            timeframe=Timeframe.D1,
            timestamp=t,
            open=100.0,
            high=105.0,
            low=95.0,
            close=float("nan"),
            volume=100.0,
        )
        engine.validate_candles([c])


def test_engine_compute_from_candles() -> None:
    engine = QuantEngine(repository=MagicMock())
    candles = make_candle_sequence(30)
    results = engine.compute_from_candles(candles, indicators=["sma", "rsi"])

    assert "sma" in results
    assert "rsi" in results
    assert len(results["sma"].values) == 30
    assert len(results["rsi"].values) == 30
    assert results["sma"].values[-1].status == IndicatorStatus.VALID
    assert results["rsi"].values[-1].status == IndicatorStatus.VALID


def test_engine_compute_via_repository() -> None:
    repo = MagicMock()
    candles = make_candle_sequence(25)
    repo.get_candles.return_value = candles

    engine = QuantEngine(repository=repo)
    results = engine.compute(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe=Timeframe.D1,
        indicators=["sma"],
    )

    repo.get_candles.assert_called_once_with(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe=Timeframe.D1,
        start=None,
        end=None,
    )
    assert "sma" in results
    assert len(results["sma"].values) == 25


def test_engine_compute_repository_empty_raises() -> None:
    repo = MagicMock()
    repo.get_candles.return_value = []

    engine = QuantEngine(repository=repo)
    with pytest.raises(ValueError, match="No candles found"):
        engine.compute(
            symbol="RELIANCE",
            exchange="NSE",
            timeframe=Timeframe.D1,
            indicators=["sma"],
        )
