"""Parquet-based historical market data storage engine using PyArrow."""

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
    """Local Parquet-based historical data store with partition and merge safety.

    Partition hierarchy:
        {base_path}/{exchange}/{symbol}/{timeframe}/data.parquet
    """

    def __init__(self, base_path: Path | str | None = None) -> None:
        """Initialize Parquet store with root storage directory."""
        if base_path is not None:
            self.base_path = Path(base_path)
        else:
            self.base_path = get_settings().HISTORICAL_DATA_PATH

    def _get_partition_dir(self, exchange: str, symbol: str, timeframe: Timeframe) -> Path:
        """Derive the partition directory for a given series."""
        return self.base_path / exchange.upper() / symbol.upper() / timeframe.value

    def _get_data_file(self, exchange: str, symbol: str, timeframe: Timeframe) -> Path:
        """Derive the Parquet data file path for a given series."""
        return self._get_partition_dir(exchange, symbol, timeframe) / "data.parquet"

    def _get_metadata_file(self, exchange: str, symbol: str, timeframe: Timeframe) -> Path:
        """Derive the companion metadata file path for a given series."""
        return self._get_partition_dir(exchange, symbol, timeframe) / "metadata.json"

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
        data_file = self._get_data_file(exchange, symbol, timeframe)
        metadata_file = self._get_metadata_file(exchange, symbol, timeframe)

        try:
            partition_dir.mkdir(parents=True, exist_ok=True)
        except OSError as ex:
            raise DataStorageError(f"Failed to create directory {partition_dir}: {ex}") from ex

        # 2. Merge with existing data if present
        existing_candles: list[Candle] = []
        if data_file.exists():
            existing_candles = self.read(symbol=symbol, exchange=exchange, timeframe=timeframe)

        merged_map: dict[datetime, Candle] = {}
        for ec in existing_candles:
            merged_map[ec.timestamp] = ec

        for c in candles:
            ts = c.timestamp
            if ts in merged_map:
                existing = merged_map[ts]
                # Compare OHLCV for identical idempotency
                is_identical = (
                    abs(c.open - existing.open) < 1e-9
                    and abs(c.high - existing.high) < 1e-9
                    and abs(c.low - existing.low) < 1e-9
                    and abs(c.close - existing.close) < 1e-9
                    and abs(c.volume - existing.volume) < 1e-9
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

        # 3. Build PyArrow Table and write Parquet
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

        try:
            pq.write_table(table, data_file, compression="snappy")
        except Exception as ex:
            raise DataStorageError(f"Failed to write Parquet data to {data_file}: {ex}") from ex

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
            metadata_file.write_text(metadata.model_dump_json(indent=2), encoding="utf-8")
        except OSError as ex:
            raise DataStorageError(f"Failed to write metadata to {metadata_file}: {ex}") from ex

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
        data_file = self._get_data_file(exchange, symbol, timeframe)
        if not data_file.exists():
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
        return self._get_data_file(exchange, symbol, timeframe).exists()

    def get_metadata(
        self, symbol: str, exchange: str, timeframe: Timeframe
    ) -> HistoricalDatasetMetadata | None:
        """Retrieve dataset metadata if stored."""
        meta_file = self._get_metadata_file(exchange, symbol, timeframe)
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
        for meta_path in self.base_path.glob("*/*/*/metadata.json"):
            try:
                content = meta_path.read_text(encoding="utf-8")
                datasets.append(HistoricalDatasetMetadata.model_validate_json(content))
            except Exception:
                continue
        return datasets

    def delete(self, symbol: str, exchange: str, timeframe: Timeframe) -> bool:
        """Delete stored partition files for a series."""
        partition_dir = self._get_partition_dir(exchange, symbol, timeframe)
        if not partition_dir.exists():
            return False

        data_file = self._get_data_file(exchange, symbol, timeframe)
        meta_file = self._get_metadata_file(exchange, symbol, timeframe)

        try:
            if data_file.exists():
                data_file.unlink()
            if meta_file.exists():
                meta_file.unlink()
            # Attempt to clean up empty directory
            try:
                partition_dir.rmdir()
            except OSError:
                pass
            return True
        except OSError as ex:
            raise DataStorageError(f"Failed to delete partition {partition_dir}: {ex}") from ex
