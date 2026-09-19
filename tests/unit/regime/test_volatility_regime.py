"""Unit tests and boundary checks for VolatilityClassifier."""

from datetime import datetime, timezone

import pytest

from quantpilot.quant.models import IndicatorStatus
from quantpilot.regime.models import VolatilityRegime
from quantpilot.regime.volatility_regime import VolatilityClassifier
from tests.unit.regime.conftest import make_candle, make_dict_indicator_series


def test_volatility_classifications_and_boundaries() -> None:
    """Verify LOW, NORMAL, HIGH classifications and exact boundary thresholds."""
    ts = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    candle = make_candle(ts)
    clf = VolatilityClassifier(bbw_low_threshold=0.030, bbw_high_threshold=0.080)

    # 1. LOW: 0.0299 < 0.030
    ind_low = {
        "bollinger_bands": make_dict_indicator_series(
            "bollinger_bands", [{"bandwidth": 0.0299}], [ts]
        )
    }
    state, ev = clf.classify(0, [candle], ind_low)
    assert state == VolatilityRegime.LOW
    assert ev.contributing_metrics["bandwidth"] == 0.0299

    # 2. Lower boundary exact: 0.030 is NORMAL (0.030 <= bbw <= 0.080)
    ind_low_exact = {
        "bollinger_bands": make_dict_indicator_series(
            "bollinger_bands", [{"bandwidth": 0.0300}], [ts]
        )
    }
    state, _ = clf.classify(0, [candle], ind_low_exact)
    assert state == VolatilityRegime.NORMAL

    # 3. NORMAL midpoint: 0.050
    ind_normal = {
        "bollinger_bands": make_dict_indicator_series(
            "bollinger_bands", [{"bandwidth": 0.0500}], [ts]
        )
    }
    state, ev = clf.classify(0, [candle], ind_normal)
    assert state == VolatilityRegime.NORMAL

    # 4. Upper boundary exact: 0.080 is NORMAL (0.030 <= bbw <= 0.080)
    ind_high_exact = {
        "bollinger_bands": make_dict_indicator_series(
            "bollinger_bands", [{"bandwidth": 0.0800}], [ts]
        )
    }
    state, _ = clf.classify(0, [candle], ind_high_exact)
    assert state == VolatilityRegime.NORMAL

    # 5. HIGH: 0.0801 > 0.080
    ind_high = {
        "bollinger_bands": make_dict_indicator_series(
            "bollinger_bands", [{"bandwidth": 0.0801}], [ts]
        )
    }
    state, ev = clf.classify(0, [candle], ind_high)
    assert state == VolatilityRegime.HIGH
    assert ev.contributing_metrics["bandwidth"] == 0.0801


def test_volatility_natr_absence_verified() -> None:
    """Verify that NATR is not required or consumed by VolatilityClassifier."""
    clf = VolatilityClassifier()
    assert "natr" not in clf.required_indicators
    assert clf.required_indicators == ["bollinger_bands"]


def test_volatility_insufficient_data() -> None:
    """Verify INSUFFICIENT_DATA on non-valid status, missing series, or missing bandwidth key."""
    ts = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    candle = make_candle(ts)
    clf = VolatilityClassifier()

    # 1. Non-VALID status
    ind_insufficient = {
        "bollinger_bands": make_dict_indicator_series(
            "bollinger_bands",
            [{"bandwidth": 0.05}],
            [ts],
            status=IndicatorStatus.INSUFFICIENT_DATA,
        )
    }
    state, ev = clf.classify(0, [candle], ind_insufficient)
    assert state == VolatilityRegime.INSUFFICIENT_DATA
    assert ev.contributing_metrics["bollinger_bands_status"] == "INSUFFICIENT_DATA"

    # 2. Missing bandwidth key
    ind_missing_key = {
        "bollinger_bands": make_dict_indicator_series("bollinger_bands", [{"middle": 100.0}], [ts])
    }
    state, _ = clf.classify(0, [candle], ind_missing_key)
    assert state == VolatilityRegime.INSUFFICIENT_DATA

    # 3. Missing series in indicators mapping
    state, ev = clf.classify(0, [candle], {})
    assert state == VolatilityRegime.INSUFFICIENT_DATA
    assert "Missing required indicator" in ev.rationale

    # 4. Out of bounds index
    with pytest.raises(IndexError):
        clf.classify(
            2,
            [candle],
            {
                "bollinger_bands": make_dict_indicator_series(
                    "bollinger_bands", [{"bandwidth": 0.05}], [ts]
                )
            },
        )
