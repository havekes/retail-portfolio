"""FMP API stubs for testing and local development.

Offline, deterministic fixtures used by ``StubFmpGateway``. No network access:
prices are generated from static sample bars and search/lookup return a small
fixed set of known instruments.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from src.market.api_types import (
    HistoricalPrice,
    IntradayHistoricalPrice,
    SecuritySearchResult,
    SymbolLookupResult,
)
from src.market.exception import MarketDataNotFoundError, MarketDataProviderError
from src.market.gateway import MarketGateway

_KNOWN_SYMBOLS: dict[str, dict[str, str]] = {
    "AAPL": {
        "name": "Apple Inc.",
        "exchange": "NASDAQ",
        "exchange_short_name": "NASDAQ",
        "currency": "USD",
        "security_type": "Common Stock",
        "country": "US",
    },
    "MSFT": {
        "name": "Microsoft Corporation",
        "exchange": "NASDAQ",
        "exchange_short_name": "NASDAQ",
        "currency": "USD",
        "security_type": "Common Stock",
        "country": "US",
    },
    "RY": {
        "name": "Royal Bank of Canada",
        "exchange": "Toronto Stock Exchange",
        "exchange_short_name": "TSX",
        "currency": "CAD",
        "security_type": "Common Stock",
        "country": "CA",
    },
    "VOD": {
        "name": "Vodafone Group Plc",
        "exchange": "London Stock Exchange",
        "exchange_short_name": "LSE",
        "currency": "GBP",
        "security_type": "Common Stock",
        "country": "GB",
    },
}

_BASE_PRICES: dict[str, float] = {
    "AAPL": 175.0,
    "MSFT": 380.0,
    "RY": 120.0,
    "VOD": 8.5,
}


class StubFmpGateway(MarketGateway):
    """Deterministic FMP gateway stub for testing and local development.

    Prices and search are generated offline from static sample bars. Unknown
    symbols raise ``MarketDataNotFoundError`` and symbols listed in
    ``fail_on_symbols`` raise ``MarketDataProviderError`` — mirroring the
    failure paths of the real gateway without any outbound I/O.
    """

    _api_key: str
    _unknown_symbols: frozenset[str]
    _fail_on_symbols: frozenset[str]

    def __init__(
        self,
        api_key: str,
        *,
        unknown_symbols: set[str] | None = None,
        fail_on_symbols: set[str] | None = None,
    ) -> None:
        self._api_key = api_key
        self._unknown_symbols = frozenset(
            symbol.upper() for symbol in (unknown_symbols or ())
        )
        self._fail_on_symbols = frozenset(
            symbol.upper() for symbol in (fail_on_symbols or ())
        )

    def _resolve_symbol(self, symbol: str) -> str:
        """Normalize a symbol and enforce the stub's failure/not-found paths."""
        normalized = symbol.strip().upper()
        if normalized in self._fail_on_symbols:
            message = f"Market data provider failure for symbol '{normalized}'."
            raise MarketDataProviderError(message)
        if normalized in self._unknown_symbols or normalized not in _KNOWN_SYMBOLS:
            raise MarketDataNotFoundError(normalized)
        return normalized

    def _generate_prices(
        self,
        security_id: UUID,
        symbol: str,
        from_date: date,
        to_date: date,
    ) -> list[HistoricalPrice]:
        base_price = _BASE_PRICES.get(symbol, 100.0)
        current = base_price
        prices: list[HistoricalPrice] = []
        days = (to_date - from_date).days
        for offset in range(days + 1):
            current_date = from_date + timedelta(days=offset)
            change = (hash(f"{symbol}-{offset}") % 100 - 50) / 2500.0
            current *= 1 + change
            prices.append(
                HistoricalPrice(
                    security_id=security_id,
                    date=current_date,
                    open=Decimal(str(round(current * 0.995, 2))),
                    high=Decimal(str(round(current * 1.01, 2))),
                    low=Decimal(str(round(current * 0.99, 2))),
                    close=Decimal(str(round(current, 2))),
                    adjusted_close=Decimal(str(round(current, 2))),
                    volume=1_000_000 + (hash(f"{symbol}-{offset}") % 1_000_000),
                )
            )
        return prices

    def search(self, query: str) -> list[SecuritySearchResult]:
        """Search for securities by ticker or name."""
        clean_query = query.strip().upper()
        return [
            SecuritySearchResult(
                code=symbol,
                exchange=payload["exchange_short_name"],
                name=payload["name"],
                currency=payload["currency"],
                security_type=payload["security_type"],
                isin=None,
                country=payload["country"],
            )
            for symbol, payload in _KNOWN_SYMBOLS.items()
            if not clean_query
            or clean_query in symbol
            or clean_query in payload["name"].upper()
        ]

    def get_price_on_date(
        self,
        security_id: UUID,
        symbol: str,
        exchange: str,
        date: date,
    ) -> HistoricalPrice | None:
        """Get the price for a security on a specific date."""
        _ = exchange  # Price generation is symbol-driven in stub mode.
        normalized = self._resolve_symbol(symbol)
        prices = self._generate_prices(
            security_id, normalized, from_date=date, to_date=date
        )
        return prices[0] if prices else None

    def get_prices(
        self,
        security_id: UUID,
        symbol: str,
        exchange: str,
        from_date: date,
        to_date: date,
    ) -> list[HistoricalPrice]:
        """Get historical prices for a security within a date range."""
        _ = exchange  # Price generation is symbol-driven in stub mode.
        normalized = self._resolve_symbol(symbol)
        return self._generate_prices(
            security_id, normalized, from_date=from_date, to_date=to_date
        )

    def get_intraday_prices(  # noqa: PLR0913, PLR0917
        self,
        security_id: UUID,
        symbol: str,
        exchange: str,
        from_datetime: datetime,
        to_datetime: datetime,
        interval: str = "1h",
    ) -> list[IntradayHistoricalPrice]:
        """Get intraday prices for a security (deterministic hourly bars)."""
        _ = exchange  # Price generation is symbol-driven in stub mode.
        if interval != "1h":
            msg = f"Unsupported interval '{interval}'. Only '1h' interval is supported."
            raise ValueError(msg)

        normalized = self._resolve_symbol(symbol)
        if from_datetime.tzinfo is None:
            from_datetime = from_datetime.replace(tzinfo=UTC)
        if to_datetime.tzinfo is None:
            to_datetime = to_datetime.replace(tzinfo=UTC)

        prices: list[IntradayHistoricalPrice] = []
        current_dt = from_datetime.replace(minute=0, second=0, microsecond=0)
        step = 0
        while current_dt <= to_datetime:
            current = _BASE_PRICES.get(normalized, 100.0) + step / 100
            prices.append(
                IntradayHistoricalPrice(
                    security_id=security_id,
                    timestamp=current_dt,
                    open=Decimal(str(round(current * 0.998, 2))),
                    high=Decimal(str(round(current * 1.005, 2))),
                    low=Decimal(str(round(current * 0.995, 2))),
                    close=Decimal(str(round(current, 2))),
                    volume=10_000 + (hash(f"{normalized}-{step}") % 50_000),
                )
            )
            current_dt += timedelta(hours=1)
            step += 1

        return prices

    def lookup_symbol(self, query: str) -> list[SymbolLookupResult]:
        """Look up symbols/companies matching a free-text query."""
        clean_query = query.strip().upper()
        return [
            SymbolLookupResult(
                symbol=symbol,
                name=payload["name"],
                exchange=payload["exchange"],
                exchange_short_name=payload["exchange_short_name"],
                currency=payload["currency"],
                security_type=payload["security_type"],
                country=payload["country"],
            )
            for symbol, payload in _KNOWN_SYMBOLS.items()
            if not clean_query
            or clean_query in symbol
            or clean_query in payload["name"].upper()
        ]
