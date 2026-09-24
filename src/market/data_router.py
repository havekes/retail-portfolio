"""Service-to-service market data endpoints.

These routes expose the provider-agnostic data plane to trusted services (the
MCP gateway in T10/T11). They are deliberately separate from the user-JWT
``market_router``:

* authentication is the shared-secret ``require_service_token`` dependency;
* every route resolves the ``DataPlaneMarketGateway`` svcs key (the composed
  FMP/Polygon gateway wrapped in the gateway-level cache) and serves through
  the T13 :class:`EndpointResponseCache`;
* error mapping stays here: an unknown symbol becomes a structured 404 and a
  provider outage a generic 502/503 — a provider name never appears in a
  response body.

The route paths and query parameter names are a stable contract for the Go MCP
gateway (T10/T11); do not rename them:

* ``GET /api/v1/market/data/prices/{symbol}`` — ``from``, ``to``, ``exchange``
* ``GET /api/v1/market/data/symbols/search`` — ``q``
* ``GET /api/v1/market/data/options/{symbol}`` — ``expiry``, ``option_type``,
  ``strike_min``, ``strike_max``
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from svcs.fastapi import DepContainer

from src.auth.api import require_service_token
from src.market.api_types import HistoricalPrice, OptionsChain, SymbolLookupResult
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

# The data-plane gateway's ``get_prices`` signature still requires a
# ``security_id`` (it satisfies the DB-backed gateway contract), but a data-plane
# request has no security identity: prices are keyed by symbol/exchange. This nil
# UUID is a placeholder only — it never reaches a provider and is dropped when
# mapping to :class:`PriceBar`.
_NIL_SECURITY_ID = UUID(int=0)

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

    ``MarketGateway.get_prices`` is synchronous (the composed gateway wraps
    ``requests``/sync-Redis calls), so it must not run on the loop.
    """
    return await asyncio.to_thread(
        gateway.get_prices,
        _NIL_SECURITY_ID,
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
            MarketDataNotFoundError,
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

    response = await cache.cached_response(
        data_class="prices",
        endpoint="history",
        params=params,
        fetch=fetch,
        model=PriceHistoryResponse,
    )

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
            MarketDataNotFoundError,
            MarketDataProviderError,
            MarketDataConfigurationError,
        ) as exc:
            raise _map_market_error(q, exc) from exc

    results = await cache.cached_response(
        data_class="search",
        endpoint="symbol_lookup",
        params=params,
        fetch=fetch,
        model=SymbolLookupResult,
    )

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
            MarketDataNotFoundError,
            MarketDataProviderError,
            MarketDataConfigurationError,
        ) as exc:
            raise _map_market_error(normalized_symbol, exc) from exc

    return await cache.cached_response(
        data_class="options",
        endpoint="chain",
        params=params,
        fetch=fetch,
        model=OptionsChain,
    )
