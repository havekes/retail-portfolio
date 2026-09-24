"""Provider-agnostic composite market data gateway.

``CompositeMarketGateway`` implements the T01 ``MarketGateway`` contract for the
new data plane by routing each capability to the provider that owns it:

* prices, search, symbol lookup and every fundamentals capability -> FMP;
* options chains -> Polygon.

:func:`composite_market_gateway_factory` is a closeable generator factory
that yields the bare composite, which is what the provider-agnostic
``DataPlaneMarketGateway`` svcs key resolves to; the generator's ``finally``
releases the provider HTTP clients on container teardown.
Data-plane caching lives one layer up, in
:class:`~src.market.endpoint_cache.EndpointResponseCache` (``market:ep``), so
each response is stored exactly once. The legacy ``MarketGateway`` binding
stays on EODHD, so existing price-fetch flows are untouched.
"""

from collections.abc import Generator
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Protocol, cast

from src.market.api_types import (
    BalanceSheet,
    CashFlowStatement,
    CompanyProfile,
    FinancialRatios,
    HistoricalPrice,
    IncomeStatement,
    IntradayHistoricalPrice,
    KeyMetrics,
    OptionsChain,
    SecurityId,
    SecuritySearchResult,
    SymbolLookupResult,
)
from src.market.fmp import fmp_gateway_factory
from src.market.gateway import MarketGateway
from src.market.polygon import polygon_gateway_factory


class _Closeable(Protocol):
    """Structural type for a gateway with lifecycle cleanup."""

    def close(self) -> None: ...


class CompositeMarketGateway(MarketGateway):
    """Routes each ``MarketGateway`` capability to its owning provider.

    Prices, search, symbol lookup and fundamentals are delegated to ``fmp``;
    options chains are delegated to ``polygon``. The composite adds no caching
    of its own: data-plane responses are cached once, above the gateway, by
    :class:`~src.market.endpoint_cache.EndpointResponseCache`.
    """

    def __init__(self, fmp: MarketGateway, polygon: MarketGateway) -> None:
        self._fmp = fmp
        self._polygon = polygon

    def close(self) -> None:
        """Release the provider clients owned by this composite.

        Closes the FMP HTTP client and the Polygon HTTP session so their
        pooled connections are freed when the owning svcs container is torn
        down. Provider lifecycle hooks are structural (not part of the
        ``MarketGateway`` contract), hence the casts.
        """
        cast("_Closeable", self._fmp).close()
        cast("_Closeable", self._polygon).close()

    def search(self, query: str) -> list[SecuritySearchResult]:
        """Search for securities by query string (FMP)."""
        return self._fmp.search(query)

    def get_price_on_date(
        self,
        symbol: str,
        exchange: str,
        date: date,
        security_id: SecurityId | None = None,
    ) -> HistoricalPrice | None:
        """Get price for a security on a specific date (FMP)."""
        return self._fmp.get_price_on_date(symbol, exchange, date, security_id)

    def get_prices(
        self,
        symbol: str,
        exchange: str,
        from_date: date,
        to_date: date,
        security_id: SecurityId | None = None,
    ) -> list[HistoricalPrice]:
        """Get historical prices for a security within a date range (FMP)."""
        return self._fmp.get_prices(symbol, exchange, from_date, to_date, security_id)

    def get_intraday_prices(  # noqa: PLR0913, PLR0917
        self,
        symbol: str,
        exchange: str,
        from_datetime: datetime,
        to_datetime: datetime,
        interval: str = "1h",
        security_id: SecurityId | None = None,
    ) -> list[IntradayHistoricalPrice]:
        """Get intraday prices for a security within a datetime range (FMP).

        FMP itself keeps this capability unsupported (T02), so the provider's
        provider-agnostic "capability not supported" error surfaces unchanged.
        """
        return self._fmp.get_intraday_prices(
            symbol,
            exchange,
            from_datetime,
            to_datetime,
            interval=interval,
            security_id=security_id,
        )

    def lookup_symbol(self, query: str) -> list[SymbolLookupResult]:
        """Look up symbols/companies matching a free-text query (FMP)."""
        return self._fmp.lookup_symbol(query)

    def get_company_profile(
        self,
        symbol: str,
        *,
        exchange: str | None = None,
    ) -> CompanyProfile:
        """Get the company profile for a symbol (FMP)."""
        return self._fmp.get_company_profile(symbol, exchange=exchange)

    def get_income_statement(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
        *,
        exchange: str | None = None,
    ) -> list[IncomeStatement]:
        """Get income statements for a symbol (FMP)."""
        return self._fmp.get_income_statement(symbol, period, limit, exchange=exchange)

    def get_balance_sheet(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
        *,
        exchange: str | None = None,
    ) -> list[BalanceSheet]:
        """Get balance sheets for a symbol (FMP)."""
        return self._fmp.get_balance_sheet(symbol, period, limit, exchange=exchange)

    def get_cash_flow_statement(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
        *,
        exchange: str | None = None,
    ) -> list[CashFlowStatement]:
        """Get cash-flow statements for a symbol (FMP)."""
        return self._fmp.get_cash_flow_statement(
            symbol, period, limit, exchange=exchange
        )

    def get_key_metrics(
        self,
        symbol: str,
        *,
        exchange: str | None = None,
    ) -> KeyMetrics:
        """Get the key metrics / valuation snapshot for a symbol (FMP)."""
        return self._fmp.get_key_metrics(symbol, exchange=exchange)

    def get_financial_ratios(
        self,
        symbol: str,
        period: str = "annual",
        *,
        exchange: str | None = None,
    ) -> FinancialRatios:
        """Get financial ratios for a symbol (FMP)."""
        return self._fmp.get_financial_ratios(symbol, period, exchange=exchange)

    def get_options_chain(
        self,
        symbol: str,
        *,
        expiration: date | None = None,
        contract_type: Literal["call", "put"] | None = None,
        strike_min: Decimal | None = None,
        strike_max: Decimal | None = None,
    ) -> OptionsChain:
        """Get the options chain for an underlying symbol (Polygon)."""
        return self._polygon.get_options_chain(
            symbol,
            expiration=expiration,
            contract_type=contract_type,
            strike_min=strike_min,
            strike_max=strike_max,
        )


def composite_market_gateway_factory() -> Generator[MarketGateway]:
    """Build the provider-agnostic data-plane gateway.

    Constructs the FMP and Polygon gateways directly (mirroring
    ``repository_eodhd.py::eodhd_price_repository_factory`` calling
    ``eodhd_gateway_factory()``) and yields the bare composite. Data-plane
    caching is applied once, above the gateway, by
    :class:`~src.market.endpoint_cache.EndpointResponseCache`. Both provider
    factories are stub-aware, so ``STUB_EXTERNAL_API=true`` yields a fully
    offline composite.

    Closeable generator factory, mirroring
    ``indicator_service_client_factory``'s cleanup contract: svcs tears the
    generator down when the owning container is closed, which closes the FMP
    HTTP client and the Polygon HTTP session so their pooled connections are
    released. Sync (not async) because the data plane is sync: the gateway is
    resolved synchronously in ``data_router`` (``services.get``), and svcs
    refuses to enter async factories through sync ``get``. The providers are
    only closed on this path — direct ``fmp_gateway_factory`` /
    ``polygon_gateway_factory`` call sites keep today's caller-owned
    behaviour.
    """
    gateway = CompositeMarketGateway(
        fmp=fmp_gateway_factory(),
        polygon=polygon_gateway_factory(),
    )
    try:
        yield gateway
    finally:
        gateway.close()
