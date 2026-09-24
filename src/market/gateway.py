from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

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
from src.market.exception import MarketDataProviderError

_CAPABILITY_NOT_SUPPORTED = "capability not supported by this provider"


class MarketGateway(ABC):
    """Abstract base class for market data gateway implementations."""

    @abstractmethod
    def search(self, query: str) -> list[SecuritySearchResult]:
        """Search for securities by query string."""
        ...

    @abstractmethod
    def get_price_on_date(
        self,
        security_id: SecurityId,
        symbol: str,
        exchange: str,
        date: date,
    ) -> HistoricalPrice | None:
        """Get price for a security on a specific date."""
        ...

    @abstractmethod
    def get_prices(
        self,
        security_id: SecurityId,
        symbol: str,
        exchange: str,
        from_date: date,
        to_date: date,
    ) -> list[HistoricalPrice]:
        """Get historical prices for a security within a date range."""
        ...

    @abstractmethod
    def get_intraday_prices(  # noqa: PLR0913, PLR0917
        self,
        security_id: SecurityId,
        symbol: str,
        exchange: str,
        from_datetime: datetime,
        to_datetime: datetime,
        interval: str = "1h",
    ) -> list[IntradayHistoricalPrice]:
        """Get intraday prices for a security within a datetime range."""
        ...

    # ------------------------------------------------------------------ #
    # Optional capabilities.
    #
    # These are non-abstract on purpose: gateways that only serve prices and
    # search (e.g. the existing EODHD-backed gateway) stay concrete and
    # instantiable. The default body raises a provider-agnostic error that
    # later tickets (and caching/proxy wrappers) can rely on. Implementations
    # that support a capability override the method.
    # ------------------------------------------------------------------ #

    def lookup_symbol(self, query: str) -> list[SymbolLookupResult]:
        """Look up symbols/companies matching a free-text query."""
        _ = query
        raise MarketDataProviderError(_CAPABILITY_NOT_SUPPORTED)

    def get_company_profile(self, symbol: str) -> CompanyProfile:
        """Get the company profile for a symbol."""
        _ = symbol
        raise MarketDataProviderError(_CAPABILITY_NOT_SUPPORTED)

    def get_income_statement(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
    ) -> list[IncomeStatement]:
        """Get income statements for a symbol."""
        _ = symbol, period, limit
        raise MarketDataProviderError(_CAPABILITY_NOT_SUPPORTED)

    def get_balance_sheet(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
    ) -> list[BalanceSheet]:
        """Get balance sheets for a symbol."""
        _ = symbol, period, limit
        raise MarketDataProviderError(_CAPABILITY_NOT_SUPPORTED)

    def get_cash_flow_statement(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
    ) -> list[CashFlowStatement]:
        """Get cash-flow statements for a symbol."""
        _ = symbol, period, limit
        raise MarketDataProviderError(_CAPABILITY_NOT_SUPPORTED)

    def get_key_metrics(self, symbol: str) -> KeyMetrics:
        """Get the key metrics / valuation snapshot for a symbol."""
        _ = symbol
        raise MarketDataProviderError(_CAPABILITY_NOT_SUPPORTED)

    def get_financial_ratios(
        self,
        symbol: str,
        period: str = "annual",
    ) -> FinancialRatios:
        """Get financial ratios for a symbol."""
        _ = symbol, period
        raise MarketDataProviderError(_CAPABILITY_NOT_SUPPORTED)

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

        The optional keyword filters are provider-agnostic: ``expiration``
        restricts to a single expiry, ``contract_type`` to calls or puts and
        ``strike_min``/``strike_max`` to a strike range. Implementations may
        apply them upstream or locally; callers never need provider knowledge.
        """
        _ = symbol, expiration, contract_type, strike_min, strike_max
        raise MarketDataProviderError(_CAPABILITY_NOT_SUPPORTED)


class DataPlaneMarketGateway(MarketGateway):
    """svcs registration key for the provider-agnostic data-plane gateway.

    This class carries no behaviour of its own; it exists solely as a distinct
    registration key so the new FMP/Polygon data plane can coexist with the
    legacy ``MarketGateway`` binding.

    The legacy ``MarketGateway`` binding stays on EODHD (``eodhd_gateway_factory``)
    so existing price-fetch flows (``repository_eodhd``, ``MarketService``) are
    untouched. The data-plane key is what T08/T09 endpoints resolve; it is bound
    to the composed, cache-wrapped FMP/Polygon gateway
    (``composite_market_gateway_factory``). Callers receive a
    ``MarketGateway``-typed instance.
    """
