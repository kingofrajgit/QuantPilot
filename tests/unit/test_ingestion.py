"""Unit tests for Phase 2C Historical Data Ingestion, Dataset Management, and CLI."""

import csv
import unittest.mock as mock
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from quantpilot.cli import main
from quantpilot.config.settings import PROJECT_ROOT, Settings, resolve_project_path
from quantpilot.market_data.ingestion_models import (
    IngestionFormat,
    IngestionRunStatus,
)
from quantpilot.market_data.ingestion_service import HistoricalDataIngestionService
from quantpilot.market_data.models import Candle, Timeframe
from quantpilot.market_data.parquet_store import ParquetHistoricalDataStore

# -----------------------------------------------------------------------------
# Synthetic Data Fixture Generator (30 daily candles)
# -----------------------------------------------------------------------------


def generate_synthetic_daily_candles(
    count: int = 30,
    symbol: str = "RELIANCE",
    exchange: str = "NSE",
    start_dt: datetime | None = None,
) -> list[Candle]:
    """Generate deterministic synthetic daily candles."""
    if start_dt is None:
        start_dt = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    candles = []
    base_price = 2500.0

    for i in range(count):
        ts = start_dt + timedelta(days=i)
        op = base_price + (i * 2.0)
        hi = op + 15.0
        lo = op - 10.0
        cl = op + 5.0
        vo = 100000.0 + (i * 1000.0)
        candles.append(
            Candle(
                symbol=symbol,
                exchange=exchange,
                timeframe=Timeframe.D1,
                timestamp=ts,
                open=op,
                high=hi,
                low=lo,
                close=cl,
                volume=vo,
            )
        )
    return candles


def write_csv_file(path: Path, candles: list[Candle], header_case: str = "lower") -> None:
    """Write candles to a CSV file with specified header formatting."""
    if header_case == "upper":
        headers = ["TIMESTAMP", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"]
    elif header_case == "mixed":
        headers = [" Timestamp ", "Open", " High", "Low ", "Close", "Volume "]
    else:
        headers = ["timestamp", "open", "high", "low", "close", "volume"]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for c in candles:
            writer.writerow([c.timestamp.isoformat(), c.open, c.high, c.low, c.close, c.volume])


def write_parquet_file(path: Path, candles: list[Candle]) -> None:
    """Write candles to a Parquet file."""
    table = pa.Table.from_arrays(
        [
            pa.array([c.timestamp for c in candles], type=pa.timestamp("us", tz="UTC")),
            pa.array([c.open for c in candles], type=pa.float64()),
            pa.array([c.high for c in candles], type=pa.float64()),
            pa.array([c.low for c in candles], type=pa.float64()),
            pa.array([c.close for c in candles], type=pa.float64()),
            pa.array([c.volume for c in candles], type=pa.float64()),
        ],
        names=["timestamp", "open", "high", "low", "close", "volume"],
    )
    pq.write_table(table, path)


# -----------------------------------------------------------------------------
# 1 & 2. PROJECT_ROOT & Deterministic Path Resolution Tests
# -----------------------------------------------------------------------------


def test_project_root_resolution():
    """Verify PROJECT_ROOT points to repo root containing pyproject.toml."""
    assert (PROJECT_ROOT / "pyproject.toml").exists()
    assert (PROJECT_ROOT / "src" / "quantpilot").exists()

    # Relative paths resolve to <repo>/...
    resolved_hist = resolve_project_path(Path("./data/historical"))
    assert resolved_hist == (PROJECT_ROOT / "data" / "historical").resolve()

    resolved_logs = resolve_project_path("./logs")
    assert resolved_logs == (PROJECT_ROOT / "logs").resolve()


def test_path_resolution_independent_of_cwd(tmp_path, monkeypatch):
    """Verify that path resolution against PROJECT_ROOT is identical regardless of cwd."""
    # Change working directory to tmp_path
    monkeypatch.chdir(tmp_path)

    rel_path = Path("./data/historical")
    resolved = resolve_project_path(rel_path)
    assert resolved == (PROJECT_ROOT / "data" / "historical").resolve()
    assert not str(resolved).startswith(str(tmp_path))

    # Absolute paths remain unchanged
    abs_path = (tmp_path / "custom" / "storage").resolve()
    assert resolve_project_path(abs_path) == abs_path


def test_settings_resolved_paths():
    """Verify Settings provides resolved properties for historical data and logs."""
    settings = Settings()
    assert settings.resolved_historical_data_path.is_absolute()
    assert settings.resolved_log_path.is_absolute()


# -----------------------------------------------------------------------------
# 3, 4, 5. CSV & Parquet Ingestion & Column Normalization Tests
# -----------------------------------------------------------------------------


def test_csv_ingestion_valid(tmp_path):
    """Verify valid CSV ingestion with 30 synthetic daily candles."""
    store = ParquetHistoricalDataStore(base_path=tmp_path / "store")
    service = HistoricalDataIngestionService(store=store)

    candles = generate_synthetic_daily_candles(30)
    csv_file = tmp_path / "reliance_30.csv"
    write_csv_file(csv_file, candles)

    summary = service.ingest(
        source_path=csv_file,
        source_format=IngestionFormat.CSV,
        symbol="RELIANCE",
        exchange="NSE",
        timeframe=Timeframe.D1,
    )

    assert summary.status == IngestionRunStatus.SUCCESS
    assert summary.records_read == 30
    assert summary.records_written == 30
    assert summary.records_skipped == 0
    assert summary.duplicates == 0
    assert summary.conflicts == 0
    assert summary.validation_failures == 0
    assert len(summary.errors) == 0

    # Verify store content
    stored = store.read("RELIANCE", "NSE", Timeframe.D1)
    assert len(stored) == 30
    assert stored[0].timestamp == candles[0].timestamp
    assert stored[-1].timestamp == candles[-1].timestamp


def test_parquet_ingestion_valid(tmp_path):
    """Verify valid Parquet ingestion with 30 synthetic daily candles."""
    store = ParquetHistoricalDataStore(base_path=tmp_path / "store")
    service = HistoricalDataIngestionService(store=store)

    candles = generate_synthetic_daily_candles(30)
    parquet_file = tmp_path / "reliance_30.parquet"
    write_parquet_file(parquet_file, candles)

    summary = service.ingest(
        source_path=parquet_file,
        source_format=IngestionFormat.PARQUET,
        symbol="RELIANCE",
        exchange="NSE",
        timeframe=Timeframe.D1,
    )

    assert summary.status == IngestionRunStatus.SUCCESS
    assert summary.records_read == 30
    assert summary.records_written == 30
    assert len(store.read("RELIANCE", "NSE", Timeframe.D1)) == 30


def test_csv_column_normalization(tmp_path):
    """Verify CSV header case-insensitivity, aliases, and whitespace stripping."""
    store = ParquetHistoricalDataStore(base_path=tmp_path / "store")
    service = HistoricalDataIngestionService(store=store)

    candles = generate_synthetic_daily_candles(5)
    csv_file = tmp_path / "reliance_mixed_cols.csv"
    write_csv_file(csv_file, candles, header_case="mixed")

    summary = service.ingest(
        source_path=csv_file,
        source_format="csv",
        symbol="RELIANCE",
        exchange="NSE",
        timeframe="1d",
    )

    assert summary.status == IngestionRunStatus.SUCCESS
    assert summary.records_written == 5


# -----------------------------------------------------------------------------
# 6, 7, 8. Missing Columns, Invalid Timestamps & Timezone Normalization
# -----------------------------------------------------------------------------


def test_csv_missing_required_column(tmp_path):
    """Verify that missing required columns fail the ingestion atomically."""
    store = ParquetHistoricalDataStore(base_path=tmp_path / "store")
    service = HistoricalDataIngestionService(store=store)

    csv_file = tmp_path / "missing_open.csv"
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "high", "low", "close", "volume"])
        writer.writerow(["2026-01-01T09:15:00Z", 2515.0, 2490.0, 2505.0, 100000.0])

    summary = service.ingest(
        source_path=csv_file,
        source_format=IngestionFormat.CSV,
        symbol="RELIANCE",
        exchange="NSE",
        timeframe=Timeframe.D1,
    )

    assert summary.status == IngestionRunStatus.FAILED
    assert summary.records_written == 0
    assert any("Missing required CSV column" in err for err in summary.errors)


def test_naive_timestamp_rejected_without_timezone(tmp_path):
    """Verify naive timestamps are rejected when no source_timezone is provided."""
    store = ParquetHistoricalDataStore(base_path=tmp_path / "store")
    service = HistoricalDataIngestionService(store=store)

    csv_file = tmp_path / "naive_ts.csv"
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        writer.writerow(["2026-01-01 09:15:00", 2500.0, 2515.0, 2490.0, 2505.0, 100000.0])

    summary = service.ingest(
        source_path=csv_file,
        source_format=IngestionFormat.CSV,
        symbol="RELIANCE",
        exchange="NSE",
        timeframe=Timeframe.D1,
    )

    assert summary.status == IngestionRunStatus.FAILED
    assert summary.records_written == 0
    assert any("Naive timestamp" in err for err in summary.errors)


def test_naive_timestamp_accepted_with_source_timezone(tmp_path):
    """Verify naive timestamps are localized with source_timezone and normalized to UTC."""
    store = ParquetHistoricalDataStore(base_path=tmp_path / "store")
    service = HistoricalDataIngestionService(store=store)

    csv_file = tmp_path / "naive_with_tz.csv"
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        # 09:15:00 IST is 03:45:00 UTC
        writer.writerow(["2026-01-01 09:15:00", 2500.0, 2515.0, 2490.0, 2505.0, 100000.0])

    summary = service.ingest(
        source_path=csv_file,
        source_format=IngestionFormat.CSV,
        symbol="RELIANCE",
        exchange="NSE",
        timeframe=Timeframe.D1,
        source_timezone="Asia/Kolkata",
    )

    assert summary.status == IngestionRunStatus.SUCCESS
    assert summary.records_written == 1

    stored = store.read("RELIANCE", "NSE", Timeframe.D1)
    assert stored[0].timestamp == datetime(2026, 1, 1, 3, 45, tzinfo=timezone.utc)


# -----------------------------------------------------------------------------
# 9, 10, 11, 12. Non-finite (NaN, Inf) and Invalid OHLCV Tests
# -----------------------------------------------------------------------------


def test_nan_rejected(tmp_path):
    """Verify NaN in any OHLCV field causes atomic rejection."""
    store = ParquetHistoricalDataStore(base_path=tmp_path / "store")
    service = HistoricalDataIngestionService(store=store)

    csv_file = tmp_path / "nan_candle.csv"
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        writer.writerow(["2026-01-01T09:15:00Z", "NaN", 2515.0, 2490.0, 2505.0, 100000.0])

    summary = service.ingest(
        source_path=csv_file,
        source_format=IngestionFormat.CSV,
        symbol="RELIANCE",
        exchange="NSE",
        timeframe=Timeframe.D1,
    )

    assert summary.status == IngestionRunStatus.FAILED
    assert summary.records_written == 0
    assert any("non-finite value" in err for err in summary.errors)


def test_inf_rejected(tmp_path):
    """Verify Infinity in any OHLCV field causes atomic rejection."""
    store = ParquetHistoricalDataStore(base_path=tmp_path / "store")
    service = HistoricalDataIngestionService(store=store)

    csv_file = tmp_path / "inf_candle.csv"
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        writer.writerow(["2026-01-01T09:15:00Z", 2500.0, "Infinity", 2490.0, 2505.0, 100000.0])

    summary = service.ingest(
        source_path=csv_file,
        source_format=IngestionFormat.CSV,
        symbol="RELIANCE",
        exchange="NSE",
        timeframe=Timeframe.D1,
    )

    assert summary.status == IngestionRunStatus.FAILED
    assert summary.records_written == 0
    assert any("non-finite value" in err for err in summary.errors)


def test_invalid_ohlc_relationships_rejected(tmp_path):
    """Verify High < Low or Close > High is rejected atomically."""
    store = ParquetHistoricalDataStore(base_path=tmp_path / "store")
    service = HistoricalDataIngestionService(store=store)

    csv_file = tmp_path / "invalid_ohlc.csv"
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        # High (2480) is less than Low (2490)
        writer.writerow(["2026-01-01T09:15:00Z", 2500.0, 2480.0, 2490.0, 2505.0, 100000.0])

    summary = service.ingest(
        source_path=csv_file,
        source_format=IngestionFormat.CSV,
        symbol="RELIANCE",
        exchange="NSE",
        timeframe=Timeframe.D1,
    )

    assert summary.status == IngestionRunStatus.FAILED
    assert summary.records_written == 0


def test_invalid_negative_volume_rejected(tmp_path):
    """Verify negative volume is rejected atomically."""
    store = ParquetHistoricalDataStore(base_path=tmp_path / "store")
    service = HistoricalDataIngestionService(store=store)

    csv_file = tmp_path / "neg_volume.csv"
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        writer.writerow(["2026-01-01T09:15:00Z", 2500.0, 2515.0, 2490.0, 2505.0, -100.0])

    summary = service.ingest(
        source_path=csv_file,
        source_format=IngestionFormat.CSV,
        symbol="RELIANCE",
        exchange="NSE",
        timeframe=Timeframe.D1,
    )

    assert summary.status == IngestionRunStatus.FAILED
    assert summary.records_written == 0


# -----------------------------------------------------------------------------
# 13, 14, 15, 16, 17. In-batch / Store Duplicates & Conflict Rejection
# -----------------------------------------------------------------------------


def test_in_batch_identical_duplicate_idempotent(tmp_path):
    """Verify identical in-batch duplicates are counted and 1 candle is written."""
    store = ParquetHistoricalDataStore(base_path=tmp_path / "store")
    service = HistoricalDataIngestionService(store=store)

    candles = generate_synthetic_daily_candles(1)
    csv_file = tmp_path / "duplicate_batch.csv"
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        c = candles[0]
        # Write same row twice
        writer.writerow([c.timestamp.isoformat(), c.open, c.high, c.low, c.close, c.volume])
        writer.writerow([c.timestamp.isoformat(), c.open, c.high, c.low, c.close, c.volume])

    summary = service.ingest(
        source_path=csv_file,
        source_format=IngestionFormat.CSV,
        symbol="RELIANCE",
        exchange="NSE",
        timeframe=Timeframe.D1,
    )

    assert summary.status == IngestionRunStatus.SUCCESS
    assert summary.records_read == 2
    assert summary.records_written == 1
    assert summary.duplicates == 1
    assert summary.conflicts == 0


def test_in_batch_conflicting_duplicate_aborts_all(tmp_path):
    """Verify that conflicting records in the same batch fail the entire ingestion."""
    store = ParquetHistoricalDataStore(base_path=tmp_path / "store")
    service = HistoricalDataIngestionService(store=store)

    c1 = generate_synthetic_daily_candles(1)[0]
    csv_file = tmp_path / "conflict_batch.csv"
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        writer.writerow([c1.timestamp.isoformat(), c1.open, c1.high, c1.low, c1.close, c1.volume])
        # Same timestamp, different Close price
        writer.writerow(
            [c1.timestamp.isoformat(), c1.open, c1.high, c1.low, c1.close + 10.0, c1.volume]
        )

    summary = service.ingest(
        source_path=csv_file,
        source_format=IngestionFormat.CSV,
        symbol="RELIANCE",
        exchange="NSE",
        timeframe=Timeframe.D1,
    )

    assert summary.status == IngestionRunStatus.FAILED
    assert summary.records_written == 0
    assert summary.conflicts == 1
    assert not store.exists("RELIANCE", "NSE", Timeframe.D1)


def test_store_duplicate_idempotent_skipping(tmp_path):
    """Verify that re-ingesting already-stored candles skips them idempotently."""
    store = ParquetHistoricalDataStore(base_path=tmp_path / "store")
    service = HistoricalDataIngestionService(store=store)

    candles = generate_synthetic_daily_candles(10)
    csv_file = tmp_path / "candles_10.csv"
    write_csv_file(csv_file, candles)

    # First ingestion
    s1 = service.ingest(csv_file, "csv", "RELIANCE", "NSE", "1d")
    assert s1.status == IngestionRunStatus.SUCCESS
    assert s1.records_written == 10

    # Re-ingestion of same file
    s2 = service.ingest(csv_file, "csv", "RELIANCE", "NSE", "1d")
    assert s2.status == IngestionRunStatus.SUCCESS
    assert s2.records_written == 0
    assert s2.records_skipped == 10
    assert s2.duplicates == 10
    assert s2.conflicts == 0


def test_atomic_conflict_rejection_mandate(tmp_path):
    """Mandatory test: 1 conflict in a batch of 30 candles results in ZERO candles written."""
    store = ParquetHistoricalDataStore(base_path=tmp_path / "store")
    service = HistoricalDataIngestionService(store=store)

    existing = generate_synthetic_daily_candles(5)
    csv_initial = tmp_path / "initial.csv"
    write_csv_file(csv_initial, existing)
    service.ingest(csv_initial, "csv", "RELIANCE", "NSE", "1d")

    # Second batch of 10 candles: candle at index 2 conflicts with existing[2]
    incoming = generate_synthetic_daily_candles(10)
    # Mutate index 2 to create a conflict
    bad_c = incoming[2]
    incoming[2] = Candle(
        symbol=bad_c.symbol,
        exchange=bad_c.exchange,
        timeframe=bad_c.timeframe,
        timestamp=bad_c.timestamp,
        open=bad_c.open,
        high=bad_c.high + 50.0,
        low=bad_c.low,
        close=bad_c.close + 40.0,
        volume=bad_c.volume,
    )

    csv_batch = tmp_path / "batch_with_one_conflict.csv"
    write_csv_file(csv_batch, incoming)

    summary = service.ingest(csv_batch, "csv", "RELIANCE", "NSE", "1d")

    # Invariant check: ZERO new candles written
    assert summary.status == IngestionRunStatus.FAILED
    assert summary.records_written == 0
    assert summary.conflicts >= 1

    # Store must still have exactly the 5 initial candles, untouched!
    stored = store.read("RELIANCE", "NSE", Timeframe.D1)
    assert len(stored) == 5
    assert stored[2].high == existing[2].high


# -----------------------------------------------------------------------------
# 18, 19, 20. Incremental Ingestion & Date Filtering
# -----------------------------------------------------------------------------


def test_incremental_ingestion_new_and_overlapping(tmp_path):
    """Verify incremental ingestion appends new candles while skipping overlapping ones."""
    store = ParquetHistoricalDataStore(base_path=tmp_path / "store")
    service = HistoricalDataIngestionService(store=store)

    all_candles = generate_synthetic_daily_candles(30)
    batch1 = all_candles[:15]
    batch2 = all_candles[10:30]  # Overlaps on indices 10..14 (5 candles)

    f1 = tmp_path / "b1.csv"
    f2 = tmp_path / "b2.csv"
    write_csv_file(f1, batch1)
    write_csv_file(f2, batch2)

    s1 = service.ingest(f1, "csv", "RELIANCE", "NSE", "1d")
    assert s1.records_written == 15

    s2 = service.ingest(f2, "csv", "RELIANCE", "NSE", "1d")
    assert s2.status == IngestionRunStatus.SUCCESS
    assert s2.records_written == 15  # 20 - 5 overlapping
    assert s2.records_skipped == 5
    assert s2.duplicates == 5

    stored = store.read("RELIANCE", "NSE", Timeframe.D1)
    assert len(stored) == 30


def test_date_filtering(tmp_path):
    """Verify filtering candles by start_time and end_time."""
    store = ParquetHistoricalDataStore(base_path=tmp_path / "store")
    service = HistoricalDataIngestionService(store=store)

    candles = generate_synthetic_daily_candles(30)
    f = tmp_path / "full.csv"
    write_csv_file(f, candles)

    start_filter = candles[5].timestamp
    end_filter = candles[14].timestamp

    summary = service.ingest(
        source_path=f,
        source_format="csv",
        symbol="RELIANCE",
        exchange="NSE",
        timeframe="1d",
        start_time=start_filter,
        end_time=end_filter,
    )

    assert summary.status == IngestionRunStatus.SUCCESS
    assert summary.records_written == 10
    assert summary.earliest_timestamp == start_filter
    assert summary.latest_timestamp == end_filter


def test_invalid_date_range_rejected(tmp_path):
    """Verify start_time > end_time is rejected."""
    store = ParquetHistoricalDataStore(base_path=tmp_path / "store")
    service = HistoricalDataIngestionService(store=store)

    f = tmp_path / "dummy.csv"
    write_csv_file(f, generate_synthetic_daily_candles(5))

    start = datetime(2026, 1, 10, tzinfo=timezone.utc)
    end = datetime(2026, 1, 5, tzinfo=timezone.utc)

    summary = service.ingest(
        source_path=f,
        source_format="csv",
        symbol="RELIANCE",
        exchange="NSE",
        timeframe="1d",
        start_time=start,
        end_time=end,
    )

    assert summary.status == IngestionRunStatus.FAILED
    assert summary.records_written == 0
    assert any("Invalid date range" in err for err in summary.errors)


# -----------------------------------------------------------------------------
# 21, 22. Dataset Coverage & Conservative Gap Detection
# -----------------------------------------------------------------------------


def test_coverage_report_and_gap_detection(tmp_path):
    """Verify coverage report and conservative gap detection with disclaimer."""
    store = ParquetHistoricalDataStore(base_path=tmp_path / "store")
    service = HistoricalDataIngestionService(store=store)

    # Create dataset with an intentional gap of 5 days
    c1 = generate_synthetic_daily_candles(5, start_dt=datetime(2026, 1, 1, tzinfo=timezone.utc))
    c2 = generate_synthetic_daily_candles(5, start_dt=datetime(2026, 1, 11, tzinfo=timezone.utc))

    store.write(c1)
    store.write(c2)

    coverage = service.check_coverage("RELIANCE", "NSE", Timeframe.D1)

    assert coverage.record_count == 10
    assert coverage.has_potential_gaps is True
    assert coverage.potential_gap_count == 1
    assert "Phase 2C does not yet provide exchange-calendar-aware" in coverage.disclaimer
    assert len(coverage.gap_details) == 1


# -----------------------------------------------------------------------------
# 23, 24. CLI Tests (Relative & Absolute Source Paths)
# -----------------------------------------------------------------------------


def test_cli_ingestion_relative_and_absolute(tmp_path, monkeypatch):
    """Verify CLI data ingest command works with both relative and absolute paths."""
    # Write a test CSV file inside tmp_path
    candles = generate_synthetic_daily_candles(10)
    abs_csv = tmp_path / "cli_test.csv"
    write_csv_file(abs_csv, candles)

    # Use custom storage directory via monkeypatching Settings
    monkeypatch.setenv("HISTORICAL_DATA_PATH", str(tmp_path / "data" / "historical"))

    # Test with absolute path
    code = main(
        [
            "data",
            "ingest",
            "--source",
            str(abs_csv),
            "--format",
            "csv",
            "--symbol",
            "RELIANCE",
            "--exchange",
            "NSE",
            "--timeframe",
            "1d",
        ]
    )
    assert code == 0

    # Test with relative path resolved against PROJECT_ROOT
    rel_csv_path = PROJECT_ROOT / "cli_rel_test.csv"
    try:
        write_csv_file(rel_csv_path, candles)
        # Change cwd to tmp_path to ensure relative path is resolved against PROJECT_ROOT
        monkeypatch.chdir(tmp_path)

        code_rel = main(
            [
                "data",
                "ingest",
                "--source",
                "cli_rel_test.csv",
                "--format",
                "csv",
                "--symbol",
                "TCS",
                "--exchange",
                "NSE",
                "--timeframe",
                "1d",
            ]
        )
        assert code_rel == 0
    finally:
        if rel_csv_path.exists():
            rel_csv_path.unlink()


# -----------------------------------------------------------------------------
# 25, 26, 27, 28, 29. True Atomic Persistence & Staging Failure Tests
# -----------------------------------------------------------------------------


def test_simulated_storage_staging_failure_leaves_dataset_unchanged(tmp_path):
    """Verify that a storage staging failure leaves the existing dataset 100% untouched."""
    store_dir = tmp_path / "store"
    store = ParquetHistoricalDataStore(base_path=store_dir)
    service = HistoricalDataIngestionService(store=store)

    # Initial 5 candles committed cleanly
    initial_candles = generate_synthetic_daily_candles(5)
    csv_initial = tmp_path / "initial.csv"
    write_csv_file(csv_initial, initial_candles)
    s1 = service.ingest(csv_initial, "csv", "RELIANCE", "NSE", "1d")
    assert s1.status == IngestionRunStatus.SUCCESS

    # Now attempt second batch, but mock pyarrow.parquet.write_table to simulate disk/IO failure
    new_candles = generate_synthetic_daily_candles(
        5, start_dt=datetime(2026, 2, 1, tzinfo=timezone.utc)
    )
    csv_new = tmp_path / "new_batch.csv"
    write_csv_file(csv_new, new_candles)

    with mock.patch("pyarrow.parquet.write_table", side_effect=OSError("Simulated Disk Full")):
        s2 = service.ingest(csv_new, "csv", "RELIANCE", "NSE", "1d")
        assert s2.status == IngestionRunStatus.FAILED
        assert s2.records_written == 0

    # Verify existing dataset is completely untouched
    stored = store.read("RELIANCE", "NSE", Timeframe.D1)
    assert len(stored) == 5
    assert stored[-1].timestamp == initial_candles[-1].timestamp

    # Verify no orphan temporary files exist in the partition dir
    partition_dir = store_dir / "NSE" / "RELIANCE" / "1d"
    tmp_files = list(partition_dir.glob("*.tmp*"))
    assert len(tmp_files) == 0


def test_manifest_guarantees_data_metadata_consistency(tmp_path):
    """Verify manifest transaction pointer guarantees data and metadata version consistency."""
    store = ParquetHistoricalDataStore(base_path=tmp_path / "store")
    candles = generate_synthetic_daily_candles(15)

    meta = store.write(candles)
    assert meta.record_count == 15

    # Check manifest exists and reflects exact record count
    partition_dir = tmp_path / "store" / "NSE" / "RELIANCE" / "1d"
    manifest_file = partition_dir / "manifest.json"
    assert manifest_file.exists()

    meta_read = store.get_metadata("RELIANCE", "NSE", Timeframe.D1)
    assert meta_read is not None
    assert meta_read.record_count == 15
    assert meta_read.earliest_timestamp == candles[0].timestamp
    assert meta_read.latest_timestamp == candles[-1].timestamp
