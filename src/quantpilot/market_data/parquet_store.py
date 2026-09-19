"""Parquet-based historical market data storage engine using PyArrow."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from quantpilot.config.settings import get_settings
from quantpilot.exceptions import (
    DataConflictError,
    DataStorageError,
    DataValidationError,
)
from quantpilot.market_data.historical_base import (
    HistoricalDataStore,
    validate_historical_range,
)
from quantpilot.market_data.historical_models import HistoricalDatasetMetadata
from quantpilot.market_data.models import (
    Candle,
    DataQualityStatus,
    Timeframe,
)
from quantpilot.market_data.validation import validate_candles

# Explicit PyArrow schema for canonical Candle storage
CANDLE_ARROW_SCHEMA = pa.schema(
    [
        ("symbol", pa.string()),
        ("exchange", pa.string()),
        ("timeframe", pa.string()),
        ("timestamp", pa.timestamp("us", tz="UTC")),
        ("open", pa.float64()),
        ("high", pa.float64()),
        ("low", pa.float64()),
        ("close", pa.float64()),
        ("volume", pa.float64()),
    ]
)


class ParquetHistoricalDataStore(HistoricalDataStore):
    """Local Parquet-based historical data store with atomic manifest transactions.

    Partition hierarchy:
        {base_path}/{exchange}/{symbol}/{timeframe}/
            manifest.json (atomic transaction pointer)
            data_{version_id}.parquet (active version dataset)
            metadata.json (companion metadata for backward compatibility)
    """

    def __init__(self, base_path: Path | str | None = None) -> None:
        """Initialize Parquet store with root storage directory."""
        if base_path is not None:
            self.base_path = Path(base_path)
        else:
            self.base_path = get_settings().resolved_historical_data_path

    def _get_partition_dir(self, exchange: str, symbol: str, timeframe: Timeframe) -> Path:
        """Derive the partition directory for a given series."""
        return self.base_path / exchange.upper() / symbol.upper() / timeframe.value

    def _get_manifest_file(self, exchange: str, symbol: str, timeframe: Timeframe) -> Path:
        """Derive the atomic manifest pointer file path for a given series."""
        return self._get_partition_dir(exchange, symbol, timeframe) / "manifest.json"

    def _get_legacy_data_file(self, exchange: str, symbol: str, timeframe: Timeframe) -> Path:
        """Derive legacy fallback Parquet data file path."""
        return self._get_partition_dir(exchange, symbol, timeframe) / "data.parquet"

    def _get_legacy_metadata_file(self, exchange: str, symbol: str, timeframe: Timeframe) -> Path:
        """Derive legacy fallback metadata file path."""
        return self._get_partition_dir(exchange, symbol, timeframe) / "metadata.json"

    def _get_active_data_file(
        self, exchange: str, symbol: str, timeframe: Timeframe
    ) -> Path | None:
        """Return the active Parquet data file using manifest pointer or legacy fallback."""
        manifest_file = self._get_manifest_file(exchange, symbol, timeframe)
        if manifest_file.exists():
            try:
                manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
                target_name = manifest_data.get("data_file")
                if target_name:
                    target_file = self._get_partition_dir(exchange, symbol, timeframe) / target_name
                    if target_file.exists():
                        return target_file
            except Exception:
                pass
        # Fallback to legacy data.parquet if present
        legacy = self._get_legacy_data_file(exchange, symbol, timeframe)
        if legacy.exists():
            return legacy
        return None

    def _get_data_file(self, exchange: str, symbol: str, timeframe: Timeframe) -> Path:
        """Derive active data file path, or legacy path if not yet written."""
        active = self._get_active_data_file(exchange, symbol, timeframe)
        if active is not None:
            return active
        return self._get_legacy_data_file(exchange, symbol, timeframe)

    def _get_metadata_file(self, exchange: str, symbol: str, timeframe: Timeframe) -> Path:
        """Derive metadata file path."""
        return self._get_legacy_metadata_file(exchange, symbol, timeframe)

    def write(self, candles: list[Candle]) -> HistoricalDatasetMetadata:
        """Store a batch of validated historical candles.

        Enforces:
        - Non-empty batch check
        - Uniform series identity across the batch
        - Phase 2A data quality validation
        - Idempotent repeated write for identical records
        - Rejection of conflicting records sharing the same key
        """
        if not candles:
            raise ValueError("No candles provided to write")

        first = candles[0]
        symbol = first.symbol
        exchange = first.exchange
        timeframe = first.timeframe

        # Ensure batch belongs to a uniform series
        for i, c in enumerate(candles):
            if c.symbol != symbol or c.exchange != exchange or c.timeframe != timeframe:
                raise ValueError(
                    f"Batch contains mixed series at index {i}: "
                    f"expected ({symbol}, {exchange}, {timeframe.value}), "
                    f"got ({c.symbol}, {c.exchange}, {c.timeframe.value})"
                )

        # 1. Run Phase 2A validation
        report = validate_candles(candles)
        if report.status == DataQualityStatus.INVALID:
            raise DataValidationError(
                f"Historical candles failed validation: {'; '.join(report.errors)}"
            )

        partition_dir = self._get_partition_dir(exchange, symbol, timeframe)
        try:
            partition_dir.mkdir(parents=True, exist_ok=True)
        except OSError as ex:
            raise DataStorageError(f"Failed to create directory {partition_dir}: {ex}") from ex

        # 2. Merge with existing data if present
        existing_candles: list[Candle] = []
        if self.exists(symbol=symbol, exchange=exchange, timeframe=timeframe):
            existing_candles = self.read(symbol=symbol, exchange=exchange, timeframe=timeframe)

        merged_map: dict[datetime, Candle] = {}
        for ec in existing_candles:
            merged_map[ec.timestamp] = ec

        for c in candles:
            ts = c.timestamp
            if ts in merged_map:
                existing = merged_map[ts]
                # Compare OHLCV for exact identical idempotency
                is_identical = (
                    c.open == existing.open
                    and c.high == existing.high
                    and c.low == existing.low
                    and c.close == existing.close
                    and c.volume == existing.volume
                )

                if not is_identical:
                    key_str = f"({symbol}, {exchange}, {timeframe.value}, {ts.isoformat()})"
                    in_s = f"O:{c.open}, H:{c.high}, L:{c.low}, C:{c.close}, V:{c.volume}"
                    ex_s = (
                        f"O:{existing.open}, H:{existing.high}, L:{existing.low}, "
                        f"C:{existing.close}, V:{existing.volume}"
                    )
                    raise DataConflictError(
                        f"Conflicting record for key {key_str}: "
                        f"incoming=({in_s}) vs existing=({ex_s})"
                    )
            else:
                merged_map[ts] = c

        # Sort all candles chronologically
        sorted_candles = sorted(merged_map.values(), key=lambda x: x.timestamp)

        # 3. Build PyArrow Table
        col_symbol = [c.symbol for c in sorted_candles]
        col_exchange = [c.exchange for c in sorted_candles]
        col_timeframe = [c.timeframe.value for c in sorted_candles]
        col_timestamp = [c.timestamp for c in sorted_candles]
        col_open = [c.open for c in sorted_candles]
        col_high = [c.high for c in sorted_candles]
        col_low = [c.low for c in sorted_candles]
        col_close = [c.close for c in sorted_candles]
        col_volume = [c.volume for c in sorted_candles]

        table = pa.Table.from_arrays(
            [
                pa.array(col_symbol, type=pa.string()),
                pa.array(col_exchange, type=pa.string()),
                pa.array(col_timeframe, type=pa.string()),
                pa.array(col_timestamp, type=pa.timestamp("us", tz="UTC")),
                pa.array(col_open, type=pa.float64()),
                pa.array(col_high, type=pa.float64()),
                pa.array(col_low, type=pa.float64()),
                pa.array(col_close, type=pa.float64()),
                pa.array(col_volume, type=pa.float64()),
            ],
            schema=CANDLE_ARROW_SCHEMA,
        )

        # 4. True Atomic Staging and Commit
        version_id = uuid.uuid4().hex[:12]
        op_id = uuid.uuid4().hex[:8]
        staged_data_file = partition_dir / f"data_{version_id}.parquet.tmp.{op_id}"
        committed_data_file = partition_dir / f"data_{version_id}.parquet"
        staged_manifest_file = partition_dir / f"manifest.json.tmp.{op_id}"
        manifest_file = self._get_manifest_file(exchange, symbol, timeframe)
        legacy_meta_file = self._get_legacy_metadata_file(exchange, symbol, timeframe)

        metadata = HistoricalDatasetMetadata(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            earliest_timestamp=sorted_candles[0].timestamp,
            latest_timestamp=sorted_candles[-1].timestamp,
            record_count=len(sorted_candles),
            ingestion_timestamp=datetime.now(timezone.utc),
            validation_status=report.status,
        )

        try:
            # Stage new parquet file
            pq.write_table(table, staged_data_file, compression="snappy")
            staged_data_file.replace(committed_data_file)

            # Stage manifest binding data and metadata in one atomic payload
            manifest_payload = {
                "version": version_id,
                "data_file": committed_data_file.name,
                "metadata": metadata.model_dump(mode="json"),
            }
            staged_manifest_file.write_text(
                json.dumps(manifest_payload, indent=2), encoding="utf-8"
            )

            # ATOMIC COMMIT: Single filesystem replace operation
            staged_manifest_file.replace(manifest_file)

            # Maintain companion metadata.json for backward compatibility
            try:
                legacy_meta_file.write_text(metadata.model_dump_json(indent=2), encoding="utf-8")
            except OSError:
                pass

            # Cleanup older generation files after successful atomic commit
            for p in partition_dir.glob("data_*.parquet"):
                if p.name != committed_data_file.name:
                    try:
                        p.unlink()
                    except OSError:
                        pass
        except Exception as ex:
            # Staging or commit failed: clean up all temporary and staged files
            for tmp in [staged_data_file, committed_data_file, staged_manifest_file]:
                if tmp.exists():
                    try:
                        tmp.unlink()
                    except OSError:
                        pass
            # Existing manifest_file was untouched
            raise DataStorageError(f"Failed to atomically persist dataset: {ex}") from ex

        return metadata

    def read(
        self,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Candle]:
        """Read historical candles filtered by optional date range."""
        data_file = self._get_active_data_file(exchange, symbol, timeframe)
        if data_file is None or not data_file.exists():
            return []

        if start is not None and end is not None:
            validate_historical_range(start, end)

        start_utc = start.astimezone(timezone.utc) if start is not None else None
        end_utc = end.astimezone(timezone.utc) if end is not None else None

        try:
            table = pq.read_table(data_file)
        except Exception as ex:
            raise DataStorageError(f"Failed to read Parquet data from {data_file}: {ex}") from ex

        candles: list[Candle] = []
        timestamps = table["timestamp"].to_pylist()
        opens = table["open"].to_pylist()
        highs = table["high"].to_pylist()
        lows = table["low"].to_pylist()
        closes = table["close"].to_pylist()
        volumes = table["volume"].to_pylist()

        for ts, op, hi, lo, cl, vol in zip(
            timestamps, opens, highs, lows, closes, volumes, strict=True
        ):
            # PyArrow gives timezone-aware UTC datetime
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            else:
                ts = ts.astimezone(timezone.utc)

            if start_utc is not None and ts < start_utc:
                continue
            if end_utc is not None and ts > end_utc:
                continue

            candles.append(
                Candle(
                    symbol=symbol,
                    exchange=exchange,
                    timeframe=timeframe,
                    timestamp=ts,
                    open=float(op),
                    high=float(hi),
                    low=float(lo),
                    close=float(cl),
                    volume=float(vol),
                )
            )

        return candles

    def exists(self, symbol: str, exchange: str, timeframe: Timeframe) -> bool:
        """Check whether historical data file exists for series."""
        return self._get_active_data_file(exchange, symbol, timeframe) is not None

    def get_metadata(
        self, symbol: str, exchange: str, timeframe: Timeframe
    ) -> HistoricalDatasetMetadata | None:
        """Retrieve dataset metadata if stored."""
        manifest_file = self._get_manifest_file(exchange, symbol, timeframe)
        if manifest_file.exists():
            try:
                manifest_dict = json.loads(manifest_file.read_text(encoding="utf-8"))
                if "metadata" in manifest_dict:
                    return HistoricalDatasetMetadata.model_validate(manifest_dict["metadata"])
            except Exception:
                pass

        meta_file = self._get_legacy_metadata_file(exchange, symbol, timeframe)
        if not meta_file.exists():
            return None

        try:
            content = meta_file.read_text(encoding="utf-8")
            return HistoricalDatasetMetadata.model_validate_json(content)
        except Exception as ex:
            raise DataStorageError(f"Failed to read metadata from {meta_file}: {ex}") from ex

    def list_datasets(self) -> list[HistoricalDatasetMetadata]:
        """Discover and list all historical datasets in the storage directory."""
        if not self.base_path.exists():
            return []

        datasets: list[HistoricalDatasetMetadata] = []
        seen_keys: set[tuple[str, str, str]] = set()

        # Check manifest files first
        for manifest_path in self.base_path.glob("*/*/*/manifest.json"):
            try:
                manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
                meta = HistoricalDatasetMetadata.model_validate(manifest_data["metadata"])
                key = (meta.symbol, meta.exchange, meta.timeframe.value)
                datasets.append(meta)
                seen_keys.add(key)
            except Exception:
                continue

        # Check legacy metadata files
        for meta_path in self.base_path.glob("*/*/*/metadata.json"):
            try:
                content = meta_path.read_text(encoding="utf-8")
                meta = HistoricalDatasetMetadata.model_validate_json(content)
                key = (meta.symbol, meta.exchange, meta.timeframe.value)
                if key not in seen_keys:
                    datasets.append(meta)
                    seen_keys.add(key)
            except Exception:
                continue

        return datasets

    def delete(self, symbol: str, exchange: str, timeframe: Timeframe) -> bool:
        """Delete stored partition files for a series."""
        partition_dir = self._get_partition_dir(exchange, symbol, timeframe)
        if not partition_dir.exists():
            return False

        try:
            manifest_file = self._get_manifest_file(exchange, symbol, timeframe)
            meta_file = self._get_legacy_metadata_file(exchange, symbol, timeframe)
            legacy_data = self._get_legacy_data_file(exchange, symbol, timeframe)

            if manifest_file.exists():
                manifest_file.unlink()
            if meta_file.exists():
                meta_file.unlink()
            if legacy_data.exists():
                legacy_data.unlink()

            for p in partition_dir.glob("data_*.parquet"):
                try:
                    p.unlink()
                except OSError:
                    pass

            for tmp in partition_dir.glob("*.tmp*"):
                try:
                    tmp.unlink()
                except OSError:
                    pass

            # Attempt to clean up empty directory
            try:
                partition_dir.rmdir()
            except OSError:
                pass
            return True
        except OSError as ex:
            raise DataStorageError(f"Failed to delete partition {partition_dir}: {ex}") from ex
