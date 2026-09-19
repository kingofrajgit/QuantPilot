"""Tests for constructor parameter validation across all regime classifiers."""

import pytest

from quantpilot.regime.momentum_regime import MomentumClassifier
from quantpilot.regime.structure_regime import StructureClassifier
from quantpilot.regime.trend_regime import TrendClassifier
from quantpilot.regime.volatility_regime import VolatilityClassifier
from quantpilot.regime.volume_regime import VolumeClassifier


def test_trend_classifier_parameters() -> None:
    """Verify parameter boundaries for TrendClassifier."""
    # Valid defaults
    clf = TrendClassifier()
    assert clf.parameters["slope_threshold"] == 0.0
    assert clf.parameters["distance_threshold"] == 0.005

    # Valid custom
    clf2 = TrendClassifier(slope_threshold=0.01, distance_threshold=0.01)
    assert clf2.parameters["slope_threshold"] == 0.01

    # Invalid slope_threshold < 0.0
    with pytest.raises(ValueError, match="slope_threshold must be >= 0.0"):
        TrendClassifier(slope_threshold=-0.001)

    # Invalid distance_threshold <= 0.0
    with pytest.raises(ValueError, match="distance_threshold must be > 0.0"):
        TrendClassifier(distance_threshold=0.0)
    with pytest.raises(ValueError, match="distance_threshold must be > 0.0"):
        TrendClassifier(distance_threshold=-0.01)


def test_momentum_classifier_parameters() -> None:
    """Verify parameter boundaries for MomentumClassifier."""
    clf = MomentumClassifier()
    assert clf.parameters["rsi_bullish_bound"] == 55.0
    assert clf.parameters["rsi_bearish_bound"] == 45.0

    # Invalid rsi_bullish_bound
    with pytest.raises(ValueError, match="rsi_bullish_bound must be in"):
        MomentumClassifier(rsi_bullish_bound=50.0)
    with pytest.raises(ValueError, match="rsi_bullish_bound must be in"):
        MomentumClassifier(rsi_bullish_bound=100.1)

    # Invalid rsi_bearish_bound
    with pytest.raises(ValueError, match="rsi_bearish_bound must be in"):
        MomentumClassifier(rsi_bearish_bound=50.0)
    with pytest.raises(ValueError, match="rsi_bearish_bound must be in"):
        MomentumClassifier(rsi_bearish_bound=-0.1)


def test_volatility_classifier_parameters() -> None:
    """Verify parameter boundaries for VolatilityClassifier."""
    clf = VolatilityClassifier()
    assert clf.parameters["bbw_low_threshold"] == 0.030
    assert clf.parameters["bbw_high_threshold"] == 0.080

    # Invalid bbw_low_threshold <= 0.0
    with pytest.raises(ValueError, match="bbw_low_threshold must be > 0.0"):
        VolatilityClassifier(bbw_low_threshold=0.0)

    # Invalid bbw_high_threshold <= bbw_low_threshold
    with pytest.raises(ValueError, match="bbw_high_threshold.*must be > bbw_low_threshold"):
        VolatilityClassifier(bbw_low_threshold=0.05, bbw_high_threshold=0.05)
    with pytest.raises(ValueError, match="bbw_high_threshold.*must be > bbw_low_threshold"):
        VolatilityClassifier(bbw_low_threshold=0.05, bbw_high_threshold=0.04)


def test_volume_classifier_parameters() -> None:
    """Verify parameter boundaries for VolumeClassifier."""
    clf = VolumeClassifier()
    assert clf.parameters["rvol_high_threshold"] == 1.20
    assert clf.parameters["rvol_low_threshold"] == 0.80

    # Invalid rvol_high_threshold <= 1.0
    with pytest.raises(ValueError, match="rvol_high_threshold must be > 1.0"):
        VolumeClassifier(rvol_high_threshold=1.0)
    with pytest.raises(ValueError, match="rvol_high_threshold must be > 1.0"):
        VolumeClassifier(rvol_high_threshold=0.9)

    # Invalid rvol_low_threshold
    with pytest.raises(ValueError, match="rvol_low_threshold must be in"):
        VolumeClassifier(rvol_low_threshold=0.0)
    with pytest.raises(ValueError, match="rvol_low_threshold must be in"):
        VolumeClassifier(rvol_low_threshold=1.0)
    with pytest.raises(ValueError, match="rvol_low_threshold must be in"):
        VolumeClassifier(rvol_low_threshold=1.2)


def test_structure_classifier_parameters() -> None:
    """Verify parameter boundaries for StructureClassifier."""
    clf = StructureClassifier()
    assert clf.parameters["trend_channel_proximity"] == 0.020
    assert clf.parameters["bbw_consolidation_threshold"] == 0.030

    # Invalid trend_channel_proximity <= 0.0
    with pytest.raises(ValueError, match="trend_channel_proximity must be > 0.0"):
        StructureClassifier(trend_channel_proximity=0.0)

    # Invalid bbw_consolidation_threshold <= 0.0
    with pytest.raises(ValueError, match="bbw_consolidation_threshold must be > 0.0"):
        StructureClassifier(bbw_consolidation_threshold=0.0)
