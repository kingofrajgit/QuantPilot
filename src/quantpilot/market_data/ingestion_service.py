"""Historical market data ingestion service with atomic persistence and validation."""

import csv
import math
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pyarrow.parquet as pq

from quantpilot.config.settings import resolve_project_path
from quantpilot.market_data.historical_base import HistoricalDataStore, validate_historical_range
from quantpilot.market_data.ingestion_models import (
    DatasetCoverageReport,
    IngestionFormat,
    IngestionRunStatus,
    IngestionSummary,
)
from quantpilot.market_data.models import Candle, Timeframe
from quantpilot.market_data.parquet_store import ParquetHistoricalDataStore
from quantpilot.market_data.validation import validate_candles

TIMEFRAME_DELTAS: dict[Timeframe, timedelta] = {
    Timeframe.M1: timedelta(minutes=1),
    Timeframe.M5: timedelta(minutes=5),
    Timeframe.M15: timedelta(minutes=15),
    Timeframe.M30: timedelta(minutes=30),
    Timeframe.H1: timedelta(hours=1),
    Timeframe.H4: timedelta(hours=4),
    Timeframe.D1: timedelta(days=1),
    Timeframe.W1: timedelta(weeks=1),
}


class HistoricalDataIngestionService:
    """Orchestrates historical dataset ingestion, normalization, validation, and storage.

    Guarantees:
    - Atomic all-or-nothing persistence: if any parse error, validation failure,
      or data conflict is detected, ZERO candles are written.
    - Idempotent repeated ingestion for identical candles.
    - Strict rejection of conflicting records.
    - Timezone-aware UTC normalization.
    """

    def __init__(self, store: HistoricalDataStore | None = None) -> None:
        """Initialize ingestion service with target historical data store."""
        self.store = store if store is not None else ParquetHistoricalDataStore()

    def ingest(
        self,
        source_path: Path | str,
        source_format: str | IngestionFormat,
        symbol: str,
        exchange: str,
        timeframe: Timeframe | str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        source_timezone: str | None = None,
    ) -> IngestionSummary:
        """Ingest historical market data file atomically.

        Args:
            source_path: Path to CSV or Parquet file (relative resolved via PROJECT_ROOT)
            source_format: 'csv' or 'parquet'
            symbol: Ticker symbol (e.g. RELIANCE)
            exchange: Exchange identifier (e.g. NSE)
            timeframe: Candle resolution (e.g. 1d, 1m)
            start_time: Optional inclusive start filter (UTC or aware)
            end_time: Optional inclusive end filter (UTC or aware)
            source_timezone: Optional default timezone for naive timestamps (e.g. Asia/Kolkata)

        Returns:
            IngestionSummary containing detailed run statistics and atomic status.
        """
        run_id = uuid.uuid4().hex
        started_at = datetime.now(timezone.utc)
        clean_symbol = symbol.strip().upper()
        clean_exchange = exchange.strip().upper()
        errors: list[str] = []

        # 1. Parse and validate parameters
        tf = self._parse_timeframe(timeframe, errors)
        fmt = self._parse_format(source_format, errors)

        resolved_source = resolve_project_path(source_path)
        source_str = str(source_path)

        if not resolved_source.exists() or not resolved_source.is_file():
            errors.append(f"Source file not found or is not a file: {resolved_source}")

        source_tz = self._parse_source_timezone(source_timezone, errors)

        start_utc, end_utc = self._parse_date_range(start_time, end_time, errors)

        if errors or tf is None or fmt is None:
            return IngestionSummary(
                run_id=run_id,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                source=source_str,
                source_format=fmt or IngestionFormat.CSV,
                symbol=clean_symbol,
                exchange=clean_exchange,
                timeframe=tf or Timeframe.D1,
                records_read=0,
                records_valid=0,
                records_written=0,
                records_skipped=0,
                duplicates=0,
                conflicts=0,
                validation_failures=len(errors),
                earliest_timestamp=None,
                latest_timestamp=None,
                status=IngestionRunStatus.FAILED,
                errors=errors,
            )

        # 2. Parse source rows into candidate dictionaries
        records_read = 0
        raw_candles: list[Candle] = []

        if fmt == IngestionFormat.CSV:
            raw_candles, records_read = self._read_csv(
                resolved_source, clean_symbol, clean_exchange, tf, source_tz, errors
            )
        elif fmt == IngestionFormat.PARQUET:
            raw_candles, records_read = self._read_parquet(
                resolved_source, clean_symbol, clean_exchange, tf, source_tz, errors
            )

        # 3. If parsing had fatal errors, abort immediately
        if errors:
            return IngestionSummary(
                run_id=run_id,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                source=source_str,
                source_format=fmt,
                symbol=clean_symbol,
                exchange=clean_exchange,
                timeframe=tf,
                records_read=records_read,
                records_valid=0,
                records_written=0,
                records_skipped=0,
                duplicates=0,
                conflicts=0,
                validation_failures=len(errors),
                earliest_timestamp=None,
                latest_timestamp=None,
                status=IngestionRunStatus.FAILED,
                errors=errors,
            )

        # 4. Filter by date range
        filtered_candles: list[Candle] = []
        for c in raw_candles:
            if start_utc is not None and c.timestamp < start_utc:
                continue
            if end_utc is not None and c.timestamp > end_utc:
                continue
            filtered_candles.append(c)

        # 5. In-batch deduplication and conflict detection
        batch_map: dict[datetime, Candle] = {}
        in_batch_duplicates = 0
        conflicts = 0

        for c in filtered_candles:
            ts = c.timestamp
            if ts in batch_map:
                existing_in_batch = batch_map[ts]
                if self._candles_equal(c, existing_in_batch):
                    in_batch_duplicates += 1
                else:
                    conflicts += 1
                    errors.append(
                        f"In-batch conflicting candles at {ts.isoformat()}: "
                        f"new=({c.open}, {c.high}, {c.low}, {c.close}, {c.volume}) vs "
                        f"existing=({existing_in_batch.open}, {existing_in_batch.high}, "
                        f"{existing_in_batch.low}, {existing_in_batch.close}, "
                        f"{existing_in_batch.volume})"
                    )
            else:
                batch_map[ts] = c

        unique_batch_candles = sorted(batch_map.values(), key=lambda x: x.timestamp)

        # 6. Store-level deduplication and conflict detection
        existing_store_candles: list[Candle] = []
        if self.store.exists(symbol=clean_symbol, exchange=clean_exchange, timeframe=tf):
            existing_store_candles = self.store.read(
                symbol=clean_symbol, exchange=clean_exchange, timeframe=tf
            )

        store_map = {c.timestamp: c for c in existing_store_candles}
        new_candles_to_write: list[Candle] = []
        store_duplicates = 0

        for c in unique_batch_candles:
            ts = c.timestamp
            if ts in store_map:
                stored = store_map[ts]
                if self._candles_equal(c, stored):
                    store_duplicates += 1
                else:
                    conflicts += 1
                    errors.append(
                        f"Store conflicting candle at {ts.isoformat()}: "
                        f"incoming=({c.open}, {c.high}, {c.low}, {c.close}, {c.volume}) vs "
                        f"stored=({stored.open}, {stored.high}, {stored.low}, "
                        f"{stored.close}, {stored.volume})"
                    )
            else:
                new_candles_to_write.append(c)

        total_duplicates = in_batch_duplicates + store_duplicates
        records_skipped = in_batch_duplicates + store_duplicates

        # 7. Pre-commit Validation: validate all candidates
        validation_failures = len(errors)
        if unique_batch_candles:
            report = validate_candles(unique_batch_candles)
            if report.status.value == "INVALID":
                validation_failures += len(report.errors)
                errors.extend(report.errors)

        # 8. ATOMIC ALL-OR-NOTHING GATE:
        # If ANY conflict, validation failure, or error exists -> write ZERO candles
        if conflicts > 0 or validation_failures > 0 or errors:
            return IngestionSummary(
                run_id=run_id,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                source=source_str,
                source_format=fmt,
                symbol=clean_symbol,
                exchange=clean_exchange,
                timeframe=tf,
                records_read=records_read,
                records_valid=len(unique_batch_candles) if conflicts == 0 else 0,
                records_written=0,
                records_skipped=records_skipped,
                duplicates=total_duplicates,
                conflicts=conflicts,
                validation_failures=validation_failures,
                earliest_timestamp=(
                    unique_batch_candles[0].timestamp if unique_batch_candles else None
                ),
                latest_timestamp=(
                    unique_batch_candles[-1].timestamp if unique_batch_candles else None
                ),
                status=IngestionRunStatus.FAILED,
                errors=errors,
            )

        # 9. Clean batch: write to storage
        records_written = 0
        if new_candles_to_write:
            try:
                self.store.write(new_candles_to_write)
                records_written = len(new_candles_to_write)
            except Exception as ex:
                errors.append(f"Storage write failure: {ex}")
                return IngestionSummary(
                    run_id=run_id,
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                    source=source_str,
                    source_format=fmt,
                    symbol=clean_symbol,
                    exchange=clean_exchange,
                    timeframe=tf,
                    records_read=records_read,
                    records_valid=len(unique_batch_candles),
                    records_written=0,
                    records_skipped=records_skipped,
                    duplicates=total_duplicates,
                    conflicts=conflicts,
                    validation_failures=1,
                    earliest_timestamp=(
                        unique_batch_candles[0].timestamp if unique_batch_candles else None
                    ),
                    latest_timestamp=(
                        unique_batch_candles[-1].timestamp if unique_batch_candles else None
                    ),
                    status=IngestionRunStatus.FAILED,
                    errors=errors,
                )

        return IngestionSummary(
            run_id=run_id,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            source=source_str,
            source_format=fmt,
            symbol=clean_symbol,
            exchange=clean_exchange,
            timeframe=tf,
            records_read=records_read,
            records_valid=len(unique_batch_candles),
            records_written=records_written,
            records_skipped=records_skipped,
            duplicates=total_duplicates,
            conflicts=0,
            validation_failures=0,
            earliest_timestamp=unique_batch_candles[0].timestamp if unique_batch_candles else None,
            latest_timestamp=unique_batch_candles[-1].timestamp if unique_batch_candles else None,
            status=IngestionRunStatus.SUCCESS,
            errors=[],
        )

    def check_coverage(
        self, symbol: str, exchange: str, timeframe: Timeframe | str
    ) -> DatasetCoverageReport:
        """Analyze stored dataset for chronological coverage and potential gaps.

        Conservative gap detection: flags chronological gaps exceeding standard
        timeframe spacing without assuming an exchange calendar.
        """
        clean_symbol = symbol.strip().upper()
        clean_exchange = exchange.strip().upper()
        tf = timeframe if isinstance(timeframe, Timeframe) else Timeframe(str(timeframe).lower())

        stored_candles = self.store.read(clean_symbol, clean_exchange, tf)
        if not stored_candles:
            return DatasetCoverageReport(
                symbol=clean_symbol,
                exchange=clean_exchange,
                timeframe=tf,
                record_count=0,
                earliest_timestamp=None,
                latest_timestamp=None,
                has_potential_gaps=False,
                potential_gap_count=0,
                gap_details=[],
            )

        sorted_candles = sorted(stored_candles, key=lambda x: x.timestamp)
        expected_delta = TIMEFRAME_DELTAS.get(tf, timedelta(days=1))
        gap_threshold = expected_delta * 1.5

        gap_details: list[str] = []
        for i in range(1, len(sorted_candles)):
            prev_ts = sorted_candles[i - 1].timestamp
            curr_ts = sorted_candles[i].timestamp
            delta = curr_ts - prev_ts
            if delta > gap_threshold:
                gap_details.append(
                    f"Potential gap between {prev_ts.isoformat()} and {curr_ts.isoformat()} "
                    f"(interval: {delta}, expected: {expected_delta})"
                )

        return DatasetCoverageReport(
            symbol=clean_symbol,
            exchange=clean_exchange,
            timeframe=tf,
            record_count=len(sorted_candles),
            earliest_timestamp=sorted_candles[0].timestamp,
            latest_timestamp=sorted_candles[-1].timestamp,
            has_potential_gaps=bool(gap_details),
            potential_gap_count=len(gap_details),
            gap_details=gap_details,
        )

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    def _parse_timeframe(self, timeframe: Timeframe | str, errors: list[str]) -> Timeframe | None:
        if isinstance(timeframe, Timeframe):
            return timeframe
        try:
            return Timeframe(str(timeframe).strip().lower())
        except ValueError:
            errors.append(f"Unsupported timeframe: '{timeframe}'")
            return None

    def _parse_format(
        self, source_format: IngestionFormat | str, errors: list[str]
    ) -> IngestionFormat | None:
        if isinstance(source_format, IngestionFormat):
            return source_format
        try:
            return IngestionFormat(str(source_format).strip().lower())
        except ValueError:
            errors.append(f"Unsupported source format: '{source_format}'. Use 'csv' or 'parquet'")
            return None

    def _parse_source_timezone(self, tz_str: str | None, errors: list[str]) -> ZoneInfo | None:
        if tz_str is None or not tz_str.strip():
            return None
        try:
            return ZoneInfo(tz_str.strip())
        except ZoneInfoNotFoundError:
            errors.append(f"Invalid source timezone: '{tz_str}'")
            return None

    def _parse_date_range(
        self,
        start_time: datetime | None,
        end_time: datetime | None,
        errors: list[str],
    ) -> tuple[datetime | None, datetime | None]:
        if start_time is None and end_time is None:
            return None, None
        try:
            if start_time is not None and end_time is not None:
                validate_historical_range(start_time, end_time)
            start_utc = start_time.astimezone(timezone.utc) if start_time is not None else None
            end_utc = end_time.astimezone(timezone.utc) if end_time is not None else None
            return start_utc, end_utc
        except Exception as ex:
            errors.append(f"Invalid date range: {ex}")
            return None, None

    def _parse_timestamp(self, raw: str | datetime, source_tz: ZoneInfo | None) -> datetime:
        """Parse timestamp string or datetime, enforce awareness or source_tz, normalize to UTC."""
        if isinstance(raw, datetime):
            dt = raw
        else:
            s = str(raw).strip()
            # Support common ISO formats
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            dt = datetime.fromisoformat(s)

        if dt.tzinfo is None:
            if source_tz is None:
                raise ValueError(f"Naive timestamp '{raw}' rejected: no source_timezone provided.")
            dt = dt.replace(tzinfo=source_tz)

        return dt.astimezone(timezone.utc)

    def _parse_float(self, value: str | float | int, name: str) -> float:
        """Parse float, reject NaN and Infinities."""
        try:
            val = float(value)
        except (ValueError, TypeError) as ex:
            raise ValueError(f"Field '{name}' is not a valid number: {value}") from ex

        if math.isnan(val) or math.isinf(val):
            raise ValueError(f"Field '{name}' contains non-finite value: {val}")
        return val

    def _candles_equal(self, a: Candle, b: Candle) -> bool:
        """Compare two candles for exact numerical equality."""
        return (
            a.open == b.open
            and a.high == b.high
            and a.low == b.low
            and a.close == b.close
            and a.volume == b.volume
        )

    def _read_csv(
        self,
        file_path: Path,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
        source_tz: ZoneInfo | None,
        errors: list[str],
    ) -> tuple[list[Candle], int]:
        """Parse raw CSV file into canonical Candle instances."""
        candles: list[Candle] = []
        records_read = 0

        try:
            with file_path.open("r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames is None:
                    errors.append("CSV file is empty or missing header row")
                    return [], 0

                # Normalize column headers
                col_map: dict[str, str] = {
                    c.strip().lower(): c for c in reader.fieldnames if c and c.strip()
                }

                # Find canonical columns
                ts_col = self._find_column(col_map, ["timestamp", "datetime", "date", "time"])
                open_col = self._find_column(col_map, ["open"])
                high_col = self._find_column(col_map, ["high"])
                low_col = self._find_column(col_map, ["low"])
                close_col = self._find_column(col_map, ["close"])
                vol_col = self._find_column(col_map, ["volume", "vol"])

                missing = []
                if not ts_col:
                    missing.append("timestamp")
                if not open_col:
                    missing.append("open")
                if not high_col:
                    missing.append("high")
                if not low_col:
                    missing.append("low")
                if not close_col:
                    missing.append("close")
                if not vol_col:
                    missing.append("volume")

                if missing:
                    errors.append(f"Missing required CSV column(s): {', '.join(missing)}")
                    return [], 0

                for row_idx, row in enumerate(reader, start=1):
                    records_read += 1
                    try:
                        ts_raw = row[ts_col]
                        op_raw = row[open_col]
                        hi_raw = row[high_col]
                        lo_raw = row[low_col]
                        cl_raw = row[close_col]
                        vo_raw = row[vol_col]

                        ts_utc = self._parse_timestamp(ts_raw, source_tz)
                        op = self._parse_float(op_raw, "open")
                        hi = self._parse_float(hi_raw, "high")
                        lo = self._parse_float(lo_raw, "low")
                        cl = self._parse_float(cl_raw, "close")
                        vo = self._parse_float(vo_raw, "volume")

                        candle = Candle(
                            symbol=symbol,
                            exchange=exchange,
                            timeframe=timeframe,
                            timestamp=ts_utc,
                            open=op,
                            high=hi,
                            low=lo,
                            close=cl,
                            volume=vo,
                        )
                        candles.append(candle)
                    except Exception as ex:
                        errors.append(f"Row {row_idx} validation failure: {ex}")

        except Exception as ex:
            errors.append(f"Failed to read CSV {file_path}: {ex}")

        return candles, records_read

    def _read_parquet(
        self,
        file_path: Path,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
        source_tz: ZoneInfo | None,
        errors: list[str],
    ) -> tuple[list[Candle], int]:
        """Parse raw Parquet file into canonical Candle instances."""
        candles: list[Candle] = []
        records_read = 0

        try:
            table = pq.read_table(file_path)
            col_names = {c.lower(): c for c in table.column_names}

            ts_col = self._find_column(col_names, ["timestamp", "datetime", "date", "time"])
            open_col = self._find_column(col_names, ["open"])
            high_col = self._find_column(col_names, ["high"])
            low_col = self._find_column(col_names, ["low"])
            close_col = self._find_column(col_names, ["close"])
            vol_col = self._find_column(col_names, ["volume", "vol"])

            missing = []
            if not ts_col:
                missing.append("timestamp")
            if not open_col:
                missing.append("open")
            if not high_col:
                missing.append("high")
            if not low_col:
                missing.append("low")
            if not close_col:
                missing.append("close")
            if not vol_col:
                missing.append("volume")

            if missing:
                errors.append(f"Missing required Parquet column(s): {', '.join(missing)}")
                return [], 0

            ts_list = table[ts_col].to_pylist()
            op_list = table[open_col].to_pylist()
            hi_list = table[high_col].to_pylist()
            lo_list = table[low_col].to_pylist()
            cl_list = table[close_col].to_pylist()
            vo_list = table[vol_col].to_pylist()

            records_read = len(ts_list)

            for i in range(records_read):
                try:
                    ts_utc = self._parse_timestamp(ts_list[i], source_tz)
                    op = self._parse_float(op_list[i], "open")
                    hi = self._parse_float(hi_list[i], "high")
                    lo = self._parse_float(lo_list[i], "low")
                    cl = self._parse_float(cl_list[i], "close")
                    vo = self._parse_float(vo_list[i], "volume")

                    candle = Candle(
                        symbol=symbol,
                        exchange=exchange,
                        timeframe=timeframe,
                        timestamp=ts_utc,
                        open=op,
                        high=hi,
                        low=lo,
                        close=cl,
                        volume=vo,
                    )
                    candles.append(candle)
                except Exception as ex:
                    errors.append(f"Record {i} validation failure: {ex}")

        except Exception as ex:
            errors.append(f"Failed to read Parquet {file_path}: {ex}")

        return candles, records_read

    def _find_column(self, col_map: dict[str, str], aliases: list[str]) -> str | None:
        for alias in aliases:
            if alias in col_map:
                return col_map[alias]
        return None
