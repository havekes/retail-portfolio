import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from time import perf_counter_ns
from typing import Literal

from src.market.api_types import (
    BalanceSheet,
    CashFlowStatement,
    CompanyProfile,
    FinancialRatios,
    HistoricalPrice,
    IncomeStatement,
    InstitutionalOwnershipResponse,
    IntradayHistoricalPrice,
    KeyMetrics,
    OptionExpirations,
    OptionsChain,
    Quote,
    SecurityId,
    SecuritySearchResult,
    SymbolLookupResult,
)
from src.market.exception import MarketDataProviderError
from src.observability import emit_event

_CAPABILITY_NOT_SUPPORTED = "capability not supported by this provider"

#: Internal telemetry dimension for the provider behind the market gateway.
#: Upstream provider identity is allowed in telemetry only — never in a user- or
#: agent-facing payload.
MARKET_DATA_PROVIDER = "eodhd"

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


class MarketGateway(ABC):
    """Abstract base class for market data gateway implementations."""

    @abstractmethod
    def search(self, query: str) -> list[SecuritySearchResult]:
        """Search for securities by query string."""
        ...

    @abstractmethod
    def get_price_on_date(
        self,
        symbol: str,
        exchange: str,
        date: date,
        security_id: SecurityId | None = None,
    ) -> HistoricalPrice | None:
        """Get price for a security on a specific date.

        Prices are keyed by ``symbol``/``exchange``; ``security_id`` identifies
        the persisted security and is optional. Provider-agnostic callers (the
        data plane) omit it, and the returned price's ``security_id`` is then
        ``None``. Callers persisting the result must supply it.
        """
        ...

    @abstractmethod
    def get_prices(
        self,
        symbol: str,
        exchange: str,
        from_date: date,
        to_date: date,
        security_id: SecurityId | None = None,
    ) -> list[HistoricalPrice]:
        """Get historical prices for a security within a date range.

        ``security_id`` is optional and only labels the returned prices for
        persistence; see :meth:`get_price_on_date`.
        """
        ...

    @abstractmethod
    def get_intraday_prices(  # noqa: PLR0913, PLR0917
        self,
        symbol: str,
        exchange: str,
        from_datetime: datetime,
        to_datetime: datetime,
        interval: str = "1h",
        security_id: SecurityId | None = None,
    ) -> list[IntradayHistoricalPrice]:
        """Get intraday prices for a security within a datetime range.

        ``security_id`` is optional and only labels the returned prices for
        persistence; see :meth:`get_price_on_date`.
        """
        ...

<<<<<<< HEAD
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

    def get_company_profile(
        self,
        symbol: str,
        *,
        exchange: str | None = None,
    ) -> CompanyProfile:
        """Get the company profile for a symbol.

        ``exchange`` is optional and forwarded for non-US ticker mapping.
        """
        _ = symbol, exchange
        raise MarketDataProviderError(_CAPABILITY_NOT_SUPPORTED)

    def get_income_statement(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
        *,
        exchange: str | None = None,
    ) -> list[IncomeStatement]:
        """Get income statements for a symbol.

        ``exchange`` is optional and forwarded for non-US ticker mapping.
        """
        _ = symbol, period, limit, exchange
        raise MarketDataProviderError(_CAPABILITY_NOT_SUPPORTED)

    def get_balance_sheet(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
        *,
        exchange: str | None = None,
    ) -> list[BalanceSheet]:
        """Get balance sheets for a symbol.

        ``exchange`` is optional and forwarded for non-US ticker mapping.
        """
        _ = symbol, period, limit, exchange
        raise MarketDataProviderError(_CAPABILITY_NOT_SUPPORTED)

    def get_cash_flow_statement(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
        *,
        exchange: str | None = None,
    ) -> list[CashFlowStatement]:
        """Get cash-flow statements for a symbol.

        ``exchange`` is optional and forwarded for non-US ticker mapping.
        """
        _ = symbol, period, limit, exchange
        raise MarketDataProviderError(_CAPABILITY_NOT_SUPPORTED)

    def get_key_metrics(
        self,
        symbol: str,
        *,
        exchange: str | None = None,
    ) -> KeyMetrics:
        """Get the key metrics / valuation snapshot for a symbol.

        ``exchange`` is optional and forwarded for non-US ticker mapping.
        """
        _ = symbol, exchange
        raise MarketDataProviderError(_CAPABILITY_NOT_SUPPORTED)

    def get_financial_ratios(
        self,
        symbol: str,
        period: str = "annual",
        *,
        exchange: str | None = None,
    ) -> FinancialRatios:
        """Get financial ratios for a symbol.

        ``exchange`` is optional and forwarded for non-US ticker mapping.
        """
        _ = symbol, period, exchange
        raise MarketDataProviderError(_CAPABILITY_NOT_SUPPORTED)

    def get_institutional_ownership(
        self,
        symbol: str,
        *,
        exchange: str | None = None,
    ) -> InstitutionalOwnershipResponse:
        """Get institutional ownership metrics and quarterly history for a symbol."""
        _ = symbol, exchange
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

    def get_option_expirations(self, symbol: str) -> OptionExpirations:
        """Get available option expiration dates for an underlying symbol."""
        _ = symbol
        raise MarketDataProviderError(_CAPABILITY_NOT_SUPPORTED)

    def get_quote(
        self,
        symbol: str,
        *,
        exchange: str | None = None,
    ) -> Quote:
        """Get live quote snapshot for a symbol."""
        _ = symbol, exchange
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


def error_slug_from_exception(exc: BaseException) -> str:
    """Return a stable, low-cardinality failure class for an exception."""
    class_name = type(exc).__name__ or "exception"
    return _CAMEL_BOUNDARY.sub("_", class_name).lower() or "exception"


def freshness_lag_ms(value: date | datetime) -> int:
    """Return the age in milliseconds of a returned data point, never negative."""
    if isinstance(value, datetime):
        reference = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    else:
        reference = datetime.combine(value, time.min, tzinfo=UTC)
    return max(0, int((datetime.now(UTC) - reference).total_seconds() * 1000))


@dataclass
class MarketFetch:
    """
    Mutable accumulator yielded by ``record_fetch``.

    Call sites set ``row_count``/``freshness_lag_ms`` once the gateway result is
    known; ``cache_state`` defaults to ``miss`` because these paths always
    re-request from the provider.
    """

    cache_state: str | None = None
    freshness_lag_ms: int | None = None
    row_count: int | None = None


def emit_market_data_fetched(  # noqa: PLR0913
    *,
    symbol: str,
    dataset: str,
    provider: str,
    exchange: str | None = None,
    cache_state: str | None = None,
    freshness_lag_ms: int | None = None,
    duration_ms: float,
    outcome: str,
    row_count: int | None = None,
    error_slug: str | None = None,
) -> None:
    """
    Emit one ``market.data.fetched`` wide event.

    Flat primitive fields only: nested structures are neither needed nor wanted
    inside an event emitted underneath a request span.
    """
    emit_event(
        "market.data.fetched",
        symbol=symbol,
        dataset=dataset,
        provider=provider,
        exchange=exchange,
        cache_state=cache_state,
        freshness_lag_ms=freshness_lag_ms,
        duration_ms=duration_ms,
        outcome=outcome,
        row_count=row_count,
        error_slug=error_slug,
    )


@contextmanager
def record_fetch(
    *,
    symbol: str,
    dataset: str,
    provider: str = MARKET_DATA_PROVIDER,
    exchange: str | None = None,
    cache_state: str | None = "miss",
) -> Iterator[MarketFetch]:
    """
    Time one provider fetch and emit exactly one ``market.data.fetched`` event.

    Synchronous and thread-safe (plain ``perf_counter_ns``) so it can wrap calls
    dispatched through ``asyncio.to_thread`` from the caller's side. An exception
    from the wrapped call is reported with ``outcome="failure"`` and a stable
    ``error_slug``, then re-raised so existing handlers keep working.
    """
    record = MarketFetch(cache_state=cache_state)
    started = perf_counter_ns()
    try:
        yield record
    except Exception as error:
        emit_market_data_fetched(
            symbol=symbol,
            dataset=dataset,
            provider=provider,
            exchange=exchange,
            cache_state=record.cache_state,
            freshness_lag_ms=record.freshness_lag_ms,
            duration_ms=(perf_counter_ns() - started) / 1_000_000,
            outcome="failure",
            row_count=record.row_count,
            error_slug=error_slug_from_exception(error),
        )
        raise
    else:
        emit_market_data_fetched(
            symbol=symbol,
            dataset=dataset,
            provider=provider,
            exchange=exchange,
            cache_state=record.cache_state,
            freshness_lag_ms=record.freshness_lag_ms,
            duration_ms=(perf_counter_ns() - started) / 1_000_000,
            outcome="success",
            row_count=record.row_count,
        )

