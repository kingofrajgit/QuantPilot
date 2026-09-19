"""Unit tests for SimulatedBroker and ZerodhaBroker safety boundary."""

import pytest
from pydantic import SecretStr

from quantpilot.broker import (
    AccountBalance,
    OrderSide,
    OrderStatus,
    OrderType,
    SimulatedBroker,
    ZerodhaBroker,
    get_broker,
)
from quantpilot.config.settings import Settings
from quantpilot.exceptions import ConfigurationError, OrderError, SecurityError


def test_simulated_broker_initial_state():
    """Verify SimulatedBroker initializes with correct default balance and no positions."""
    broker = SimulatedBroker(initial_cash=500_000.0, currency="INR")
    balance = broker.get_account_balance()

    assert isinstance(balance, AccountBalance)
    assert balance.cash == 500_000.0
    assert balance.currency == "INR"
    assert broker.get_positions() == {}
    assert broker.is_live() is False


def test_simulated_broker_market_buy_fill():
    """Verify market BUY order deterministically deducts cash and records position."""
    broker = SimulatedBroker(initial_cash=100_000.0)
    broker.set_price("INFY", 1500.0)

    order = broker.place_order(
        symbol="INFY",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
    )

    assert order.status == OrderStatus.FILLED
    assert order.filled_quantity == 10
    assert order.average_fill_price == 1500.0

    balance = broker.get_account_balance()
    assert balance.cash == 100_000.0 - (10 * 1500.0)

    positions = broker.get_positions()
    assert "INFY" in positions
    assert positions["INFY"].quantity == 10
    assert positions["INFY"].average_price == 1500.0


def test_simulated_broker_market_buy_insufficient_funds():
    """Verify market BUY order is rejected when funds are insufficient."""
    broker = SimulatedBroker(initial_cash=1_000.0)
    broker.set_price("TCS", 3500.0)

    order = broker.place_order(
        symbol="TCS",
        side=OrderSide.BUY,
        quantity=1,
        order_type=OrderType.MARKET,
    )

    assert order.status == OrderStatus.REJECTED
    assert "Insufficient funds" in (order.reason or "")
    assert broker.get_account_balance().cash == 1_000.0
    assert broker.get_positions() == {}


def test_simulated_broker_market_sell_fill():
    """Verify market SELL order reduces position and credits cash."""
    broker = SimulatedBroker(initial_cash=100_000.0)
    broker.set_price("RELIANCE", 2500.0)

    # First buy 10 shares
    broker.place_order(symbol="RELIANCE", side=OrderSide.BUY, quantity=10)

    # Now sell 4 shares at higher price
    broker.set_price("RELIANCE", 2600.0)
    sell_order = broker.place_order(
        symbol="RELIANCE",
        side=OrderSide.SELL,
        quantity=4,
        order_type=OrderType.MARKET,
    )

    assert sell_order.status == OrderStatus.FILLED
    assert sell_order.filled_quantity == 4
    assert sell_order.average_fill_price == 2600.0

    positions = broker.get_positions()
    assert positions["RELIANCE"].quantity == 6

    expected_cash = 100_000.0 - (10 * 2500.0) + (4 * 2600.0)
    assert broker.get_account_balance().cash == expected_cash


def test_simulated_broker_market_sell_insufficient_position():
    """Verify market SELL order is rejected if position is not held or quantity is insufficient."""
    broker = SimulatedBroker(initial_cash=100_000.0)
    broker.set_price("SBIN", 700.0)

    sell_order = broker.place_order(
        symbol="SBIN",
        side=OrderSide.SELL,
        quantity=5,
        order_type=OrderType.MARKET,
    )

    assert sell_order.status == OrderStatus.REJECTED
    assert "Insufficient position" in (sell_order.reason or "")


def test_simulated_broker_invalid_quantity():
    """Verify invalid quantity raises OrderError."""
    broker = SimulatedBroker()
    with pytest.raises(OrderError, match="positive"):
        broker.place_order(symbol="INFY", side=OrderSide.BUY, quantity=0)


def test_zerodha_broker_disabled_by_default():
    """Verify ZerodhaBroker raises SecurityError if LIVE_TRADING_ENABLED is False."""
    settings = Settings(LIVE_TRADING_ENABLED=False)
    with pytest.raises(SecurityError, match="Live trading is disabled"):
        ZerodhaBroker(settings=settings)


def test_zerodha_broker_requires_credentials_when_live_flag_set():
    """Verify ZerodhaBroker raises ConfigurationError if credentials are missing."""
    settings = Settings(
        LIVE_TRADING_ENABLED=True,
        ZERODHA_API_KEY=None,
    )
    with pytest.raises(ConfigurationError, match="Missing required Zerodha credential"):
        ZerodhaBroker(settings=settings)


def test_zerodha_broker_live_execution_refused_in_bootstrap_phase():
    """Verify that even with LIVE_TRADING_ENABLED and credentials, live orders are refused."""
    settings = Settings(
        LIVE_TRADING_ENABLED=True,
        ZERODHA_API_KEY=SecretStr("mock_key"),
        ZERODHA_API_SECRET=SecretStr("mock_secret"),
        ZERODHA_ACCESS_TOKEN=SecretStr("mock_token"),
    )
    broker = ZerodhaBroker(settings=settings)
    assert broker.is_live() is True

    # Order placement must be blocked and raise NotImplementedError in this phase
    with pytest.raises(
        NotImplementedError, match="Live Zerodha order execution is strictly disabled"
    ):
        broker.place_order(symbol="INFY", side=OrderSide.BUY, quantity=1)

    with pytest.raises(
        NotImplementedError, match="Live Zerodha order cancellation is strictly disabled"
    ):
        broker.cancel_order("order-123")


def test_get_broker_defaults_to_simulated():
    """Verify get_broker() returns SimulatedBroker under default settings."""
    broker = get_broker()
    assert isinstance(broker, SimulatedBroker)
    assert broker.is_live() is False
