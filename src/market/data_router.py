"""Service-to-service market data endpoints.

These routes expose the provider-agnostic data plane to trusted services (the
MCP gateway in T10/T11). They are deliberately separate from the user-JWT
``market_router``:

* authentication is the shared-secret ``require_service_token`` dependency;
* every route resolves the ``DataPlaneMarketGateway`` svcs key (the composed
  market data gateway) and serves through the T13
  :class:`EndpointResponseCache` — the single canonical data-plane cache;
* every price-bearing response has a required top-level ``currency``;
* error mapping stays here: an unknown symbol becomes a structured 404 and a
  provider outage a generic 502/503 — a provider name never appears in a
  response body.

The route paths and query parameter names are a stable contract for the Go MCP
gateway (T10/T11); do not rename them:

* ``GET /api/v1/market/data/prices/{symbol}`` — ``from``, ``to``, ``exchange``
  (``SupportedExchange``)
* ``GET /api/v1/market/data/indicators/{symbol}`` — ``indicator``, ``period``,
  ``fast``, ``slow``, ``signal``, ``std_dev``, ``from``, ``to``, ``exchange``
  (``SupportedExchange``)
* ``GET /api/v1/market/data/symbols/search`` — ``q``
* ``GET /api/v1/market/data/options/{symbol}`` — ``expiry``, ``option_type``,
  ``strike_min``, ``strike_max``
* ``GET /api/v1/market/data/fundamentals/{symbol}`` — ``exchange``
  (``SupportedExchange``)
* ``GET /api/v1/market/data/fundamentals/{symbol}/statements`` — ``statement``
  (``income``/``balance``/``cashflow``), ``period`` (``annual``/``quarter``),
  ``limit``, ``exchange`` (``SupportedExchange``)

``exchange`` is forwarded to the gateway on every route that accepts it so
non-US symbols map to the provider's ticker suffix; the fundamentals overview
returns the canonical profile plus key metrics and ratios, and the statements
route returns the canonical statement list for the requested
``statement``/``period``.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from svcs.fastapi import DepContainer

from src.auth.api import require_service_token
from src.market.api_types import (
    BalanceSheet,
    CashFlowStatement,
    CompanyFundamentals,
    HistoricalPrice,
    IncomeStatement,
    IndicatorSeriesResponse,
    OptionExpirations,
    OptionsChain,
    SupportedExchange,
    SupportedIndicator,
    SymbolLookupResult,
)
from src.market.currency import resolve_listing_currency
from src.market.endpoint_cache import EndpointResponseCache
from src.market.exception import (
    MarketDataConfigurationError,
    MarketDataNotFoundError,
    MarketDataProviderError,
)
from src.market.gateway import DataPlaneMarketGateway
from src.market.price_aggregation import (
    PriceInterval,
    aggregate_bars,
    resolve_price_range,
)
from src.market.schema import (
    IndicatorCandleSchema,
    IndicatorSpecSchema,
    PriceBar,
    PriceHistoryResponse,
)
from src.market.service import IndicatorServiceClient

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
async def market_data_prices(  # noqa: PLR0913, PLR0917
    _svc: Annotated[None, Depends(require_service_token)],
    symbol: str,
    services: DepContainer,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: Annotated[date | None, Query()] = None,
    interval: Annotated[PriceInterval, Query()] = "day",
    exchange: Annotated[SupportedExchange | None, Query()] = None,
) -> PriceHistoryResponse:
    """Price history for a symbol, served through the endpoint cache."""
    resolved_from, resolved_to = resolve_price_range(from_, to, interval)

    normalized_symbol = symbol.upper()
    gateway = services.get(DataPlaneMarketGateway)
    cache = await services.aget(EndpointResponseCache)

    # Date-only bounds: ``get_prices`` is a daily read, and passing plain
    # ``date`` objects keeps the cache key free of the naive/aware midnight
    # ambiguity (``_canonicalize_param`` never sees a ``datetime`` here).
    params = {
        "symbol": normalized_symbol,
        "exchange": exchange,
        "from": resolved_from,
        "to": resolved_to,
        "interval": interval,
    }

    async def fetch() -> PriceHistoryResponse:
        prices_task = _fetch_prices(
            gateway, normalized_symbol, exchange, resolved_from, resolved_to
        )
        currency_task = resolve_listing_currency(
            gateway, cache, normalized_symbol, exchange
        )
        try:
            prices, currency = await asyncio.gather(prices_task, currency_task)
        except (
            MarketDataProviderError,
            MarketDataConfigurationError,
        ) as exc:
            raise _map_market_error(normalized_symbol, exc) from exc

        bars = [
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
        ]
        aggregated = aggregate_bars(bars, interval)

        return PriceHistoryResponse(
            symbol=normalized_symbol,
            currency=currency,
            exchange=exchange,
            from_date=resolved_from,
            to_date=resolved_to,
            interval=interval,
            items=aggregated,
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


def _to_indicator_candles(
    prices: list[HistoricalPrice],
) -> list[IndicatorCandleSchema]:
    """Convert historical prices to candles expected by the indicator service."""
    candles: list[IndicatorCandleSchema] = []
    for p in sorted(prices, key=lambda item: item.date):
        split_ratio = (
            float(p.adjusted_close) / float(p.close)
            if p.adjusted_close is not None
            and p.close is not None
            and float(p.close) != 0
            and float(p.adjusted_close) != float(p.close)
            else 1.0
        )
        candles.append(
            IndicatorCandleSchema(
                time=p.date.isoformat(),
                open=float(p.open) * split_ratio,
                high=float(p.high) * split_ratio,
                low=float(p.low) * split_ratio,
                close=(
                    float(p.adjusted_close) if split_ratio != 1.0 else float(p.close)
                ),
                volume=float(p.volume),
            )
        )
    return candles


def _parse_point_date(pt: dict[str, Any]) -> date | None:
    time_val = pt.get("time")
    if isinstance(time_val, date) and not isinstance(time_val, datetime):
        return time_val
    if isinstance(time_val, datetime):
        return time_val.date()
    if isinstance(time_val, str):
        try:
            return date.fromisoformat(time_val[:10])
        except ValueError:
            return None
    return None


def _resolve_indicator_spec(  # noqa: PLR0913, PLR0917
    indicator: SupportedIndicator,
    period: int | None,
    fast: int | None,
    slow: int | None,
    signal: int | None,
    std_dev: float | None,
) -> tuple[IndicatorSpecSchema, dict[str, Any], int]:
    """Resolve default parameters, indicator spec, and longest lookback."""
    if indicator == "bollinger":
        resolved_period = period if period is not None else 20
        resolved_std_dev = std_dev if std_dev is not None else 2.0
        return (
            IndicatorSpecSchema(
                type="bb",
                period=resolved_period,
                std_dev=resolved_std_dev,
            ),
            {"period": resolved_period, "std_dev": resolved_std_dev},
            resolved_period,
        )
    if indicator == "macd":
        resolved_fast = fast if fast is not None else 12
        resolved_slow = slow if slow is not None else 26
        resolved_signal = signal if signal is not None else 9
        return (
            IndicatorSpecSchema(
                type="macd",
                fast=resolved_fast,
                slow=resolved_slow,
                signal=resolved_signal,
            ),
            {"fast": resolved_fast, "slow": resolved_slow, "signal": resolved_signal},
            resolved_slow + resolved_signal,
        )
    if indicator in ("sma", "ema", "rsi"):
        resolved_period = period if period is not None else 14
        return (
            IndicatorSpecSchema(type=indicator, period=resolved_period),
            {"period": resolved_period},
            resolved_period,
        )
    raise HTTPException(
        status_code=422,
        detail=f"Unsupported indicator '{indicator}'.",
    )


def _trim_indicator_points(
    computed: Any,
    spec: IndicatorSpecSchema,
    indicator: str,
    from_date: date,
    to_date: date,
) -> list[dict[str, Any]]:
    """Trim computed indicator points to [from_date, to_date]."""
    raw_points: list[dict[str, Any]] = []
    if isinstance(computed, dict):
        raw_points = (
            computed.get(spec.type)
            or computed.get("bb")
            or computed.get(indicator)
            or (next(iter(computed.values())) if computed else [])
        )
    elif isinstance(computed, list):
        raw_points = computed

    return [
        pt
        for pt in raw_points
        if (d := _parse_point_date(pt)) is not None and from_date <= d <= to_date
    ]


@data_router.get("/indicators/{symbol}")
async def market_data_indicator(  # noqa: PLR0913, PLR0917
    _svc: Annotated[None, Depends(require_service_token)],
    symbol: str,
    services: DepContainer,
    indicator: Annotated[SupportedIndicator, Query()],
    period: Annotated[int | None, Query(ge=2, le=400)] = None,
    fast: Annotated[int | None, Query(ge=2, le=400)] = None,
    slow: Annotated[int | None, Query(ge=2, le=400)] = None,
    signal: Annotated[int | None, Query(ge=2, le=400)] = None,
    std_dev: Annotated[float | None, Query(gt=0)] = None,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: Annotated[date | None, Query()] = None,
    exchange: Annotated[SupportedExchange | None, Query()] = None,
) -> IndicatorSeriesResponse:
    """Technical indicator series for a symbol, served through the endpoint cache."""
    resolved_from, resolved_to = resolve_price_range(from_, to, "day")
    spec, resolved_params, longest_lookback = _resolve_indicator_spec(
        indicator, period, fast, slow, signal, std_dev
    )

    # Warm-up length = 3 * longest lookback, converted to calendar days * 7/5 + 10.
    warmup_bars = 3 * longest_lookback
    warmup_days = int(warmup_bars * 7 / 5) + 10
    fetch_from = resolved_from - timedelta(days=warmup_days)

    normalized_symbol = symbol.upper()
    gateway = services.get(DataPlaneMarketGateway)
    cache = await services.aget(EndpointResponseCache)

    cache_params: dict[str, Any] = {
        "symbol": normalized_symbol,
        "exchange": exchange,
        "indicator": indicator,
        "from": resolved_from,
        "to": resolved_to,
    }
    cache_params.update(resolved_params)

    async def fetch() -> IndicatorSeriesResponse:
        prices_task = _fetch_prices(
            gateway, normalized_symbol, exchange, fetch_from, resolved_to
        )
        currency_task = resolve_listing_currency(
            gateway, cache, normalized_symbol, exchange
        )
        try:
            prices, currency = await asyncio.gather(prices_task, currency_task)
        except (
            MarketDataProviderError,
            MarketDataConfigurationError,
        ) as exc:
            raise _map_market_error(normalized_symbol, exc) from exc

        candles = _to_indicator_candles(prices)
        if not candles:
            return IndicatorSeriesResponse(
                symbol=normalized_symbol,
                indicator=indicator,
                currency=currency,
                exchange=exchange,
                params=resolved_params,
                from_date=resolved_from,
                to_date=resolved_to,
                points=[],
            )

        indicator_client = await services.aget(IndicatorServiceClient)
        computed = await indicator_client.compute(
            interval="1d",
            candles=candles,
            indicators=[spec],
        )

        trimmed_points = _trim_indicator_points(
            computed, spec, indicator, resolved_from, resolved_to
        )

        return IndicatorSeriesResponse(
            symbol=normalized_symbol,
            indicator=indicator,
            currency=currency,
            exchange=exchange,
            params=resolved_params,
            from_date=resolved_from,
            to_date=resolved_to,
            points=trimmed_points,
        )

    try:
        response = await cache.cached_response(
            data_class="prices",
            endpoint="indicator",
            params=cache_params,
            fetch=fetch,
            model=IndicatorSeriesResponse,
        )
    except MarketDataNotFoundError as exc:
        raise _map_market_error(normalized_symbol, exc) from exc

    if not response.points:
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


@data_router.get("/options/{symbol}/expirations")
async def market_data_option_expirations(
    _svc: Annotated[None, Depends(require_service_token)],
    symbol: str,
    services: DepContainer,
) -> OptionExpirations:
    """Available option expiration dates for an underlying symbol."""
    normalized_symbol = symbol.upper()
    gateway = services.get(DataPlaneMarketGateway)
    cache = await services.aget(EndpointResponseCache)

    params = {"symbol": normalized_symbol}

    async def fetch() -> OptionExpirations:
        try:
            return await asyncio.to_thread(
                gateway.get_option_expirations,
                normalized_symbol,
            )
        except (
            MarketDataProviderError,
            MarketDataConfigurationError,
        ) as exc:
            raise _map_market_error(normalized_symbol, exc) from exc

    try:
        return await cache.cached_response(
            data_class="options",
            endpoint="expirations",
            params=params,
            fetch=fetch,
            model=OptionExpirations,
        )
    except MarketDataNotFoundError as exc:
        raise _map_market_error(normalized_symbol, exc) from exc


@data_router.get("/options/{symbol}")
async def market_data_options(  # noqa: PLR0913, PLR0917
    _svc: Annotated[None, Depends(require_service_token)],
    symbol: str,
    services: DepContainer,
    expiry: Annotated[date, Query()],
    option_type: Annotated[Literal["call", "put"] | None, Query()] = None,
    strike_min: Annotated[Decimal | None, Query()] = None,
    strike_max: Annotated[Decimal | None, Query()] = None,
) -> OptionsChain:
    """Options chain for an underlying."""
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
        options_task = asyncio.to_thread(
            gateway.get_options_chain,
            normalized_symbol,
            expiration=expiry,
            contract_type=option_type,
            strike_min=strike_min,
            strike_max=strike_max,
        )
        currency_task = resolve_listing_currency(
            gateway, cache, normalized_symbol, exchange=None
        )
        try:
            chain, currency = await asyncio.gather(options_task, currency_task)
        except (
            MarketDataProviderError,
            MarketDataConfigurationError,
        ) as exc:
            raise _map_market_error(normalized_symbol, exc) from exc

        return chain.model_copy(update={"currency": currency})

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


async def _optional_section[T](call: Awaitable[T]) -> T | None:
    """Return None when an optional section raises MarketDataNotFoundError."""
    try:
        return await call
    except MarketDataNotFoundError:
        return None


@data_router.get("/fundamentals/{symbol}")
async def market_data_fundamentals(
    _svc: Annotated[None, Depends(require_service_token)],
    symbol: str,
    services: DepContainer,
    exchange: Annotated[SupportedExchange | None, Query()] = None,
) -> CompanyFundamentals:
    """Company details plus key metrics and ratios, served through the cache.

    The response keeps the canonical ``profile``, ``key_metrics`` and
    ``ratios`` objects field-for-field; ``exchange`` is forwarded so non-US
    symbols map to the provider's ticker suffix. Key metrics and ratios are
    nullable when unavailable upstream.
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
                _optional_section(
                    asyncio.to_thread(
                        gateway.get_key_metrics,
                        normalized_symbol,
                        exchange=exchange,
                    )
                ),
                _optional_section(
                    asyncio.to_thread(
                        gateway.get_financial_ratios,
                        normalized_symbol,
                        exchange=exchange,
                    )
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
    exchange: Annotated[SupportedExchange | None, Query()] = None,
) -> list[IncomeStatement] | list[BalanceSheet] | list[CashFlowStatement]:
    """Statement list for a symbol, served through the cache.

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
            # The statement lists are plain dicts on the cache hit; the
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
