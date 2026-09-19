"""Unit tests for parameter validation and boundary conditions across all 21 indicators."""

import pytest

from quantpilot.quant.momentum import MACDIndicator, ROCIndicator, RSIIndicator
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


def test_trend_parameter_validation() -> None:
    # SMA
    with pytest.raises(ValueError, match="period"):
        SMAIndicator(period=0)
    with pytest.raises(ValueError, match="period"):
        SMAIndicator(period=-5)
    assert SMAIndicator(period=1).minimum_observations == 1

    # EMA
    with pytest.raises(ValueError, match="period"):
        EMAIndicator(period=0)
    assert EMAIndicator(period=1).minimum_observations == 1

    # PriceVsSMA
    with pytest.raises(ValueError, match="period"):
        PriceVsSMAIndicator(period=0)

    # SMASlope
    with pytest.raises(ValueError, match="period"):
        SMASlopeIndicator(period=0, lag=1)
    with pytest.raises(ValueError, match="lag"):
        SMASlopeIndicator(period=10, lag=0)

    # EMASlope
    with pytest.raises(ValueError, match="period"):
        EMASlopeIndicator(period=0, lag=1)
    with pytest.raises(ValueError, match="lag"):
        EMASlopeIndicator(period=10, lag=-1)


def test_momentum_parameter_validation() -> None:
    # ROC
    with pytest.raises(ValueError, match="period"):
        ROCIndicator(period=0)

    # RSI
    with pytest.raises(ValueError, match="period"):
        RSIIndicator(period=0)

    # MACD
    with pytest.raises(ValueError, match="fast_period"):
        MACDIndicator(fast_period=0, slow_period=26, signal_period=9)
    with pytest.raises(ValueError, match="slow_period"):
        MACDIndicator(fast_period=12, slow_period=12, signal_period=9)
    with pytest.raises(ValueError, match="slow_period"):
        MACDIndicator(fast_period=26, slow_period=12, signal_period=9)
    with pytest.raises(ValueError, match="signal_period"):
        MACDIndicator(fast_period=12, slow_period=26, signal_period=0)


def test_volume_parameter_validation() -> None:
    # VolumeSMA
    with pytest.raises(ValueError, match="period"):
        VolumeSMAIndicator(period=0)

    # RVOL
    with pytest.raises(ValueError, match="period"):
        RVOLIndicator(period=0)

    # VolumeChange
    with pytest.raises(ValueError, match="lag"):
        VolumeChangeIndicator(lag=0)

    # OBV (no configurable parameters)
    obv = OBVIndicator()
    assert obv.minimum_observations == 1


def test_volatility_parameter_validation() -> None:
    # TrueRange (no configurable parameters)
    tr = TrueRangeIndicator()
    assert tr.minimum_observations == 1

    # ATR
    with pytest.raises(ValueError, match="period"):
        ATRIndicator(period=0)

    # NATR
    with pytest.raises(ValueError, match="period"):
        NATRIndicator(period=0)

    # RollingStdDev (period >= 2)
    with pytest.raises(ValueError, match="period"):
        RollingStdDevIndicator(period=1)
    with pytest.raises(ValueError, match="period"):
        RollingStdDevIndicator(period=0)
    assert RollingStdDevIndicator(period=2).minimum_observations == 2

    # BollingerBands (period >= 2, std_multiplier >= 0)
    with pytest.raises(ValueError, match="period"):
        BollingerBandsIndicator(period=1, std_multiplier=2.0)
    with pytest.raises(ValueError, match="std_multiplier"):
        BollingerBandsIndicator(period=20, std_multiplier=-0.1)
    bb = BollingerBandsIndicator(period=2, std_multiplier=0.0)
    assert bb.minimum_observations == 2


def test_structure_parameter_validation() -> None:
    # RollingHigh
    with pytest.raises(ValueError, match="period"):
        RollingHighIndicator(period=0)

    # RollingLow
    with pytest.raises(ValueError, match="period"):
        RollingLowIndicator(period=0)

    # StructureBreakoutDistance
    with pytest.raises(ValueError, match="period"):
        StructureBreakoutIndicator(period=0)


def test_relative_strength_parameter_validation() -> None:
    # RelativeStrength
    with pytest.raises(ValueError, match="period"):
        RelativeStrengthIndicator(period=0)
