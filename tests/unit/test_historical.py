"""Comprehensive unit tests for Phase 2B Historical Market Data & Storage."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from quantpilot.exceptions import DataConflictError, DataValidationError
from quantpilot.market_data import (
    Candle,
    HistoricalDataRepository,
    HistoricalDatasetMetadata,
    LocalHistoricalDataProvider,
    ParquetHistoricalDataStore,
    Timeframe,
    ZerodhaHistoricalDataProvider,
    validate_historical_range,
)

UTC = timezone.utc
IST = timezone(timedelta(hours=5, minutes=30))


def _generate_test_candles(
    symbol: str = "RELIANCE",
    exchange: str = "NSE",
    timeframe: Timeframe = Timeframe.D1,
    count: int = 30,
    start_date: datetime | None = None,
    base_price: float = 2500.0,
) -> list[Candle]:
    """Generate deterministic synthetic candles for historical data testing."""
    start = start_date or datetime(2026, 1, 1, 9, 15, tzinfo=UTC)
    candles: list[Candle] = []

    price = base_price
    for i in range(count):
        ts = start + timedelta(days=i)
        fluctuation = (i % 7 - 3) * 5.0
        open_p = round(max(price, 100.0), 2)
        close_p = round(max(price + fluctuation, 100.0), 2)
        high_p = round(max(open_p, close_p) + 10.0, 2)
        low_p = round(min(open_p, close_p) - 10.0, 2)
        volume = float(50000 + (i * 1000))

        candles.append(
            Candle(
                symbol=symbol,
                exchange=exchange,
                timeframe=timeframe,
                timestamp=ts,
                open=open_p,
                high=high_p,
                low=low_p,
                close=close_p,
                volume=volume,
            )
        )
        price = close_p

    return candles


# =====================================================================
# 1. Range Validation Tests
# =====================================================================


def test_validate_historical_range_valid():
    """Verify valid range returns normalized UTC timestamps."""
    start = datetime(2026, 1, 1, 9, 15, tzinfo=IST)
    end = datetime(2026, 1, 10, 15, 30, tzinfo=IST)
    s_norm, e_norm = validate_historical_range(start, end)
    assert s_norm.tzinfo == IST
    assert e_norm.tzinfo == IST


def test_validate_historical_range_naive_rejected():
    """Verify naive datetimes in range check raise ValueError."""
    naive_start = datetime(2026, 1, 1, 9, 15)
    aware_end = datetime(2026, 1, 10, 15, 30, tzinfo=UTC)

    with pytest.raises(ValueError, match="start timestamp must be timezone-aware"):
        validate_historical_range(naive_start, aware_end)

    with pytest.raises(ValueError, match="end timestamp must be timezone-aware"):
        validate_historical_range(aware_end, naive_start)


def test_validate_historical_range_inverted_rejected():
    """Verify start > end raises ValueError."""
    start = datetime(2026, 1, 10, tzinfo=UTC)
    end = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="must be less than or equal to"):
        validate_historical_range(start, end)


# =====================================================================
# 2. Parquet Storage Engine Tests
# =====================================================================


def test_parquet_store_write_and_read_roundtrip(tmp_path: Path):
    """Verify round-trip preservation of all candle fields and UTC timestamps."""
    store = ParquetHistoricalDataStore(base_path=tmp_path)
    candles = _generate_test_candles(count=25)

    meta = store.write(candles)
    assert isinstance(meta, HistoricalDatasetMetadata)
    assert meta.record_count == 25
    assert meta.earliest_timestamp == candles[0].timestamp
    assert meta.latest_timestamp == candles[-1].timestamp
    assert meta.symbol == "RELIANCE"
    assert meta.exchange == "NSE"

    loaded = store.read("RELIANCE", "NSE", Timeframe.D1)
    assert len(loaded) == 25
    for original, read_back in zip(candles, loaded, strict=True):
        assert original.symbol == read_back.symbol
        assert original.exchange == read_back.exchange
        assert original.timeframe == read_back.timeframe
        assert original.timestamp == read_back.timestamp
        assert original.timestamp.tzinfo == UTC
        assert original.open == read_back.open
        assert original.high == read_back.high
        assert original.low == read_back.low
        assert original.close == read_back.close
        assert original.volume == read_back.volume


def test_parquet_store_read_with_date_range_filtering(tmp_path: Path):
    """Verify reading with start and end filtering slices records correctly."""
    store = ParquetHistoricalDataStore(base_path=tmp_path)
    candles = _generate_test_candles(count=30)
    store.write(candles)

    # Filter to intermediate 10 days
    start_filter = candles[5].timestamp
    end_filter = candles[15].timestamp

    filtered = store.read("RELIANCE", "NSE", Timeframe.D1, start=start_filter, end=end_filter)
    assert len(filtered) == 11
    assert filtered[0].timestamp == start_filter
    assert filtered[-1].timestamp == end_filter


def test_parquet_store_empty_read_non_existent(tmp_path: Path):
    """Verify reading a non-existent series returns empty list without error."""
    store = ParquetHistoricalDataStore(base_path=tmp_path)
    result = store.read("NON_EXISTENT", "NSE", Timeframe.D1)
    assert result == []
    assert store.exists("NON_EXISTENT", "NSE", Timeframe.D1) is False
    assert store.get_metadata("NON_EXISTENT", "NSE", Timeframe.D1) is None


def test_parquet_store_idempotent_repeated_writes(tmp_path: Path):
    """Verify writing the exact same candles repeatedly is idempotent and does not duplicate."""
    store = ParquetHistoricalDataStore(base_path=tmp_path)
    candles = _generate_test_candles(count=15)

    meta1 = store.write(candles)
    assert meta1.record_count == 15

    # Repeat write with identical records
    meta2 = store.write(candles)
    assert meta2.record_count == 15

    loaded = store.read("RELIANCE", "NSE", Timeframe.D1)
    assert len(loaded) == 15


def test_parquet_store_append_new_candles(tmp_path: Path):
    """Verify writing new chronological candles appends and updates metadata."""
    store = ParquetHistoricalDataStore(base_path=tmp_path)
    batch1 = _generate_test_candles(count=10, start_date=datetime(2026, 1, 1, tzinfo=UTC))
    meta1 = store.write(batch1)
    assert meta1.record_count == 10

    # Next batch starting day after batch1 ends
    batch2 = _generate_test_candles(count=10, start_date=datetime(2026, 1, 11, tzinfo=UTC))
    meta2 = store.write(batch2)
    assert meta2.record_count == 20
    assert meta2.earliest_timestamp == batch1[0].timestamp
    assert meta2.latest_timestamp == batch2[-1].timestamp

    loaded = store.read("RELIANCE", "NSE", Timeframe.D1)
    assert len(loaded) == 20
    assert loaded[0].timestamp == batch1[0].timestamp
    assert loaded[-1].timestamp == batch2[-1].timestamp


def test_parquet_store_conflicting_candle_rejected(tmp_path: Path):
    """Verify conflicting record for same key (different OHLCV) raises DataConflictError."""
    store = ParquetHistoricalDataStore(base_path=tmp_path)
    candles = _generate_test_candles(count=5)
    store.write(candles)

    # Create conflicting candle for candles[2].timestamp with different close price
    conflict_ts = candles[2].timestamp
    conflicting_candle = Candle(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe=Timeframe.D1,
        timestamp=conflict_ts,
        open=2500.0,
        high=2600.0,
        low=2400.0,
        close=2599.0,  # Different price
        volume=999999.0,
    )

    with pytest.raises(DataConflictError, match="Conflicting record for key"):
        store.write([conflicting_candle])


def test_parquet_store_rejects_non_chronological_batch(tmp_path: Path):
    """Verify store rejects non-chronological incoming batch via Phase 2A validation."""
    store = ParquetHistoricalDataStore(base_path=tmp_path)
    t1 = datetime(2026, 1, 5, tzinfo=UTC)
    t2 = datetime(2026, 1, 1, tzinfo=UTC)

    c1 = Candle(
        symbol="INFY",
        exchange="NSE",
        timeframe=Timeframe.D1,
        timestamp=t1,
        open=100.0,
        high=110.0,
        low=90.0,
        close=105.0,
        volume=1000.0,
    )
    c2 = Candle(
        symbol="INFY",
        exchange="NSE",
        timeframe=Timeframe.D1,
        timestamp=t2,
        open=100.0,
        high=110.0,
        low=90.0,
        close=105.0,
        volume=1000.0,
    )

    with pytest.raises(DataValidationError, match="Non-chronological"):
        store.write([c1, c2])


def test_parquet_store_rejects_batch_internal_duplicates(tmp_path: Path):
    """Verify store rejects a batch containing internal duplicates."""
    store = ParquetHistoricalDataStore(base_path=tmp_path)
    t1 = datetime(2026, 1, 1, tzinfo=UTC)
    c1 = Candle(
        symbol="INFY",
        exchange="NSE",
        timeframe=Timeframe.D1,
        timestamp=t1,
        open=100.0,
        high=110.0,
        low=90.0,
        close=105.0,
        volume=1000.0,
    )
    c2 = Candle(
        symbol="INFY",
        exchange="NSE",
        timeframe=Timeframe.D1,
        timestamp=t1,
        open=100.0,
        high=110.0,
        low=90.0,
        close=105.0,
        volume=1000.0,
    )

    with pytest.raises(DataValidationError, match="Duplicate candle detected"):
        store.write([c1, c2])


def test_parquet_store_list_and_delete(tmp_path: Path):
    """Verify list_datasets and delete operations."""
    store = ParquetHistoricalDataStore(base_path=tmp_path)
    candles_rel = _generate_test_candles(symbol="RELIANCE", count=10)
    candles_tcs = _generate_test_candles(symbol="TCS", count=10)

    store.write(candles_rel)
    store.write(candles_tcs)

    datasets = store.list_datasets()
    assert len(datasets) == 2
    symbols = {d.symbol for d in datasets}
    assert symbols == {"RELIANCE", "TCS"}

    deleted = store.delete("TCS", "NSE", Timeframe.D1)
    assert deleted is True
    assert store.exists("TCS", "NSE", Timeframe.D1) is False
    assert len(store.list_datasets()) == 1


# =====================================================================
# 3. Local Historical Provider Tests
# =====================================================================


def test_local_provider_retrieval(tmp_path: Path):
    """Verify LocalHistoricalDataProvider returns canonical candles from store."""
    store = ParquetHistoricalDataStore(base_path=tmp_path)
    candles = _generate_test_candles(count=20)
    store.write(candles)

    provider = LocalHistoricalDataProvider(store=store)
    result = provider.get_historical_candles(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe=Timeframe.D1,
        start=candles[0].timestamp,
        end=candles[10].timestamp,
    )

    assert len(result) == 11
    assert result[0].timestamp == candles[0].timestamp
    assert result[-1].timestamp == candles[10].timestamp


def test_local_provider_empty_outside_window(tmp_path: Path):
    """Verify LocalHistoricalDataProvider returns empty list when query is outside stored window."""
    store = ParquetHistoricalDataStore(base_path=tmp_path)
    candles = _generate_test_candles(count=10, start_date=datetime(2026, 1, 1, tzinfo=UTC))
    store.write(candles)

    provider = LocalHistoricalDataProvider(store=store)
    # Query in 2025
    result = provider.get_historical_candles(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe=Timeframe.D1,
        start=datetime(2025, 1, 1, tzinfo=UTC),
        end=datetime(2025, 1, 10, tzinfo=UTC),
    )
    assert result == []


# =====================================================================
# 4. Historical Data Repository (Query Interface) Tests
# =====================================================================


def test_repository_query_layer(tmp_path: Path):
    """Verify HistoricalDataRepository provides a clean high-level query interface."""
    repo = HistoricalDataRepository(base_path=tmp_path)
    candles = _generate_test_candles(count=30)
    repo.store_candles(candles)

    assert repo.has_data("RELIANCE", "NSE", Timeframe.D1) is True
    assert repo.has_data("INFY", "NSE", Timeframe.D1) is False

    meta = repo.get_metadata("RELIANCE", "NSE", Timeframe.D1)
    assert meta is not None
    assert meta.record_count == 30

    queried = repo.get_candles(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe=Timeframe.D1,
        start=candles[5].timestamp,
        end=candles[15].timestamp,
    )
    assert len(queried) == 11
    assert queried[0].timestamp == candles[5].timestamp
    assert queried[-1].timestamp == candles[15].timestamp

    # Chronological guarantee
    for i in range(len(queried) - 1):
        assert queried[i].timestamp < queried[i + 1].timestamp


# =====================================================================
# 5. Zerodha Historical Boundary Tests
# =====================================================================


def test_zerodha_historical_boundary():
    """Verify ZerodhaHistoricalDataProvider requires zero credentials and blocks execution."""
    # Must instantiate without credentials or errors
    provider = ZerodhaHistoricalDataProvider()

    now = datetime.now(UTC)
    with pytest.raises(
        NotImplementedError, match="Live Zerodha historical data retrieval is strictly deferred"
    ):
        provider.get_historical_candles(
            symbol="INFY",
            exchange="NSE",
            timeframe=Timeframe.D1,
            start=now,
            end=now,
        )


# =====================================================================
# 6. Complete End-to-End Pipeline Integration Test
# =====================================================================


def test_complete_historical_data_pipeline(tmp_path: Path):
    """Verify complete pipeline: Fixture -> Provider -> Validation -> Store -> Repository Query."""
    # 1. Deterministic synthetic fixture
    raw_candles = _generate_test_candles(symbol="TCS", exchange="NSE", count=25)

    # 2. Local Parquet Store with validation
    store = ParquetHistoricalDataStore(base_path=tmp_path)
    metadata = store.write(raw_candles)
    assert metadata.record_count == 25

    # 3. Local Provider reading from store
    provider = LocalHistoricalDataProvider(store=store)

    # 4. Repository Query
    repo = HistoricalDataRepository(store=store, provider=provider)
    result = repo.get_candles(
        symbol="TCS",
        exchange="NSE",
        timeframe=Timeframe.D1,
        start=raw_candles[0].timestamp,
        end=raw_candles[-1].timestamp,
    )

    # 5. Verification of canonical types and fidelity
    assert len(result) == 25
    assert all(isinstance(c, Candle) for c in result)
    assert result[0].symbol == "TCS"
    assert result[0].exchange == "NSE"
    assert result[0].timestamp.tzinfo == UTC
    assert result[-1].timestamp == raw_candles[-1].timestamp
