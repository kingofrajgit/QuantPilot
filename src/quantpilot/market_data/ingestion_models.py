"""Data models and metadata for historical data ingestion and dataset management."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from quantpilot.market_data.models import (
    Timeframe,
    _validate_and_normalize_timestamp,
)


class IngestionFormat(str, Enum):
    """Supported file formats for historical data ingestion."""

    CSV = "csv"
    PARQUET = "parquet"


class IngestionRunStatus(str, Enum):
    """Status of an ingestion operation.

    Phase 2C uses strict atomic all-or-nothing ingestion. Status is binary:
    SUCCESS or FAILED.
    """

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class IngestionSummary(BaseModel):
    """Structured report produced by an ingestion run."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    run_id: str = Field(..., min_length=1, description="Unique identifier for ingestion run")
    started_at: datetime = Field(..., description="UTC start time of ingestion run")
    completed_at: datetime = Field(..., description="UTC completion time of ingestion run")
    source: str = Field(..., min_length=1, description="Source file path (portable)")
    source_format: IngestionFormat = Field(..., description="Ingested file format")
    symbol: str = Field(..., min_length=1, description="Trading ticker symbol")
    exchange: str = Field(..., min_length=1, description="Exchange identifier (e.g. NSE)")
    timeframe: Timeframe = Field(..., description="Candle bar resolution")

    records_read: int = Field(default=0, ge=0, description="Total records parsed from source")
    records_valid: int = Field(default=0, ge=0, description="Records passing validation")
    records_written: int = Field(default=0, ge=0, description="New records committed to storage")
    records_skipped: int = Field(default=0, ge=0, description="Duplicate records skipped")
    duplicates: int = Field(default=0, ge=0, description="Total duplicate records detected")

    conflicts: int = Field(default=0, ge=0, description="Conflicting records detected")
    validation_failures: int = Field(default=0, ge=0, description="Records failing validation")

    earliest_timestamp: datetime | None = Field(
        default=None, description="Earliest candle timestamp in ingested batch"
    )
    latest_timestamp: datetime | None = Field(
        default=None, description="Latest candle timestamp in ingested batch"
    )

    status: IngestionRunStatus = Field(..., description="Ingestion run status: SUCCESS or FAILED")
    errors: list[str] = Field(
        default_factory=list, description="Actionable error or warning messages"
    )

    @field_validator("started_at", "completed_at", mode="before")
    @classmethod
    def validate_mandatory_tz(cls, v: datetime | str) -> datetime:
        return _validate_and_normalize_timestamp(v)

    @field_validator("earliest_timestamp", "latest_timestamp", mode="before")
    @classmethod
    def validate_optional_tz(cls, v: datetime | str | None) -> datetime | None:
        if v is None:
            return None
        return _validate_and_normalize_timestamp(v)


class DatasetCoverageReport(BaseModel):
    """Chronological dataset coverage analysis with conservative gap detection."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    symbol: str = Field(..., min_length=1, description="Trading ticker symbol")
    exchange: str = Field(..., min_length=1, description="Exchange identifier")
    timeframe: Timeframe = Field(..., description="Candle bar resolution")
    record_count: int = Field(default=0, ge=0, description="Total candles in storage")
    earliest_timestamp: datetime | None = Field(
        default=None, description="Earliest stored candle timestamp"
    )
    latest_timestamp: datetime | None = Field(
        default=None, description="Latest stored candle timestamp"
    )
    has_potential_gaps: bool = Field(
        default=False, description="Whether potential chronological gaps were detected"
    )
    potential_gap_count: int = Field(
        default=0, ge=0, description="Number of potential chronological gaps detected"
    )
    gap_details: list[str] = Field(
        default_factory=list, description="Descriptions of potential chronological gaps"
    )
    disclaimer: str = Field(
        default=(
            "Phase 2C does not yet provide exchange-calendar-aware gap classification. "
            "Gap detection is chronological/timeframe based and should be interpreted "
            "as a potential data-quality indicator."
        ),
        description="Standard conservative disclaimer for gap interpretation",
    )

    @field_validator("earliest_timestamp", "latest_timestamp", mode="before")
    @classmethod
    def validate_optional_tz(cls, v: datetime | str | None) -> datetime | None:
        if v is None:
            return None
        return _validate_and_normalize_timestamp(v)
