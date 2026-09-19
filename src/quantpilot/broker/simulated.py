"""Simulated broker implementation for development, backtesting, and testing.

Provides a deterministic in-memory broker without network access, external dependencies,
or real credentials.
"""

import uuid
from datetime import datetime, timezone

from quantpilot.broker.base import (
    AccountBalance,
    Broker,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
)
from quantpilot.exceptions import OrderError


class SimulatedBroker(Broker):
    """Deterministic in-memory broker for local development and testing."""

    def __init__(
        self,
        initial_cash: float = 1_000_000.0,
        currency: str = "INR",
        default_price: float = 100.0,
    ) -> None:
        """Initialize the simulated broker with deterministic starting state.

        Args:
            initial_cash: Starting cash balance.
            currency: Account currency denominator.
            default_price: Default synthetic execution price when not explicitly provided.
        """
        self._currency = currency
        self._cash = initial_cash
        self._default_price = default_price
        self._positions: dict[str, Position] = {}
        self._orders: dict[str, Order] = {}
        self._price_map: dict[str, float] = {}

    def set_price(self, symbol: str, price: float) -> None:
        """Set a deterministic price for a symbol."""
        if price <= 0:
            raise ValueError("Price must be greater than zero")
        self._price_map[symbol] = price
        if symbol in self._positions:
            self._positions[symbol].current_price = price

    def get_price(self, symbol: str) -> float:
        """Get the current simulated price for a symbol."""
        return self._price_map.get(symbol, self._default_price)

    def get_account_balance(self) -> AccountBalance:
        """Fetch current balance."""
        return AccountBalance(
            currency=self._currency,
            cash=self._cash,
            available_margin=self._cash,
        )

    def get_positions(self) -> dict[str, Position]:
        """Fetch open positions."""
        return {k: v for k, v in self._positions.items() if v.quantity > 0}

    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        price: float | None = None,
    ) -> Order:
        """Submit and deterministically execute or record an order."""
        if quantity <= 0:
            raise OrderError(f"Order quantity must be positive, got {quantity}")

        order_id = f"sim-{uuid.uuid4().hex[:8]}"
        fill_price = price if price is not None and price > 0 else self.get_price(symbol)
        now = datetime.now(timezone.utc)

        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            status=OrderStatus.PENDING,
            created_at=now,
            updated_at=now,
        )

        # Deterministic simulation for Market orders
        if order_type == OrderType.MARKET:
            if side == OrderSide.BUY:
                required_funds = fill_price * quantity
                if self._cash < required_funds:
                    order.status = OrderStatus.REJECTED
                    order.reason = (
                        f"Insufficient funds: required {required_funds:.2f}, "
                        f"available {self._cash:.2f}"
                    )
                else:
                    self._cash -= required_funds
                    self._update_position_buy(symbol, quantity, fill_price)
                    order.status = OrderStatus.FILLED
                    order.filled_quantity = quantity
                    order.average_fill_price = fill_price
                    order.updated_at = datetime.now(timezone.utc)

            elif side == OrderSide.SELL:
                current_pos = self._positions.get(symbol)
                available_qty = current_pos.quantity if current_pos else 0.0
                if available_qty < quantity:
                    order.status = OrderStatus.REJECTED
                    order.reason = (
                        f"Insufficient position: required {quantity}, available {available_qty}"
                    )
                else:
                    proceeds = fill_price * quantity
                    self._cash += proceeds
                    self._update_position_sell(symbol, quantity, fill_price)
                    order.status = OrderStatus.FILLED
                    order.filled_quantity = quantity
                    order.average_fill_price = fill_price
                    order.updated_at = datetime.now(timezone.utc)

        # Record order
        self._orders[order_id] = order
        return order

    def cancel_order(self, order_id: str) -> Order:
        """Cancel a pending order."""
        if order_id not in self._orders:
            raise OrderError(f"Order not found: {order_id}")

        order = self._orders[order_id]
        if order.status != OrderStatus.PENDING:
            raise OrderError(f"Cannot cancel order in status {order.status}")

        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now(timezone.utc)
        return order

    def get_order(self, order_id: str) -> Order | None:
        """Retrieve order by ID."""
        return self._orders.get(order_id)

    def is_live(self) -> bool:
        """Simulated broker is never live."""
        return False

    def _update_position_buy(self, symbol: str, quantity: float, price: float) -> None:
        """Update internal position state after a buy fill."""
        if symbol not in self._positions:
            self._positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                average_price=price,
                current_price=price,
            )
        else:
            pos = self._positions[symbol]
            total_qty = pos.quantity + quantity
            total_cost = (pos.quantity * pos.average_price) + (quantity * price)
            pos.average_price = total_cost / total_qty
            pos.quantity = total_qty
            pos.current_price = price

    def _update_position_sell(self, symbol: str, quantity: float, price: float) -> None:
        """Update internal position state after a sell fill."""
        pos = self._positions[symbol]
        pos.quantity -= quantity
        pos.current_price = price
        if pos.quantity <= 0:
            del self._positions[symbol]
