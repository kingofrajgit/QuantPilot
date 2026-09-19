"""Broker abstraction layer for QuantPilot.

Provides clean, implementation-independent broker interfaces.
Application components must interact exclusively with this abstraction,
never binding directly to broker-specific SDKs.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class OrderSide(str, Enum):
    """Side of the order."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Type of order."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(str, Enum):
    """Lifecycle status of an order."""

    PENDING = "PENDING"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass
class Order:
    """Represents an order placed through a broker interface."""

    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: float | None = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0
    reason: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Position:
    """Represents an open or held position."""

    symbol: str
    quantity: float
    average_price: float
    current_price: float = 0.0

    @property
    def market_value(self) -> float:
        price = self.current_price if self.current_price > 0 else self.average_price
        return self.quantity * price

    @property
    def unrealized_pnl(self) -> float:
        if self.current_price <= 0:
            return 0.0
        return (self.current_price - self.average_price) * self.quantity


@dataclass
class AccountBalance:
    """Represents available funds and account margins."""

    currency: str = "INR"
    cash: float = 0.0
    available_margin: float = 0.0


class Broker(ABC):
    """Abstract interface defining required broker operations."""

    @abstractmethod
    def get_account_balance(self) -> AccountBalance:
        """Fetch current account balances and margins."""
        pass

    @abstractmethod
    def get_positions(self) -> dict[str, Position]:
        """Fetch current open positions keyed by symbol."""
        pass

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        price: float | None = None,
    ) -> Order:
        """Submit an order to the broker."""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> Order:
        """Cancel an open order by its identifier."""
        pass

    @abstractmethod
    def get_order(self, order_id: str) -> Order | None:
        """Fetch an order by its identifier."""
        pass

    @abstractmethod
    def is_live(self) -> bool:
        """Return True only if connected to a live, real-money execution environment."""
        pass
