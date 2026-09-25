"""Polygon API stub for testing and local development.

Deterministic, fully offline options-chain gateway used when
``STUB_EXTERNAL_API=true``. It mirrors the failure/not-found knobs of
``StubFmpGateway``/``StubEodhdGateway`` and shares the options-chain fixtures
with ``StubEodhdGateway`` (see ``src.stubs.market_fixtures``), so stub-mode
options reads are reproducible and provider-independent.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from src.market.api_types import (
    HistoricalPrice,
    IntradayHistoricalPrice,
    OptionsChain,
    OptionsChainEntry,
    OptionsContract,
    OptionsQuote,
    SecurityId,
    SecuritySearchResult,
)
from src.market.exception import MarketDataNotFoundError, MarketDataProviderError
from src.market.gateway import MarketGateway
from src.stubs.market_fixtures import (
    KNOWN_SYMBOLS,
    OPTIONS_CHAINS,
    STUB_AS_OF_DATE,
)

_CAPABILITY_NOT_SUPPORTED = "capability not supported by this provider"


class StubPolygonGateway(MarketGateway):
    """Deterministic Polygon gateway stub for testing and local development.

    Only the options-chain capability is served (matching ``PolygonGateway``);
    the other capabilities raise the same provider-agnostic "capability not
    supported" error. Unknown symbols raise ``MarketDataNotFoundError`` and
    symbols listed in ``fail_on_symbols`` raise ``MarketDataProviderError`` —
    mirroring the failure paths of the real gateway without any outbound I/O.
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

    def close(self) -> None:
        """No-op: the stub owns no HTTP session to release."""

    def _resolve_symbol(self, symbol: str) -> str:
        """Normalize a symbol and enforce the stub's failure/not-found paths."""
        normalized = symbol.strip().upper()
        if normalized in self._fail_on_symbols:
            msg = f"Market data provider failure for symbol '{normalized}'."
            raise MarketDataProviderError(msg)
        if normalized in self._unknown_symbols or normalized not in KNOWN_SYMBOLS:
            raise MarketDataNotFoundError(normalized)
        return normalized

    def get_options_chain(
        self,
        symbol: str,
        *,
        expiration: date | None = None,
        contract_type: Literal["call", "put"] | None = None,
        strike_min: Decimal | None = None,
        strike_max: Decimal | None = None,
    ) -> OptionsChain:
        """Get the options chain for an underlying symbol.

        Honours the provider-agnostic filters (expiry, option type and strike
        range). A known symbol without options still returns an empty chain
        rather than raising, matching ``StubEodhdGateway``.
        """
        normalized = self._resolve_symbol(symbol)
        entries: list[OptionsChainEntry] = []
        for payload in OPTIONS_CHAINS.get(normalized, []):
            contract = payload["contract"]
            if (
                expiration is not None
                and contract["expiration_date"] != expiration.isoformat()
            ):
                continue
            if contract_type is not None and contract["contract_type"] != contract_type:
                continue
            strike = Decimal(contract["strike_price"])
            if strike_min is not None and strike < strike_min:
                continue
            if strike_max is not None and strike > strike_max:
                continue
            entries.append(
                OptionsChainEntry(
                    contract=OptionsContract(**contract),
                    quote=OptionsQuote(**payload["quote"]),
                )
            )
        return OptionsChain(
            underlying_symbol=normalized,
            as_of=STUB_AS_OF_DATE,
            contracts=entries,
        )

    # ------------------------------------------------------------------ #
    # Unsupported capabilities.
    #
    # This stub only serves options chains, mirroring ``PolygonGateway``: the
    # abstract methods raise the same provider-agnostic capability error as the
    # ABC defaults, keeping the class concrete.
    # ------------------------------------------------------------------ #

    def search(self, query: str) -> list[SecuritySearchResult]:
        """Search is not supported by this gateway."""
        _ = query
        raise MarketDataProviderError(_CAPABILITY_NOT_SUPPORTED)

    def get_price_on_date(
        self,
        symbol: str,
        exchange: str,
        date: date,
        security_id: SecurityId | None = None,
    ) -> HistoricalPrice | None:
        """Single-date prices are not supported by this gateway."""
        _ = security_id, symbol, exchange, date
        raise MarketDataProviderError(_CAPABILITY_NOT_SUPPORTED)

    def get_prices(
        self,
        symbol: str,
        exchange: str,
        from_date: date,
        to_date: date,
        security_id: SecurityId | None = None,
    ) -> list[HistoricalPrice]:
        """Historical prices are not supported by this gateway."""
        _ = security_id, symbol, exchange, from_date, to_date
        raise MarketDataProviderError(_CAPABILITY_NOT_SUPPORTED)

    def get_intraday_prices(  # noqa: PLR0913, PLR0917
        self,
        symbol: str,
        exchange: str,
        from_datetime: datetime,
        to_datetime: datetime,
        interval: str = "1h",
        security_id: SecurityId | None = None,
    ) -> list[IntradayHistoricalPrice]:
        """Intraday prices are not supported by this gateway."""
        _ = security_id, symbol, exchange, from_datetime, to_datetime, interval
        raise MarketDataProviderError(_CAPABILITY_NOT_SUPPORTED)
