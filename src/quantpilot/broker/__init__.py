"""Broker abstraction and adapter implementations for QuantPilot."""

from quantpilot.broker.base import (
    AccountBalance,
    Broker,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
)
from quantpilot.broker.simulated import SimulatedBroker
from quantpilot.broker.zerodha import ZerodhaBroker
from quantpilot.config.settings import Settings, get_settings


def get_broker(settings: Settings | None = None) -> Broker:
    """Return the active broker interface.

    Defaults strictly to SimulatedBroker.
    """
    cfg = settings or get_settings()
    if cfg.LIVE_TRADING_ENABLED:
        return ZerodhaBroker(settings=cfg)
    return SimulatedBroker()


__all__ = [
    "AccountBalance",
    "Broker",
    "Order",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "Position",
    "SimulatedBroker",
    "ZerodhaBroker",
    "get_broker",
]
