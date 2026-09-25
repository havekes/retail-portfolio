"""Service-to-service market data endpoints.

These routes expose the provider-agnostic data plane to trusted services (the
MCP gateway in T10/T11). They are deliberately separate from the user-JWT
``market_router``:

* authentication is the shared-secret ``require_service_token`` dependency;
* every route resolves the ``DataPlaneMarketGateway`` svcs key (the composed
  FMP/Polygon gateway) and serves through the T13
  :class:`EndpointResponseCache` — the single canonical data-plane cache;
* error mapping stays here: an unknown symbol becomes a structured 404 and a
  provider outage a generic 502/503 — a provider name never appears in a
  response body.

The route paths and query parameter names are a stable contract for the Go MCP
gateway (T10/T11); do not rename them:

* ``GET /api/v1/market/data/prices/{symbol}`` — ``from``, ``to``, ``exchange``
* ``GET /api/v1/market/data/symbols/search`` — ``q``
* ``GET /api/v1/market/data/options/{symbol}`` — ``expiry``, ``option_type``,
  ``strike_min``, ``strike_max``
* ``GET /api/v1/market/data/fundamentals/{symbol}`` — ``exchange``
* ``GET /api/v1/market/data/fundamentals/{symbol}/statements`` — ``statement``
  (``income``/``balance``/``cashflow``), ``period`` (``annual``/``quarter``),
  ``limit``, ``exchange``

``exchange`` is forwarded to the gateway on every route that accepts it so
non-US symbols map to the provider's ticker suffix; the fundamentals overview
returns the FMP-shaped profile plus key metrics and ratios, and the statements
route returns the full FMP-shaped statement list for the requested
``statement``/``period``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from svcs.fastapi import DepContainer

from src.auth.api import require_service_token
from src.market.api_types import (
    BalanceSheet,
    CashFlowStatement,
    CompanyFundamentals,
    HistoricalPrice,
    IncomeStatement,
    OptionsChain,
    SymbolLookupResult,
)
from src.market.endpoint_cache import EndpointResponseCache
from src.market.exception import (
    MarketDataConfigurationError,
    MarketDataNotFoundError,
    MarketDataProviderError,
)
from src.market.gateway import DataPlaneMarketGateway
from src.market.schema import PriceBar, PriceHistoryResponse

logger = logging.getLogger(__name__)

data_router = APIRouter(prefix="/market/data")

_PROVIDER_UNAVAILABLE_DETAIL = "Market data provider is unavailable."


def _map_market_error(symbol: str, exc: Exception) -> HTTPException:
    """Translate a provider-agnostic gateway failure into an HTTP error.

    Details never embed a provider name or a raw upstream message: a missing
    symbol is a 404, a provider outage a generic 502, and a configuration
    problem a 503.
    """
    if isinstance(exc, MarketDataNotFoundError):
        return HTTPException(
            status_code=404,
            detail=f"No market data found for symbol '{symbol}'.",
        )
    if isinstance(exc, MarketDataConfigurationError):
        return HTTPException(status_code=503, detail=_PROVIDER_UNAVAILABLE_DETAIL)
    return HTTPException(status_code=502, detail=_PROVIDER_UNAVAILABLE_DETAIL)


async def _fetch_prices(
    gateway: DataPlaneMarketGateway,
    symbol: str,
    exchange: str | None,
    from_date: date,
    to_date: date,
) -> list[HistoricalPrice]:
    """Bridge the sync gateway read onto the event loop.

    ``MarketGateway.get_prices`` is synchronous (the composed gateway performs
    blocking provider HTTP), so it must not run on the loop.
    """
    return await asyncio.to_thread(
        gateway.get_prices,
        symbol,
        exchange or "",
        from_date,
        to_date,
    )


@data_router.get("/prices/{symbol}")
async def market_data_prices(
    _svc: Annotated[None, Depends(require_service_token)],
    symbol: str,
    from_: Annotated[date, Query(alias="from")],
    to: Annotated[date, Query()],
    services: DepContainer,
    exchange: Annotated[str | None, Query()] = None,
) -> PriceHistoryResponse:
    """Daily price history for a symbol, served through the endpoint cache."""
    if from_ > to:
        raise HTTPException(422, "from must be less than or equal to to")

    normalized_symbol = symbol.upper()
    gateway = services.get(DataPlaneMarketGateway)
    cache = await services.aget(EndpointResponseCache)

    # Date-only bounds: ``get_prices`` is a daily read, and passing plain
    # ``date`` objects keeps the cache key free of the naive/aware midnight
    # ambiguity (``_canonicalize_param`` never sees a ``datetime`` here).
    params = {
        "symbol": normalized_symbol,
        "exchange": exchange,
        "from": from_,
        "to": to,
    }

    async def fetch() -> PriceHistoryResponse:
        try:
            prices = await _fetch_prices(
                gateway, normalized_symbol, exchange, from_, to
            )
        except (
            MarketDataProviderError,
            MarketDataConfigurationError,
        ) as exc:
            raise _map_market_error(normalized_symbol, exc) from exc

        return PriceHistoryResponse(
            symbol=normalized_symbol,
            exchange=exchange,
            from_date=from_,
            to_date=to,
            items=[
                PriceBar(
                    date=price.date,
                    open=price.open,
                    high=price.high,
                    low=price.low,
                    close=price.close,
                    volume=price.volume,
                    adjusted_close=price.adjusted_close,
                )
                for price in prices
            ],
        )

    try:
        response = await cache.cached_response(
            data_class="prices",
            endpoint="history",
            params=params,
            fetch=fetch,
            model=PriceHistoryResponse,
        )
    except MarketDataNotFoundError as exc:
        # A missing symbol is negative-cached by the wrapper; translate the
        # re-raised domain error here so the 404 is served from cache on repeat.
        raise _map_market_error(normalized_symbol, exc) from exc

    # Raised after the cache wrapper so an empty window is cached exactly like a
    # populated one (a stable 404 for the TTL) instead of being re-fetched.
    if not response.items:
        raise HTTPException(
            status_code=404,
            detail=f"No market data found for symbol '{normalized_symbol}'.",
        )

    return response


@data_router.get("/symbols/search")
async def market_data_symbol_search(
    _svc: Annotated[None, Depends(require_service_token)],
    q: Annotated[str, Query(min_length=1, max_length=100)],
    services: DepContainer,
) -> list[SymbolLookupResult]:
    """Symbol/company lookup by free-text query, served through the cache."""
    gateway = services.get(DataPlaneMarketGateway)
    cache = await services.aget(EndpointResponseCache)

    params = {"query": q}

    async def fetch() -> list[SymbolLookupResult]:
        try:
            return await asyncio.to_thread(gateway.lookup_symbol, q)
        except (
            MarketDataProviderError,
            MarketDataConfigurationError,
        ) as exc:
            raise _map_market_error(q, exc) from exc

    try:
        results = await cache.cached_response(
            data_class="search",
            endpoint="symbol_lookup",
            params=params,
            fetch=fetch,
            model=SymbolLookupResult,
        )
    except MarketDataNotFoundError as exc:
        # An unknown query is negative-cached by the wrapper; translate the
        # re-raised domain error here so the 404 is served from cache on repeat.
        raise _map_market_error(q, exc) from exc

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No market data found for query '{q}'.",
        )

    return results


@data_router.get("/options/{symbol}")
async def market_data_options(  # noqa: PLR0913, PLR0917
    _svc: Annotated[None, Depends(require_service_token)],
    symbol: str,
    services: DepContainer,
    expiry: Annotated[date | None, Query()] = None,
    option_type: Annotated[Literal["call", "put"] | None, Query()] = None,
    strike_min: Annotated[Decimal | None, Query()] = None,
    strike_max: Annotated[Decimal | None, Query()] = None,
) -> OptionsChain:
    """Options chain for an underlying, mirroring the Polygon contract shape."""
    if strike_min is not None and strike_max is not None and strike_min > strike_max:
        raise HTTPException(422, "strike_min must be less than or equal to strike_max")

    normalized_symbol = symbol.upper()
    gateway = services.get(DataPlaneMarketGateway)
    cache = await services.aget(EndpointResponseCache)

    params = {
        "symbol": normalized_symbol,
        "expiry": expiry,
        "option_type": option_type,
        "strike_min": strike_min,
        "strike_max": strike_max,
    }

    async def fetch() -> OptionsChain:
        try:
            return await asyncio.to_thread(
                gateway.get_options_chain,
                normalized_symbol,
                expiration=expiry,
                contract_type=option_type,
                strike_min=strike_min,
                strike_max=strike_max,
            )
        except (
            MarketDataProviderError,
            MarketDataConfigurationError,
        ) as exc:
            raise _map_market_error(normalized_symbol, exc) from exc

    try:
        return await cache.cached_response(
            data_class="options",
            endpoint="chain",
            params=params,
            fetch=fetch,
            model=OptionsChain,
        )
    except MarketDataNotFoundError as exc:
        # Unknown underlying / no matching contracts: negative-cached by the
        # wrapper, translated to a 404 here.
        raise _map_market_error(normalized_symbol, exc) from exc


@data_router.get("/fundamentals/{symbol}")
async def market_data_fundamentals(
    _svc: Annotated[None, Depends(require_service_token)],
    symbol: str,
    services: DepContainer,
    exchange: Annotated[str | None, Query()] = None,
) -> CompanyFundamentals:
    """Company details plus key metrics and ratios, served through the cache.

    The response keeps the FMP-shaped ``profile``, ``key_metrics`` and
    ``ratios`` objects field-for-field; ``exchange`` is forwarded so non-US
    symbols map to the provider's ticker suffix.
    """
    normalized_symbol = symbol.upper()
    gateway = services.get(DataPlaneMarketGateway)
    cache = await services.aget(EndpointResponseCache)

    params = {"symbol": normalized_symbol, "exchange": exchange}

    async def fetch() -> CompanyFundamentals:
        try:
            profile, key_metrics, ratios = await asyncio.gather(
                asyncio.to_thread(
                    gateway.get_company_profile,
                    normalized_symbol,
                    exchange=exchange,
                ),
                asyncio.to_thread(
                    gateway.get_key_metrics,
                    normalized_symbol,
                    exchange=exchange,
                ),
                asyncio.to_thread(
                    gateway.get_financial_ratios,
                    normalized_symbol,
                    exchange=exchange,
                ),
            )
        except (
            MarketDataProviderError,
            MarketDataConfigurationError,
        ) as exc:
            raise _map_market_error(normalized_symbol, exc) from exc

        return CompanyFundamentals(
            profile=profile,
            key_metrics=key_metrics,
            ratios=ratios,
        )

    try:
        return await cache.cached_response(
            data_class="metrics",
            endpoint="fundamentals",
            params=params,
            fetch=fetch,
            model=CompanyFundamentals,
        )
    except MarketDataNotFoundError as exc:
        # An unknown symbol is negative-cached by the wrapper; translate the
        # re-raised domain error here so the 404 is served from cache on repeat.
        raise _map_market_error(normalized_symbol, exc) from exc


@data_router.get("/fundamentals/{symbol}/statements")
async def market_data_statements(  # noqa: PLR0913, PLR0917
    _svc: Annotated[None, Depends(require_service_token)],
    symbol: str,
    statement: Annotated[Literal["income", "balance", "cashflow"], Query()],
    services: DepContainer,
    period: Annotated[Literal["annual", "quarter"], Query()] = "annual",
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
    exchange: Annotated[str | None, Query()] = None,
) -> list[IncomeStatement] | list[BalanceSheet] | list[CashFlowStatement]:
    """Full FMP-shaped statement list for a symbol, served through the cache.

    ``statement`` and ``period`` are ``Literal``-typed so an invalid value is a
    FastAPI 422; the selected provider read keeps every line item the provider
    returns (the response is the bare statement list, matching the search
    route). ``exchange`` is forwarded for non-US ticker mapping.
    """
    normalized_symbol = symbol.upper()
    gateway = services.get(DataPlaneMarketGateway)
    cache = await services.aget(EndpointResponseCache)

    params = {
        "symbol": normalized_symbol,
        "statement": statement,
        "period": period,
        "limit": limit,
        "exchange": exchange,
    }

    async def fetch() -> (
        list[IncomeStatement] | list[BalanceSheet] | list[CashFlowStatement]
    ):
        try:
            if statement == "income":
                return await asyncio.to_thread(
                    gateway.get_income_statement,
                    normalized_symbol,
                    period,
                    limit,
                    exchange=exchange,
                )
            if statement == "balance":
                return await asyncio.to_thread(
                    gateway.get_balance_sheet,
                    normalized_symbol,
                    period,
                    limit,
                    exchange=exchange,
                )
            return await asyncio.to_thread(
                gateway.get_cash_flow_statement,
                normalized_symbol,
                period,
                limit,
                exchange=exchange,
            )
        except (
            MarketDataProviderError,
            MarketDataConfigurationError,
        ) as exc:
            raise _map_market_error(normalized_symbol, exc) from exc

    try:
        results = await cache.cached_response(
            data_class="statements",
            endpoint="statements",
            params=params,
            fetch=fetch,
            # The statement lists are plain FMP-shaped dicts on the cache hit; the
            # response schema is documented by the route's return annotation.
            model=None,
        )
    except MarketDataNotFoundError as exc:
        # An unknown symbol is negative-cached by the wrapper; translate the
        # re-raised domain error here so the 404 is served from cache on repeat.
        raise _map_market_error(normalized_symbol, exc) from exc

    # Raised after the cache wrapper so an empty successful result (if a
    # provider ever returns one) is cached as a stable 404 for the TTL.
    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No market data found for symbol '{normalized_symbol}'.",
        )

    return results
