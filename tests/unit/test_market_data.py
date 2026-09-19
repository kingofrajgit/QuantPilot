"""Comprehensive unit tests for canonical market data models, validation, and providers."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from quantpilot.market_data import (
    Candle,
    DataQualityReport,
    DataQualityStatus,
    Instrument,
    MarketSession,
    MockMarketDataProvider,
    Quote,
    Tick,
    Timeframe,
    ZerodhaMarketDataAdapter,
    check_staleness,
    detect_duplicates,
    detect_missing_candles,
    validate_candle,
    validate_candles,
)

UTC = timezone.utc
IST = timezone(timedelta(hours=5, minutes=30))


# =====================================================================
# 1. Model Tests: Instrument, MarketSession, DataQualityReport
# =====================================================================


def test_instrument_valid():
    """Verify valid instrument creation with whitespace trimming."""
    inst = Instrument(symbol="  INFY ", exchange=" NSE ", lot_size=1, tick_size=0.05)
    assert inst.symbol == "INFY"
    assert inst.exchange == "NSE"
    assert inst.lot_size == 1
    assert inst.tick_size == 0.05
    assert inst.is_active is True


def test_instrument_empty_fields_rejected():
    """Verify empty symbols or exchanges are rejected."""
    with pytest.raises(ValidationError):
        Instrument(symbol="   ", exchange="NSE")

    with pytest.raises(ValidationError):
        Instrument(symbol="INFY", exchange="")


def test_market_session_enum_values():
    """Verify standard market session enum values."""
    assert MarketSession.PRE_MARKET == "PRE_MARKET"
    assert MarketSession.OPEN == "OPEN"
    assert MarketSession.CLOSED == "CLOSED"
    assert MarketSession.POST_MARKET == "POST_MARKET"
    assert MarketSession.UNKNOWN == "UNKNOWN"


def test_data_quality_report_serialization():
    """Verify DataQualityReport structure and serialization."""
    now = datetime.now(UTC)
    report = DataQualityReport(
        status=DataQualityStatus.VALID,
        checks_run=["ohlc", "duplicates"],
        record_count=100,
        validated_at=now,
    )
    assert report.status == DataQualityStatus.VALID
    assert report.record_count == 100
    assert report.validated_at == now
    dump = report.model_dump()
    assert dump["status"] == "VALID"
    assert dump["record_count"] == 100


# =====================================================================
# 2. Timestamp Tests: Timezone Awareness & Normalization
# =====================================================================


def test_naive_datetime_rejected():
    """Verify naive datetimes are rejected with explicit error."""
    naive_ts = datetime(2026, 9, 19, 9, 15)  # No tzinfo
    with pytest.raises(ValidationError, match="Naive datetimes are rejected"):
        Candle(
            symbol="INFY",
            exchange="NSE",
            timestamp=naive_ts,
            timeframe=Timeframe.M5,
            open=1500.0,
            high=1510.0,
            low=1495.0,
            close=1505.0,
            volume=1000.0,
        )


def test_timezone_aware_normalized_to_utc():
    """Verify timezone-aware datetime is normalized to UTC."""
    ist_ts = datetime(2026, 9, 19, 9, 15, tzinfo=IST)
    candle = Candle(
        symbol="INFY",
        exchange="NSE",
        timestamp=ist_ts,
        timeframe=Timeframe.M5,
        open=1500.0,
        high=1510.0,
        low=1495.0,
        close=1505.0,
        volume=1000.0,
    )
    assert candle.timestamp.tzinfo == UTC
    # 09:15 IST is 03:45 UTC
    assert candle.timestamp.hour == 3
    assert candle.timestamp.minute == 45


# =====================================================================
# 3. Candle Validation Tests: OHLC, Price & Volume
# =====================================================================


def test_candle_valid():
    """Verify valid candle instantiates correctly."""
    ts = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)
    c = Candle(
        symbol="TCS",
        exchange="NSE",
        timestamp=ts,
        timeframe=Timeframe.M15,
        open=3500.0,
        high=3520.0,
        low=3490.0,
        close=3510.0,
        volume=25000.0,
    )
    assert c.open == 3500.0
    assert c.high == 3520.0
    assert c.low == 3490.0
    assert c.close == 3510.0
    assert c.volume == 25000.0
    assert validate_candle(c) == []


@pytest.mark.parametrize(
    ("open_p", "high_p", "low_p", "close_p", "match"),
    [
        (100.0, 90.0, 80.0, 95.0, "High .* cannot be less than Open"),
        (100.0, 102.0, 80.0, 105.0, "High .* cannot be less than Close"),
        (100.0, 105.0, 108.0, 102.0, "High .* cannot be less than Low"),
        (100.0, 110.0, 105.0, 108.0, "Low .* cannot be greater than Open"),
        (110.0, 115.0, 105.0, 100.0, "Low .* cannot be greater than Close"),
    ],
)
def test_candle_invalid_ohlc_relationships(open_p, high_p, low_p, close_p, match):
    """Verify all OHLC relationship violations are rejected."""
    ts = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)
    with pytest.raises(ValidationError, match=match):
        Candle(
            symbol="INFY",
            exchange="NSE",
            timestamp=ts,
            timeframe=Timeframe.M5,
            open=open_p,
            high=high_p,
            low=low_p,
            close=close_p,
            volume=100.0,
        )


def test_candle_zero_price_rejected():
    """Verify zero price is strictly rejected."""
    ts = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)
    with pytest.raises(ValidationError, match="greater than 0"):
        Candle(
            symbol="INFY",
            exchange="NSE",
            timestamp=ts,
            timeframe=Timeframe.M5,
            open=0.0,
            high=10.0,
            low=0.0,
            close=5.0,
            volume=100.0,
        )


def test_candle_negative_price_rejected():
    """Verify negative price is rejected."""
    ts = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)
    with pytest.raises(ValidationError, match="greater than 0"):
        Candle(
            symbol="INFY",
            exchange="NSE",
            timestamp=ts,
            timeframe=Timeframe.M5,
            open=100.0,
            high=110.0,
            low=-5.0,
            close=105.0,
            volume=100.0,
        )


def test_candle_negative_volume_rejected():
    """Verify negative volume is rejected."""
    ts = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        Candle(
            symbol="INFY",
            exchange="NSE",
            timestamp=ts,
            timeframe=Timeframe.M5,
            open=100.0,
            high=110.0,
            low=95.0,
            close=105.0,
            volume=-1.0,
        )


# =====================================================================
# 4. Quote Tests: Bid/Ask, Prices & Quantities
# =====================================================================


def test_quote_valid():
    """Verify valid quote creation with all fields."""
    ts = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)
    q = Quote(
        symbol="RELIANCE",
        exchange="NSE",
        timestamp=ts,
        last_price=2500.0,
        bid=2499.5,
        ask=2500.5,
        bid_qty=50.0,
        ask_qty=100.0,
        volume=100000.0,
    )
    assert q.last_price == 2500.0
    assert q.bid == 2499.5
    assert q.ask == 2500.5


def test_quote_bid_exceeding_ask_rejected():
    """Verify crossed market (bid > ask) is rejected."""
    ts = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)
    with pytest.raises(ValidationError, match="Bid .* cannot exceed Ask"):
        Quote(
            symbol="RELIANCE",
            exchange="NSE",
            timestamp=ts,
            last_price=2500.0,
            bid=2505.0,
            ask=2500.0,
        )


def test_quote_optional_bid_ask_allowed():
    """Verify quote without bid/ask is valid."""
    ts = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)
    q = Quote(symbol="RELIANCE", exchange="NSE", timestamp=ts, last_price=2500.0)
    assert q.bid is None
    assert q.ask is None


def test_quote_negative_quantities_rejected():
    """Verify negative bid or ask quantity is rejected."""
    ts = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        Quote(
            symbol="RELIANCE",
            exchange="NSE",
            timestamp=ts,
            last_price=2500.0,
            bid=2490.0,
            ask=2510.0,
            bid_qty=-10.0,
        )


# =====================================================================
# 5. Tick Tests
# =====================================================================


def test_tick_valid():
    """Verify valid Tick creation."""
    ts = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)
    tick = Tick(
        symbol="SBIN",
        exchange="NSE",
        timestamp=ts,
        last_price=750.0,
        last_quantity=25.0,
        total_volume=500000.0,
    )
    assert tick.last_price == 750.0
    assert tick.last_quantity == 25.0


def test_tick_invalid_price_or_quantity():
    """Verify invalid prices or negative quantities in ticks are rejected."""
    ts = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)
    with pytest.raises(ValidationError):
        Tick(
            symbol="SBIN",
            exchange="NSE",
            timestamp=ts,
            last_price=0.0,
            last_quantity=1.0,
            total_volume=0.0,
        )

    with pytest.raises(ValidationError):
        Tick(
            symbol="SBIN",
            exchange="NSE",
            timestamp=ts,
            last_price=750.0,
            last_quantity=-1.0,
            total_volume=0.0,
        )


# =====================================================================
# 6. Dataset-Level Validation: Duplicates, Ordering, Gaps
# =====================================================================


def _make_candle(
    symbol: str, exchange: str, tf: Timeframe, ts: datetime, base: float = 100.0
) -> Candle:
    return Candle(
        symbol=symbol,
        exchange=exchange,
        timeframe=tf,
        timestamp=ts,
        open=base,
        high=base + 5.0,
        low=base - 5.0,
        close=base + 1.0,
        volume=1000.0,
    )


def test_detect_duplicates():
    """Verify duplicate detection flags identical (symbol, exchange, tf, ts)."""
    t1 = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)
    t2 = datetime(2026, 9, 19, 10, 5, tzinfo=UTC)

    c1 = _make_candle("INFY", "NSE", Timeframe.M5, t1)
    c2 = _make_candle("INFY", "NSE", Timeframe.M5, t2)
    c3 = _make_candle("INFY", "NSE", Timeframe.M5, t1)  # Duplicate of c1

    dups = detect_duplicates([c1, c2, c3])
    assert len(dups) == 1
    assert dups[0][0] == 0  # first seen at index 0
    assert dups[0][1] == 2  # duplicate at index 2


def test_duplicates_across_different_symbols_not_flagged():
    """Verify same timestamp with different symbols is NOT a duplicate."""
    t1 = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)
    c1 = _make_candle("INFY", "NSE", Timeframe.M5, t1)
    c2 = _make_candle("TCS", "NSE", Timeframe.M5, t1)

    assert detect_duplicates([c1, c2]) == []


def test_duplicates_across_different_timeframes_not_flagged():
    """Verify same timestamp with different timeframes is NOT a duplicate."""
    t1 = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)
    c1 = _make_candle("INFY", "NSE", Timeframe.M5, t1)
    c2 = _make_candle("INFY", "NSE", Timeframe.M15, t1)

    assert detect_duplicates([c1, c2]) == []


def test_non_chronological_ordering_detected():
    """Verify validate_candles flags out-of-order records."""
    t1 = datetime(2026, 9, 19, 10, 5, tzinfo=UTC)
    t2 = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)

    c1 = _make_candle("INFY", "NSE", Timeframe.M5, t1)
    c2 = _make_candle("INFY", "NSE", Timeframe.M5, t2)

    report = validate_candles([c1, c2])
    assert report.status == DataQualityStatus.INVALID
    assert any("Non-chronological" in err for err in report.errors)


def test_detect_missing_candles():
    """Verify gap detection for missing expected timestamps."""
    t1 = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)
    t2 = datetime(2026, 9, 19, 10, 5, tzinfo=UTC)
    t3 = datetime(2026, 9, 19, 10, 20, tzinfo=UTC)  # 15m gap instead of 5m

    c1 = _make_candle("INFY", "NSE", Timeframe.M5, t1)
    c2 = _make_candle("INFY", "NSE", Timeframe.M5, t2)
    c3 = _make_candle("INFY", "NSE", Timeframe.M5, t3)

    gaps = detect_missing_candles([c1, c2, c3], expected_interval=timedelta(minutes=5))
    assert len(gaps) == 1
    assert gaps[0] == (t2, t3)


def test_validate_candles_complete_valid_dataset():
    """Verify valid sequence passes validation with status VALID."""
    provider = MockMarketDataProvider()
    t_start = datetime(2026, 9, 19, 9, 15, tzinfo=UTC)
    candles = provider.generate_synthetic_candles(
        symbol="INFY",
        exchange="NSE",
        timeframe=Timeframe.M5,
        count=5,
        start_time=t_start,
        interval=timedelta(minutes=5),
    )
    report = validate_candles(candles, expected_interval=timedelta(minutes=5))
    assert report.status == DataQualityStatus.VALID
    assert report.errors == []
    assert report.record_count == 5


# =====================================================================
# 7. Staleness Tests
# =====================================================================


def test_check_staleness_fresh():
    """Verify data within allowed age is not stale."""
    now = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)
    latest = datetime(2026, 9, 19, 9, 58, tzinfo=UTC)  # 2m old
    is_stale, age = check_staleness(latest, now, allowed_staleness=timedelta(minutes=5))
    assert is_stale is False
    assert age == timedelta(minutes=2)


def test_check_staleness_stale():
    """Verify data exceeding allowed age is flagged as stale."""
    now = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)
    latest = datetime(2026, 9, 19, 9, 50, tzinfo=UTC)  # 10m old
    is_stale, age = check_staleness(latest, now, allowed_staleness=timedelta(minutes=5))
    assert is_stale is True
    assert age == timedelta(minutes=10)


def test_check_staleness_exact_threshold():
    """Verify data exactly on allowed staleness threshold is not stale."""
    now = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)
    latest = datetime(2026, 9, 19, 9, 55, tzinfo=UTC)  # exactly 5m old
    is_stale, age = check_staleness(latest, now, allowed_staleness=timedelta(minutes=5))
    assert is_stale is False
    assert age == timedelta(minutes=5)


def test_check_staleness_future_timestamp_rejected():
    """Verify future timestamps raise ValueError and are never treated as fresh."""
    now = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)
    future = datetime(2026, 9, 19, 10, 5, tzinfo=UTC)
    with pytest.raises(ValueError, match="future relative to evaluation time"):
        check_staleness(future, now, allowed_staleness=timedelta(minutes=5))


# =====================================================================
# 8. Mock Market Data Provider Tests
# =====================================================================


def test_mock_provider_deterministic_generation():
    """Verify MockMarketDataProvider generates deterministic identical output for same inputs."""
    p1 = MockMarketDataProvider(seed=123)
    p2 = MockMarketDataProvider(seed=123)

    t0 = datetime(2026, 9, 19, 9, 15, tzinfo=UTC)
    candles1 = p1.generate_synthetic_candles("INFY", "NSE", Timeframe.M5, 5, t0)
    candles2 = p2.generate_synthetic_candles("INFY", "NSE", Timeframe.M5, 5, t0)

    assert len(candles1) == 5
    for c1, c2 in zip(candles1, candles2, strict=True):
        assert c1.open == c2.open
        assert c1.high == c2.high
        assert c1.low == c2.low
        assert c1.close == c2.close
        assert c1.timestamp == c2.timestamp


def test_mock_provider_fixtures_registration():
    """Verify mock provider returns registered fixtures."""
    provider = MockMarketDataProvider()
    inst = Instrument(symbol="ITC", exchange="NSE", lot_size=1)
    provider.register_instrument(inst)

    fetched_inst = provider.get_instrument("ITC", "NSE")
    assert fetched_inst == inst

    quote = Quote(
        symbol="ITC",
        exchange="NSE",
        timestamp=datetime.now(UTC),
        last_price=450.0,
    )
    provider.register_quote(quote)
    assert provider.get_latest_quote("ITC", "NSE") == quote


def test_mock_provider_market_session():
    """Verify market session retrieval and overrides in mock provider."""
    provider = MockMarketDataProvider()
    assert provider.get_market_session("NSE") == MarketSession.OPEN

    provider.set_market_session("NSE", MarketSession.CLOSED)
    assert provider.get_market_session("NSE") == MarketSession.CLOSED


# =====================================================================
# 9. Zerodha Market Data Adapter Boundary Tests
# =====================================================================


def test_zerodha_market_data_adapter_boundary_refusal():
    """Verify Zerodha adapter instantiates without network and safely raises NotImplementedError."""
    adapter = ZerodhaMarketDataAdapter()

    with pytest.raises(
        NotImplementedError, match="Live Zerodha market data ingestion is not implemented"
    ):
        adapter.get_instrument("INFY", "NSE")

    with pytest.raises(
        NotImplementedError, match="Live Zerodha market data ingestion is not implemented"
    ):
        adapter.get_latest_quote("INFY", "NSE")

    now = datetime.now(UTC)
    with pytest.raises(
        NotImplementedError, match="Live Zerodha market data ingestion is not implemented"
    ):
        adapter.get_historical_candles("INFY", "NSE", Timeframe.M5, now, now)

    with pytest.raises(
        NotImplementedError, match="Live Zerodha market data ingestion is not implemented"
    ):
        adapter.get_market_session("NSE")
