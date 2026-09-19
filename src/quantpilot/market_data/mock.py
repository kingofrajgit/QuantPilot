"""Deterministic in-memory mock market data provider for tests and development.

Operates with zero network calls, requires zero credentials, and supports explicit
fixture registration as well as deterministic synthetic candle generation.
"""

from datetime import datetime, timedelta, timezone

from quantpilot.market_data.base import MarketDataProvider
from quantpilot.market_data.models import (
    Candle,
    Instrument,
    MarketSession,
    Quote,
    Timeframe,
)


class MockMarketDataProvider(MarketDataProvider):
    """Deterministic in-memory market data provider."""

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self._instruments: dict[tuple[str, str], Instrument] = {}
        self._quotes: dict[tuple[str, str], Quote] = {}
        self._candles: dict[tuple[str, str, str], list[Candle]] = {}
        self._sessions: dict[str, MarketSession] = {}

    def register_instrument(self, instrument: Instrument) -> None:
        """Register an explicit instrument fixture."""
        self._instruments[(instrument.symbol, instrument.exchange)] = instrument

    def register_quote(self, quote: Quote) -> None:
        """Register an explicit quote fixture."""
        self._quotes[(quote.symbol, quote.exchange)] = quote

    def register_candles(
        self,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
        candles: list[Candle],
    ) -> None:
        """Register an explicit list of candles."""
        key = (symbol, exchange, timeframe.value)
        self._candles[key] = list(candles)

    def set_market_session(self, exchange: str, session: MarketSession) -> None:
        """Set market session status for an exchange."""
        self._sessions[exchange] = session

    def get_instrument(self, symbol: str, exchange: str) -> Instrument | None:
        """Return registered instrument or a default deterministic instrument."""
        key = (symbol, exchange)
        if key in self._instruments:
            return self._instruments[key]

        return Instrument(
            symbol=symbol,
            exchange=exchange,
            instrument_token=hash(key) % 1000000,
            lot_size=1,
            tick_size=0.05,
            is_active=True,
        )

    def get_latest_quote(self, symbol: str, exchange: str) -> Quote:
        """Return registered quote or a synthesized deterministic quote."""
        key = (symbol, exchange)
        if key in self._quotes:
            return self._quotes[key]

        now = datetime.now(timezone.utc)
        base = 100.0 + (abs(hash(symbol)) % 500)
        return Quote(
            symbol=symbol,
            exchange=exchange,
            timestamp=now,
            last_price=base,
            bid=base - 0.05,
            ask=base + 0.05,
            bid_qty=100.0,
            ask_qty=100.0,
            volume=50000.0,
        )

    def get_historical_candles(
        self,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        """Return registered or synthetic historical candles filtered by [start, end]."""
        start_utc = start.astimezone(timezone.utc)
        end_utc = end.astimezone(timezone.utc)

        key = (symbol, exchange, timeframe.value)
        candles = self._candles.get(key)
        if candles is None:
            # Generate deterministic synthetic candles if none registered
            candles = self.generate_synthetic_candles(
                symbol=symbol,
                exchange=exchange,
                timeframe=timeframe,
                count=10,
                start_time=start_utc,
            )

        return [c for c in candles if start_utc <= c.timestamp <= end_utc]

    def get_market_session(self, exchange: str, timestamp: datetime | None = None) -> MarketSession:
        """Return configured market session or default to OPEN."""
        return self._sessions.get(exchange, MarketSession.OPEN)

    def generate_synthetic_candles(
        self,
        symbol: str,
        exchange: str,
        timeframe: Timeframe,
        count: int,
        start_time: datetime,
        base_price: float = 1000.0,
        interval: timedelta | None = None,
    ) -> list[Candle]:
        """Deterministically generate valid synthetic candles.

        Uses deterministic formula without unseeded random state.
        """
        if start_time.tzinfo is None:
            raise ValueError("start_time must be timezone-aware")

        ts = start_time.astimezone(timezone.utc)
        step = interval or timedelta(minutes=5)
        candles: list[Candle] = []

        price = base_price
        for i in range(count):
            # Deterministic wave pattern: sin-based fluctuation
            fluctuation = (i % 5 - 2) * 2.5
            open_p = round(max(price, 10.0), 2)
            close_p = round(max(price + fluctuation, 10.0), 2)
            high_p = round(max(open_p, close_p) + 1.5, 2)
            low_p = round(min(open_p, close_p) - 1.5, 2)
            vol = float(1000 + (i * 50))

            candles.append(
                Candle(
                    symbol=symbol,
                    exchange=exchange,
                    timestamp=ts,
                    timeframe=timeframe,
                    open=open_p,
                    high=high_p,
                    low=low_p,
                    close=close_p,
                    volume=vol,
                )
            )
            price = close_p
            ts += step

        return candles
