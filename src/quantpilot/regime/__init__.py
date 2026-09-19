"""QuantPilot Phase 4 — Market Regime & Market Structure Engine.

Provides deterministic, stateless, indicator-driven market context classification across:
- TrendRegime (BULLISH, BEARISH, SIDEWAYS, INSUFFICIENT_DATA)
- MomentumRegime (POSITIVE, NEGATIVE, NEUTRAL, INSUFFICIENT_DATA)
- VolatilityRegime (LOW, NORMAL, HIGH, INSUFFICIENT_DATA)
- VolumeRegime (HIGH_VOLUME, NORMAL_VOLUME, LOW_VOLUME,
  ACCUMULATION, DISTRIBUTION, INSUFFICIENT_DATA)
- MarketStructure (BREAKOUT, BREAKDOWN, CONSOLIDATION, TRENDING, RANGING, INSUFFICIENT_DATA)
- CompositeRegime (Strict 8-step precedence synthesis)
"""

from quantpilot.regime.base import BaseClassifier
from quantpilot.regime.combiner import RegimeCombiner
from quantpilot.regime.engine import RegimeEngine
from quantpilot.regime.models import (
    CompositeRegime,
    DimensionEvidence,
    MarketRegimeContext,
    MarketStructure,
    MomentumRegime,
    RegimeContextSeries,
    RegimeProvenance,
    TrendRegime,
    VolatilityRegime,
    VolumeRegime,
)
from quantpilot.regime.momentum_regime import MomentumClassifier
from quantpilot.regime.structure_regime import StructureClassifier
from quantpilot.regime.trend_regime import TrendClassifier
from quantpilot.regime.volatility_regime import VolatilityClassifier
from quantpilot.regime.volume_regime import VolumeClassifier

__all__ = [
    "BaseClassifier",
    "CompositeRegime",
    "DimensionEvidence",
    "MarketRegimeContext",
    "MarketStructure",
    "MomentumClassifier",
    "MomentumRegime",
    "RegimeCombiner",
    "RegimeContextSeries",
    "RegimeEngine",
    "RegimeProvenance",
    "StructureClassifier",
    "TrendClassifier",
    "TrendRegime",
    "VolatilityClassifier",
    "VolatilityRegime",
    "VolumeClassifier",
    "VolumeRegime",
]
