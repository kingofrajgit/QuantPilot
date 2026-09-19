"""Safe Zerodha adapter boundary for QuantPilot.

CRITICAL SECURITY CONSTRAINT:
Live execution is strictly DISABLED in this bootstrap phase.
No live trading or automatic order execution is permitted.
Zerodha credentials are never required upon module import.
"""

from quantpilot.broker.base import (
    AccountBalance,
    Broker,
    Order,
    OrderSide,
    OrderType,
    Position,
)
from quantpilot.config.settings import Settings, get_settings
from quantpilot.exceptions import SecurityError


class ZerodhaBroker(Broker):
    """Adapter boundary for future Zerodha Kite integration.

    Acts as a strict safety barrier:
    1. Rejects initialization if LIVE_TRADING_ENABLED is not explicitly True.
    2. Validates credentials without hardcoded fallbacks.
    3. Even if LIVE_TRADING_ENABLED is True, refuses live order execution in this bootstrap phase.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize Zerodha adapter boundary.

        Does not make network calls on import or construction.
        """
        self.settings = settings or get_settings()

        if not self.settings.LIVE_TRADING_ENABLED:
            raise SecurityError(
                "Live trading is disabled. LIVE_TRADING_ENABLED must be explicitly True "
                "to initialize ZerodhaBroker. Default safe state is fail-closed."
            )

        # Validate that credentials exist (fails closed without fallback)
        self._credentials = self.settings.get_zerodha_credentials()

    def get_account_balance(self) -> AccountBalance:
        """Query account balance from Zerodha."""
        raise NotImplementedError(
            "Live Zerodha balance retrieval is not implemented in this bootstrap phase."
        )

    def get_positions(self) -> dict[str, Position]:
        """Query open positions from Zerodha."""
        raise NotImplementedError(
            "Live Zerodha position retrieval is not implemented in this bootstrap phase."
        )

    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        price: float | None = None,
    ) -> Order:
        """Safe boundary: live order placement is strictly disabled in this phase."""
        raise NotImplementedError(
            "Live Zerodha order execution is strictly disabled and NOT implemented "
            "in this bootstrap phase. A future approved phase must implement live execution."
        )

    def cancel_order(self, order_id: str) -> Order:
        """Safe boundary: live order cancellation is strictly disabled in this phase."""
        raise NotImplementedError(
            "Live Zerodha order cancellation is strictly disabled in this bootstrap phase."
        )

    def get_order(self, order_id: str) -> Order | None:
        """Query order status from Zerodha."""
        raise NotImplementedError(
            "Live Zerodha order querying is not implemented in this bootstrap phase."
        )

    def is_live(self) -> bool:
        """Indicate whether this adapter connects to a live execution environment."""
        return True
