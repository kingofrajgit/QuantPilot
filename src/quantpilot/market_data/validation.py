"""Deterministic validation engine for canonical market data.

Enforces dataset-level invariants:
- Chronological ordering
- Duplicate detection
- Interval gap detection
- Staleness checking
- Quality reporting
"""

from datetime import datetime, timedelta, timezone

from quantpilot.market_data.models import (
    Candle,
    DataQualityReport,
    DataQualityStatus,
)


def validate_candle(candle: Candle) -> list[str]:
    """Validate single-candle invariants.

    Note: The Pydantic Candle model strictly enforces OHLC, positive price,
    non-negative volume, and timezone awareness upon construction. This function
    provides an explicit diagnostic hook returning any violations as strings.
    """
    errors: list[str] = []

    if (
        candle.timestamp.tzinfo is None
        or candle.timestamp.tzinfo.utcoffset(candle.timestamp) is None
    ):
        errors.append("Timestamp must be timezone-aware")

    if candle.open <= 0 or candle.high <= 0 or candle.low <= 0 or candle.close <= 0:
        errors.append("All OHLC prices must be strictly positive")

    if candle.volume < 0:
        errors.append("Volume cannot be negative")

    if candle.high < candle.open or candle.high < candle.close or candle.high < candle.low:
        errors.append("High price must be >= Open, Close, and Low")

    if candle.low > candle.open or candle.low > candle.close or candle.low > candle.high:
        errors.append("Low price must be <= Open, Close, and High")

    if not candle.symbol.strip():
        errors.append("Symbol cannot be empty")
    if not candle.exchange.strip():
        errors.append("Exchange cannot be empty")

    return errors


def detect_duplicates(candles: list[Candle]) -> list[tuple[int, int, Candle]]:
    """Detect duplicate candles in a dataset.

    Duplicate identity is defined strictly by:
    (symbol, exchange, timeframe, timestamp)

    Returns:
        List of tuples: (first_seen_index, duplicate_index, duplicate_candle)
    """
    seen: dict[tuple[str, str, str, datetime], int] = {}
    duplicates: list[tuple[int, int, Candle]] = []

    for idx, c in enumerate(candles):
        key = (c.symbol, c.exchange, c.timeframe.value, c.timestamp)
        if key in seen:
            first_idx = seen[key]
            duplicates.append((first_idx, idx, c))
        else:
            seen[key] = idx

    return duplicates


def detect_missing_candles(
    candles: list[Candle], expected_interval: timedelta
) -> list[tuple[datetime, datetime]]:
    """Detect timestamp gaps between consecutive candles in a sequence.

    Args:
        candles: Chronologically ordered list of candles.
        expected_interval: Expected duration between adjacent candle timestamps.

    Returns:
        List of gap tuples: (gap_start_timestamp, gap_end_timestamp)
    """
    if len(candles) < 2 or expected_interval <= timedelta(0):
        return []

    gaps: list[tuple[datetime, datetime]] = []
    for i in range(len(candles) - 1):
        curr_ts = candles[i].timestamp
        next_ts = candles[i + 1].timestamp
        delta = next_ts - curr_ts
        if delta > expected_interval:
            gaps.append((curr_ts, next_ts))

    return gaps


def check_staleness(
    latest_timestamp: datetime,
    current_time: datetime,
    allowed_staleness: timedelta,
) -> tuple[bool, timedelta]:
    """Check if market data timestamp exceeds allowed staleness.

    Args:
        latest_timestamp: Timestamp of the most recent market data record.
        current_time: Current evaluation time.
        allowed_staleness: Maximum acceptable age before data is considered stale.

    Returns:
        tuple (is_stale: bool, age: timedelta)

    Raises:
        ValueError: If either timestamp is naive or if the timestamp is in the future.
    """
    if (
        latest_timestamp.tzinfo is None
        or latest_timestamp.tzinfo.utcoffset(latest_timestamp) is None
    ):
        raise ValueError("latest_timestamp must be timezone-aware")
    if current_time.tzinfo is None or current_time.tzinfo.utcoffset(current_time) is None:
        raise ValueError("current_time must be timezone-aware")

    # Normalize both to UTC for reliable comparison
    ts_utc = latest_timestamp.astimezone(timezone.utc)
    curr_utc = current_time.astimezone(timezone.utc)

    age = curr_utc - ts_utc

    if age < timedelta(0):
        raise ValueError(
            f"Market data timestamp ({ts_utc.isoformat()}) is in the future "
            f"relative to evaluation time ({curr_utc.isoformat()}). Clock/data corruption detected."
        )

    is_stale = age > allowed_staleness
    return is_stale, age


def validate_candles(
    candles: list[Candle],
    expected_interval: timedelta | None = None,
    current_time: datetime | None = None,
    allowed_staleness: timedelta | None = None,
) -> DataQualityReport:
    """Perform dataset-level validation across an entire candle series.

    Verifies:
    1. Dataset sufficiency (non-empty)
    2. Individual candle validity
    3. Chronological ordering
    4. Duplicate detection
    5. Missing interval gaps (if expected_interval provided)
    6. Staleness evaluation (if current_time and allowed_staleness provided)

    Returns:
        Structured DataQualityReport with status, errors, warnings, and checks run.
    """
    now_utc = datetime.now(timezone.utc)
    checks: list[str] = [
        "data_sufficiency",
        "candle_integrity",
        "chronological_ordering",
        "duplicate_detection",
    ]
    errors: list[str] = []
    warnings: list[str] = []

    record_count = len(candles)
    if record_count == 0:
        return DataQualityReport(
            status=DataQualityStatus.INSUFFICIENT_DATA,
            warnings=["No candles provided to validate."],
            checks_run=checks,
            validated_at=now_utc,
            record_count=0,
        )

    # 1. Individual candle validation
    for i, c in enumerate(candles):
        c_errs = validate_candle(c)
        for err in c_errs:
            errors.append(f"Candle at index {i} invalid: {err}")

    # 2. Chronological ordering check
    ordering_valid = True
    for i in range(record_count - 1):
        if candles[i].timestamp > candles[i + 1].timestamp:
            errors.append(
                f"Non-chronological ordering at index {i} -> {i + 1}: "
                f"{candles[i].timestamp.isoformat()} > {candles[i + 1].timestamp.isoformat()}"
            )
            ordering_valid = False

    # 3. Duplicate detection
    dups = detect_duplicates(candles)
    for first_idx, dup_idx, dup_c in dups:
        errors.append(
            f"Duplicate candle detected at index {dup_idx} (matches index {first_idx}): "
            f"symbol={dup_c.symbol}, exchange={dup_c.exchange}, "
            f"timeframe={dup_c.timeframe.value}, timestamp={dup_c.timestamp.isoformat()}"
        )

    # 4. Gap detection (if requested and chronologically ordered)
    if expected_interval is not None:
        checks.append("gap_detection")
        if ordering_valid and not dups:
            gaps = detect_missing_candles(candles, expected_interval)
            for start_ts, end_ts in gaps:
                warnings.append(
                    f"Missing expected interval gap between {start_ts.isoformat()} "
                    f"and {end_ts.isoformat()} (delta: {end_ts - start_ts})"
                )

    # 5. Staleness check (if requested)
    is_stale = False
    if current_time is not None and allowed_staleness is not None:
        checks.append("staleness_check")
        latest_c = max(candles, key=lambda c: c.timestamp)
        try:
            is_stale, age = check_staleness(latest_c.timestamp, current_time, allowed_staleness)
            if is_stale:
                warnings.append(
                    f"Dataset is stale: age {age} exceeds allowed {allowed_staleness} "
                    f"(latest: {latest_c.timestamp.isoformat()})"
                )
        except ValueError as ex:
            errors.append(f"Staleness check error: {ex}")

    # Determine final status
    if errors:
        status = DataQualityStatus.INVALID
    elif is_stale:
        status = DataQualityStatus.STALE
    elif warnings:
        status = DataQualityStatus.WARNING
    else:
        status = DataQualityStatus.VALID

    return DataQualityReport(
        status=status,
        errors=errors,
        warnings=warnings,
        checks_run=checks,
        validated_at=now_utc,
        record_count=record_count,
    )
