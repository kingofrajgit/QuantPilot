"""Quantitative Analysis and Indicator Engine for QuantPilot."""

from quantpilot.quant.base import BaseIndicator
from quantpilot.quant.engine import QuantEngine
from quantpilot.quant.models import (
    IndicatorProvenance,
    IndicatorSeries,
    IndicatorStatus,
    IndicatorValue,
    QuantRunContext,
)
from quantpilot.quant.momentum import MACDIndicator, ROCIndicator, RSIIndicator
from quantpilot.quant.registry import IndicatorRegistry, default_registry
from quantpilot.quant.relative_strength import RelativeStrengthIndicator
from quantpilot.quant.structure import (
    RollingHighIndicator,
    RollingLowIndicator,
    StructureBreakoutIndicator,
)
from quantpilot.quant.trend import (
    EMAIndicator,
    EMASlopeIndicator,
    PriceVsSMAIndicator,
    SMAIndicator,
    SMASlopeIndicator,
)
from quantpilot.quant.volatility import (
    ATRIndicator,
    BollingerBandsIndicator,
    NATRIndicator,
    RollingStdDevIndicator,
    TrueRangeIndicator,
)
from quantpilot.quant.volume import (
    OBVIndicator,
    RVOLIndicator,
    VolumeChangeIndicator,
    VolumeSMAIndicator,
)

# Canonical list of 21 indicators
ALL_INDICATORS: list[type[BaseIndicator]] = [
    # Trend (5)
    SMAIndicator,
    EMAIndicator,
    PriceVsSMAIndicator,
    SMASlopeIndicator,
    EMASlopeIndicator,
    # Momentum (3)
    ROCIndicator,
    RSIIndicator,
    MACDIndicator,
    # Volume (4)
    VolumeSMAIndicator,
    RVOLIndicator,
    VolumeChangeIndicator,
    OBVIndicator,
    # Volatility (5)
    TrueRangeIndicator,
    ATRIndicator,
    NATRIndicator,
    RollingStdDevIndicator,
    BollingerBandsIndicator,
    # Structure (3)
    RollingHighIndicator,
    RollingLowIndicator,
    StructureBreakoutIndicator,
    # Relative Strength (1)
    RelativeStrengthIndicator,
]

# Register all 21 indicators into default_registry if not already registered
for indicator_cls in ALL_INDICATORS:
    try:
        default_registry.register(indicator_cls)
    except ValueError:
        pass  # Already registered

__all__ = [
    "ALL_INDICATORS",
    "ATRIndicator",
    "BaseIndicator",
    "BollingerBandsIndicator",
    "EMAIndicator",
    "EMASlopeIndicator",
    "IndicatorProvenance",
    "IndicatorRegistry",
    "IndicatorSeries",
    "IndicatorStatus",
    "IndicatorValue",
    "MACDIndicator",
    "NATRIndicator",
    "OBVIndicator",
    "PriceVsSMAIndicator",
    "QuantEngine",
    "QuantRunContext",
    "RVOLIndicator",
    "RSIIndicator",
    "ROCIndicator",
    "RelativeStrengthIndicator",
    "RollingHighIndicator",
    "RollingLowIndicator",
    "RollingStdDevIndicator",
    "SMAIndicator",
    "SMASlopeIndicator",
    "StructureBreakoutIndicator",
    "TrueRangeIndicator",
    "VolumeChangeIndicator",
    "VolumeSMAIndicator",
    "default_registry",
]
