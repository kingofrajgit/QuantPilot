"""Metadata models for historical market data storage."""

from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from quantpilot.market_data.models import (
    DataQualityStatus,
    Timeframe,
    _validate_and_normalize_timestamp,
)


class HistoricalDatasetMetadata(BaseModel):
    """Metadata describing a stored historical market dataset."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    symbol: str = Field(..., min_length=1, description="Trading ticker symbol")
    exchange: str = Field(..., min_length=1, description="Exchange identifier (e.g., NSE)")
    timeframe: Timeframe = Field(..., description="Candle bar resolution")
    earliest_timestamp: datetime = Field(..., description="Timestamp of oldest candle in dataset")
    latest_timestamp: datetime = Field(..., description="Timestamp of newest candle in dataset")
    record_count: int = Field(..., ge=0, description="Total number of stored candles")
    ingestion_timestamp: Annotated[
        datetime,
        Field(default_factory=lambda: datetime.now(timezone.utc)),
    ]
    validation_status: DataQualityStatus = Field(
        default=DataQualityStatus.VALID,
        description="Data quality status from Phase 2A validation",
    )

    @field_validator("earliest_timestamp", "latest_timestamp", "ingestion_timestamp", mode="before")
    @classmethod
    def validate_tz(cls, v: datetime) -> datetime:
        return _validate_and_normalize_timestamp(v)
