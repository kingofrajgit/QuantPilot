"""Unit tests for IndicatorRegistry and reflection."""

import pytest

from quantpilot.quant.registry import IndicatorRegistry, default_registry
from quantpilot.quant.trend import SMAIndicator

EXPECTED_21_INDICATORS = {
    "sma",
    "ema",
    "price_vs_sma",
    "sma_slope",
    "ema_slope",
    "roc",
    "rsi",
    "macd",
    "volume_sma",
    "rvol",
    "volume_change",
    "obv",
    "true_range",
    "atr",
    "natr",
    "rolling_std",
    "bollinger_bands",
    "rolling_high",
    "rolling_low",
    "structure_breakout_distance",
    "relative_strength",
}


def test_registry_contains_exactly_21_canonical_indicators() -> None:
    """Verify default_registry contains exactly the approved 21 canonical indicators."""
    available = {entry["name"] for entry in default_registry.list_available()}
    assert len(available) == 21
    assert available == EXPECTED_21_INDICATORS
    assert len(default_registry) == 21


def test_registry_rejects_duplicates() -> None:
    """Verify re-registering an indicator raises ValueError fail-closed."""
    reg = IndicatorRegistry()
    reg.register(SMAIndicator)
    with pytest.raises(ValueError, match="already registered"):
        reg.register(SMAIndicator)


def test_registry_get_and_instantiate() -> None:
    """Verify getting an indicator with custom parameters works."""
    ind = default_registry.get("sma", period=50)
    assert ind.name == "sma"
    assert ind.parameters == {"period": 50}

    with pytest.raises(KeyError, match="not found in registry"):
        default_registry.get("non_existent_indicator")


def test_registry_reflection() -> None:
    """Verify list_available reflects required metadata fields."""
    catalog = default_registry.list_available()
    assert len(catalog) == 21
    for entry in catalog:
        assert "name" in entry
        assert "class_name" in entry
        assert "version" in entry
        assert "required_fields" in entry
        assert "minimum_observations" in entry
        assert "default_parameters" in entry
        assert entry["name"] in EXPECTED_21_INDICATORS
