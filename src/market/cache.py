import asyncio
import contextlib
import hashlib
import json
import logging
import threading
from collections.abc import AsyncIterator, Callable, Coroutine, Sequence
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal, cast
from uuid import UUID

import redis.asyncio as aioredis
from pydantic import BaseModel
from redis.asyncio.client import Redis

from src.config.settings import settings
from src.core.redis import RedisManager, redis_manager
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
from src.market.gateway import MarketGateway
from src.market.schema import IndicatorSpecSchema

logger = logging.getLogger(__name__)

DEFAULT_SEARCH_CACHE_TTL = 2_592_000  # 30 days in seconds


class IndicatorCache:
    """Cache for technical indicator calculations using Redis."""

    def __init__(self, redis_client: Redis, cache_ttl: int = 3600):
        """
        Initialize indicator cache.

        Args:
            redis_client: Redis client instance
            cache_ttl: Time-to-live for cache entries in seconds (default 1 hour)
        """
        self._redis = redis_client
        self._cache_ttl = cache_ttl

    @staticmethod
    def _normalize_window_bound(value: datetime | date | str | None) -> str | None:
        """Normalize a date/datetime window bound to a date-only ISO string.

        Datetimes are reduced to their calendar date so that equivalent
        ``date`` and ``datetime`` bounds share the same cache key.
        """
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)

    def _compute_indicator_digest(
        self,
        indicators: Sequence[str | IndicatorSpecSchema | dict[str, Any]],
        from_date: datetime | date | str | None = None,
        to_date: datetime | date | str | None = None,
    ) -> str:
        canonical_items = []
        for item in indicators:
            if isinstance(item, str):
                canonical_items.append({"type": item})
            elif isinstance(item, BaseModel):
                canonical_items.append(
                    item.model_dump(by_alias=True, exclude_none=True)
                )
            elif isinstance(item, dict):
                canonical_items.append(item)
            else:
                canonical_items.append(str(item))

        serialized_items = [
            json.dumps(item, sort_keys=True) for item in canonical_items
        ]
        canonical_payload = json.dumps(
            {
                "indicators": sorted(serialized_items),
                "from_date": self._normalize_window_bound(from_date),
                "to_date": self._normalize_window_bound(to_date),
            },
            sort_keys=True,
        )
        return hashlib.sha256(canonical_payload.encode()).hexdigest()

    def _get_cache_key(  # noqa: PLR0913, PLR0917
        self,
        security_id: str,
        indicators: Sequence[str | IndicatorSpecSchema | dict[str, Any]],
        price_count: int | None = None,
        interval: str = "1d",
        chart_style: str = "candlestick",
        from_date: datetime | date | str | None = None,
        to_date: datetime | date | str | None = None,
    ) -> str:
        """
        Generate cache key based on security, interval, chart style, indicators,
        and the requested date window.

        Args:
            security_id: Security identifier
            indicators: Sequence of requested indicators (specs, dicts, or strings)
            price_count: Optional number of price data points
            interval: Chart interval (default '1d')
            chart_style: Chart style (default 'candlestick')
            from_date: Optional start of the requested date window
            to_date: Optional end of the requested date window

        Returns:
            Cache key string
        """
        digest = self._compute_indicator_digest(
            indicators, from_date=from_date, to_date=to_date
        )
        key_parts = [
            "indicators",
            str(security_id),
            str(interval),
            str(chart_style),
            digest,
        ]
        if price_count is not None:
            key_parts.append(str(price_count))
        return ":".join(key_parts)

    async def get(  # noqa: PLR0913, PLR0917
        self,
        security_id: str,
        indicators: Sequence[str | IndicatorSpecSchema | dict[str, Any]],
        price_count: int | None = None,
        interval: str = "1d",
        chart_style: str = "candlestick",
        from_date: datetime | date | str | None = None,
        to_date: datetime | date | str | None = None,
    ) -> Any:
        """
        Get cached indicator data.

        Args:
            security_id: Security identifier
            indicators: Sequence of requested indicators
            price_count: Optional number of price data points
            interval: Candle interval
            chart_style: Chart style
            from_date: Optional start of the requested date window
            to_date: Optional end of the requested date window

        Returns:
            Cached indicator data or None if not found
        """
        if not indicators:
            return None

        cache_key = self._get_cache_key(
            security_id=security_id,
            indicators=indicators,
            price_count=price_count,
            interval=interval,
            chart_style=chart_style,
            from_date=from_date,
            to_date=to_date,
        )

        try:
            cached_data = await self._redis.get(cache_key)
        except Exception as e:  # noqa: BLE001
            logger.warning("Cache get error: %s", e)
            return None
        else:
            if cached_data:
                logger.debug(
                    "Cache hit for security %s indicators %s", security_id, indicators
                )
                return json.loads(cached_data)
            logger.debug(
                "Cache miss for security %s indicators %s", security_id, indicators
            )
            return None

    async def set(  # noqa: PLR0913, PLR0917
        self,
        security_id: str,
        indicators: Sequence[str | IndicatorSpecSchema | dict[str, Any]],
        price_count: int | None = None,
        data: dict[str, Any] | None = None,
        interval: str = "1d",
        chart_style: str = "candlestick",
        from_date: datetime | date | str | None = None,
        to_date: datetime | date | str | None = None,
    ) -> None:
        """
        Cache indicator data.

        Args:
            security_id: Security identifier
            indicators: Sequence of requested indicators
            price_count: Optional number of price data points
            data: Indicator data to cache
            interval: Candle interval
            chart_style: Chart style
            from_date: Optional start of the requested date window
            to_date: Optional end of the requested date window
        """
        if not indicators or data is None:
            return

        cache_key = self._get_cache_key(
            security_id=security_id,
            indicators=indicators,
            price_count=price_count,
            interval=interval,
            chart_style=chart_style,
            from_date=from_date,
            to_date=to_date,
        )

        try:
            await self._redis.setex(cache_key, self._cache_ttl, json.dumps(data))
            logger.debug("Cached indicators for security %s", security_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("Cache set error: %s", e)

    async def invalidate_security(self, security_id: str) -> None:
        """
        Invalidate all cached indicators for a security.

        Args:
            security_id: Security identifier
        """
        try:
            pattern = f"indicators:*{security_id}*"
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(cursor, match=pattern, count=100)
                if keys:
                    await self._redis.delete(*keys)
                if cursor == 0:
                    break
            logger.debug("Invalidated cache for security %s", security_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("Cache invalidation error: %s", e)

    async def flush_all(self) -> None:
        """
        Flush all cached indicator entries.
        """
        try:
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(
                    cursor, match="indicators:*", count=100
                )
                if keys:
                    await self._redis.delete(*keys)
                if cursor == 0:
                    break
            logger.debug("Flushed all indicator cache entries")
        except Exception as e:  # noqa: BLE001
            logger.warning("Cache flush error: %s", e)


async def indicator_cache_factory() -> IndicatorCache:
    """Factory function to create indicator cache instance."""
    redis_client = aioredis.from_url(
        settings.redis_url, encoding="utf-8", decode_responses=False
    )
    return IndicatorCache(redis_client)


class SecuritySearchCache:
    """Cache for security search results using Redis."""

    def __init__(
        self,
        redis_client: Redis | None = None,
        cache_ttl: int = DEFAULT_SEARCH_CACHE_TTL,
        redis_manager: RedisManager | None = None,
    ) -> None:
        self._redis_client = redis_client
        self._cache_ttl = cache_ttl
        self._redis_manager = redis_manager

    def _normalize_query(self, query: str) -> str:
        """
        Normalize search query: strip whitespace, lowercase, collapse internal spaces.
        """
        return " ".join(query.strip().lower().split())

    def _get_cache_key(self, query: str) -> str:
        """Generate normalized cache key for search query."""
        return f"market:search:{self._normalize_query(query)}"

    @contextlib.asynccontextmanager
    async def _get_client(self) -> AsyncIterator[Redis]:
        if self._redis_client is not None:
            yield self._redis_client
        elif self._redis_manager is not None:
            async with self._redis_manager.client() as client:
                yield client
        else:
            async with redis_manager.client() as client:
                yield client

    async def get(self, query: str) -> list[SecuritySearchResult] | None:
        """
        Get cached search results for query.

        Args:
            query: Search query string

        Returns:
            List of search results or None if not found or on error
        """
        normalized = self._normalize_query(query)
        if not normalized:
            return None

        cache_key = self._get_cache_key(normalized)
        try:
            async with self._get_client() as client:
                cached_data = await client.get(cache_key)

            if cached_data is None:
                return None

            items = json.loads(cached_data)
            if not isinstance(items, list):
                logger.warning(
                    "Invalid cache payload format for query %s: expected list, got %s",
                    query,
                    type(items).__name__,
                )
                return None

            return [SecuritySearchResult.model_validate(item) for item in items]
        except Exception as e:  # noqa: BLE001
            logger.warning("Cache get error for query %s: %s", query, e)
            return None

    async def set(
        self,
        query: str,
        results: list[SecuritySearchResult],
        ttl: int | None = None,
    ) -> None:
        """
        Cache search results for query.

        Args:
            query: Search query string
            results: List of search results to cache
            ttl: Optional TTL override in seconds (defaults to self._cache_ttl)
        """
        normalized = self._normalize_query(query)
        if not normalized:
            return

        cache_key = self._get_cache_key(normalized)
        effective_ttl = ttl if ttl is not None else self._cache_ttl

        try:
            payload = json.dumps([r.model_dump(mode="json") for r in results])
            async with self._get_client() as client:
                await client.setex(cache_key, effective_ttl, payload)
            logger.debug("Cached %d search results for query %s", len(results), query)
        except Exception as e:  # noqa: BLE001
            logger.warning("Cache set error for query %s: %s", query, e)


async def security_search_cache_factory() -> SecuritySearchCache:
    """Factory function to create security search cache instance."""
    return SecuritySearchCache(redis_manager=redis_manager)


# --------------------------------------------------------------------------- #
# Gateway-level cache wrapper.
#
# ``CachedMarketGateway`` is a transparent Redis cache in front of any
# ``MarketGateway``. It mirrors the full (synchronous) ABC so callers keep
# depending on ``MarketGateway`` only. Redis is async-only, so a small
# sync-to-async bridge submits cache coroutines to one shared background event
# loop: this works for plain sync callers and for callers already inside a
# running loop (never ``asyncio.run``, which would raise there). Every cache
# failure — connection errors, malformed payloads — degrades to the wrapped
# gateway and never propagates.
# --------------------------------------------------------------------------- #

_CACHE_KEY_PREFIX = "market:gw"
_NULL_SENTINEL: dict[str, bool] = {"null": True}

# Upper bound on how long a single cache operation may block its caller. Redis
# clients are configured with ``socket_timeout=None``, so without this a stalled
# server (or a dead background loop) would hang every caller instead of
# degrading to the wrapped gateway.
_CACHE_OP_TIMEOUT = 5.0


class CacheOpTimeoutError(RuntimeError):
    """Raised when a cache operation outlives the bounded bridge wait.

    ``_get_or_fetch`` handles it like any other cache failure: log a warning
    and fall back to the wrapped gateway.
    """


# method name -> Settings field holding the per-data-class TTL (seconds).
_TTL_SETTING_FIELDS: dict[str, str] = {
    "search": "gateway_ttl_search_seconds",
    "lookup_symbol": "gateway_ttl_search_seconds",
    "get_price_on_date": "gateway_ttl_prices_seconds",
    "get_prices": "gateway_ttl_prices_seconds",
    "get_intraday_prices": "gateway_ttl_prices_seconds",
    "get_income_statement": "gateway_ttl_statements_seconds",
    "get_balance_sheet": "gateway_ttl_statements_seconds",
    "get_cash_flow_statement": "gateway_ttl_statements_seconds",
    "get_key_metrics": "gateway_ttl_metrics_seconds",
    "get_financial_ratios": "gateway_ttl_metrics_seconds",
    "get_company_profile": "gateway_ttl_metrics_seconds",
    "get_options_chain": "gateway_ttl_options_seconds",
}

# method name -> (Pydantic result model, returns a list of that model).
_RESULT_MODELS: dict[str, tuple[type[BaseModel], bool]] = {
    "search": (SecuritySearchResult, True),
    "lookup_symbol": (SymbolLookupResult, True),
    "get_price_on_date": (HistoricalPrice, False),
    "get_prices": (HistoricalPrice, True),
    "get_intraday_prices": (IntradayHistoricalPrice, True),
    "get_income_statement": (IncomeStatement, True),
    "get_balance_sheet": (BalanceSheet, True),
    "get_cash_flow_statement": (CashFlowStatement, True),
    "get_key_metrics": (KeyMetrics, False),
    "get_financial_ratios": (FinancialRatios, False),
    "get_company_profile": (CompanyProfile, False),
    "get_options_chain": (OptionsChain, False),
}


def _normalize_query(value: str) -> str:
    """Normalize a free-text query so equivalent inputs share a cache key."""
    return " ".join(value.strip().lower().split())


def _canonicalize_datetime(value: datetime) -> str:
    """Keep the full timestamp for intraday windows.

    Daily windows intentionally collapse ``date`` and ``datetime`` to a
    calendar date (see :func:`_canonicalize`), but intraday requests carry a
    materially different time range on the same day, so their key must keep
    hour/minute precision to avoid serving the wrong window.
    """
    return value.isoformat()


def _canonicalize(value: Any) -> Any:  # noqa: PLR0911
    """Reduce a cache-key argument to a JSON-serializable primitive.

    ``datetime`` is reduced to its calendar date (matching
    ``IndicatorCache._normalize_window_bound``) so equivalent ``date`` and
    ``datetime`` window bounds share a key.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        # ``normalize`` drops insignificant trailing zeros so equivalent
        # decimals (``Decimal("10.5")`` / ``Decimal("10.50")``) share a key.
        return str(value.normalize())
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _canonicalize(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_canonicalize(item) for item in value]
    if isinstance(value, str | int | float | bool):
        return value
    return str(value)


def _cache_key(method: str, **params: Any) -> str:
    """Build a deterministic cache key from a method name and its arguments."""
    canonical = {name: _canonicalize(value) for name, value in params.items()}
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode()).hexdigest()[:40]
    return f"{_CACHE_KEY_PREFIX}:{method}:{digest}"


def _ttl_for(method: str) -> int:
    """Resolve the configured TTL for a gateway method at call time."""
    return int(getattr(settings, _TTL_SETTING_FIELDS[method]))


def _encode_result(method: str, result: Any) -> str:
    """Serialize a gateway result to the JSON payload stored in Redis."""
    if result is None:
        return json.dumps(_NULL_SENTINEL)
    _model, is_list = _RESULT_MODELS[method]
    if is_list:
        return json.dumps([item.model_dump(mode="json") for item in result])
    return json.dumps(result.model_dump(mode="json"))


def _decode_result(method: str, payload: str) -> Any:
    """Deserialize a cached payload back to typed T01 results.

    Raises on malformed payloads; the caller treats that as a cache miss.
    """
    decoded: Any = json.loads(payload)
    if method == "get_price_on_date" and decoded == _NULL_SENTINEL:
        return None
    model, is_list = _RESULT_MODELS[method]
    if is_list:
        if not isinstance(decoded, list):
            msg = f"expected a list payload for {method}"
            raise ValueError(msg)
        return [model.model_validate(item) for item in decoded]
    return model.model_validate(decoded)


class _CacheBridge:
    """Owns the shared background loop that executes cache coroutines."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()

    def loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is not None and not self._loop.is_closed():
            return self._loop
        with self._lock:
            if self._loop is None or self._loop.is_closed():
                loop = asyncio.new_event_loop()
                threading.Thread(
                    target=loop.run_forever,
                    name="market-gateway-cache",
                    daemon=True,
                ).start()
                self._loop = loop
        return self._loop

    def run[T](self, coro: Coroutine[Any, Any, T]) -> T:
        """Run ``coro`` on the background loop with a bounded wait.

        A stalled Redis socket or a dead background loop must never hang the
        caller: once ``_CACHE_OP_TIMEOUT`` elapses the future is cancelled
        best-effort, a loop whose thread has died is dropped so the next call
        recreates it, and :class:`CacheOpTimeoutError` is raised so the caller
        degrades to the wrapped gateway.
        """
        future = asyncio.run_coroutine_threadsafe(coro, self.loop())
        try:
            return future.result(timeout=_CACHE_OP_TIMEOUT)
        except FutureTimeoutError as e:
            logger.warning(
                "Gateway cache operation timed out after %.1fs; "
                "degrading to the provider",
                _CACHE_OP_TIMEOUT,
            )
            future.cancel()
            self._recreate_loop_if_dead()
            msg = f"cache operation exceeded {_CACHE_OP_TIMEOUT}s"
            raise CacheOpTimeoutError(msg) from e

    def _recreate_loop_if_dead(self) -> None:
        """Drop the background loop if its thread is no longer running."""
        loop = self._loop
        if loop is None or loop.is_closed() or loop.is_running():
            return
        with self._lock:
            if self._loop is loop and not loop.is_running():
                self._loop = None


_cache_bridge = _CacheBridge()


def _run_cache_op[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run a cache coroutine from sync code without deadlocking.

    Always targets the shared background loop — never the caller's loop and
    never ``asyncio.run`` — so it is safe whether or not the calling thread
    already has a running event loop.

    NOTE: being a synchronous bridge, a caller that is itself on an async event
    loop (e.g. ``src/market/api.py``) blocks that loop for one Redis round-trip
    per cache operation while waiting here. That is accepted for now (T06 wired
    the gateway but did not make endpoints async-first); the bounded wait in
    :meth:`_CacheBridge.run` keeps the block finite, and the Redis clients are
    configured with bounded socket timeouts (see ``src/core/redis.py``).
    """
    return _cache_bridge.run(coro)


class CachedMarketGateway(MarketGateway):
    """Transparent Redis cache wrapper around another :class:`MarketGateway`.

    Each gateway read is tried in the cache first, delegated to the wrapped
    gateway on a miss and then written back with a per-data-class TTL. The
    wrapper implements the full synchronous :class:`MarketGateway` ABC, so it
    is a drop-in replacement wherever a ``MarketGateway`` is injected.
    """

    def __init__(self, inner: MarketGateway) -> None:
        self._inner = inner

    # -- key / serialization helpers ------------------------------------- #

    def _get_or_fetch[T](self, method: str, key: str, fetch: Callable[[], T]) -> T:
        """Serve ``method`` from cache, falling back to ``fetch`` on any error."""
        payload: str | None = None
        try:
            payload = _run_cache_op(self._async_get(key))
        except Exception as e:  # noqa: BLE001
            logger.warning("Gateway cache read failed for %s: %s", method, e)
        else:
            if payload is not None:
                try:
                    return cast("T", _decode_result(method, payload))
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "Gateway cache payload invalid for %s: %s", method, e
                    )

        result = fetch()
        try:
            encoded = _encode_result(method, result)
            _run_cache_op(self._async_set(key, encoded, _ttl_for(method)))
        except Exception as e:  # noqa: BLE001
            logger.warning("Gateway cache write failed for %s: %s", method, e)
        return result

    @staticmethod
    async def _async_get(key: str) -> str | None:
        async with redis_manager.client() as client:
            value = await client.get(key)
        if isinstance(value, bytes):
            return value.decode()
        return value

    @staticmethod
    async def _async_set(key: str, payload: str, ttl: int) -> None:
        async with redis_manager.client() as client:
            await client.setex(key, ttl, payload)

    # -- MarketGateway surface ------------------------------------------- #

    def search(self, query: str) -> list[SecuritySearchResult]:
        """Search for securities by query string."""
        key = _cache_key("search", query=_normalize_query(query))
        return self._get_or_fetch("search", key, lambda: self._inner.search(query))

    def get_price_on_date(
        self,
        security_id: SecurityId,
        symbol: str,
        exchange: str,
        date: date,
    ) -> HistoricalPrice | None:
        """Get price for a security on a specific date."""
        key = _cache_key(
            "get_price_on_date",
            security_id=security_id,
            symbol=symbol,
            exchange=exchange,
            date=date,
        )
        return self._get_or_fetch(
            "get_price_on_date",
            key,
            lambda: self._inner.get_price_on_date(security_id, symbol, exchange, date),
        )

    def get_prices(
        self,
        security_id: SecurityId,
        symbol: str,
        exchange: str,
        from_date: date,
        to_date: date,
    ) -> list[HistoricalPrice]:
        """Get historical prices for a security within a date range."""
        key = _cache_key(
            "get_prices",
            security_id=security_id,
            symbol=symbol,
            exchange=exchange,
            from_date=from_date,
            to_date=to_date,
        )
        return self._get_or_fetch(
            "get_prices",
            key,
            lambda: self._inner.get_prices(
                security_id, symbol, exchange, from_date, to_date
            ),
        )

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
        key = _cache_key(
            "get_intraday_prices",
            security_id=security_id,
            symbol=symbol,
            exchange=exchange,
            from_datetime=_canonicalize_datetime(from_datetime),
            to_datetime=_canonicalize_datetime(to_datetime),
            interval=interval,
        )
        return self._get_or_fetch(
            "get_intraday_prices",
            key,
            lambda: self._inner.get_intraday_prices(
                security_id,
                symbol,
                exchange,
                from_datetime,
                to_datetime,
                interval=interval,
            ),
        )

    def lookup_symbol(self, query: str) -> list[SymbolLookupResult]:
        """Look up symbols/companies matching a free-text query."""
        key = _cache_key("lookup_symbol", query=_normalize_query(query))
        return self._get_or_fetch(
            "lookup_symbol", key, lambda: self._inner.lookup_symbol(query)
        )

    def get_company_profile(
        self,
        symbol: str,
        *,
        exchange: str | None = None,
    ) -> CompanyProfile:
        """Get the company profile for a symbol."""
        key = _cache_key("get_company_profile", symbol=symbol, exchange=exchange)
        return self._get_or_fetch(
            "get_company_profile",
            key,
            lambda: self._inner.get_company_profile(symbol, exchange=exchange),
        )

    def get_income_statement(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
        *,
        exchange: str | None = None,
    ) -> list[IncomeStatement]:
        """Get income statements for a symbol."""
        key = _cache_key(
            "get_income_statement",
            symbol=symbol,
            period=period,
            limit=limit,
            exchange=exchange,
        )
        return self._get_or_fetch(
            "get_income_statement",
            key,
            lambda: self._inner.get_income_statement(
                symbol, period, limit, exchange=exchange
            ),
        )

    def get_balance_sheet(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
        *,
        exchange: str | None = None,
    ) -> list[BalanceSheet]:
        """Get balance sheets for a symbol."""
        key = _cache_key(
            "get_balance_sheet",
            symbol=symbol,
            period=period,
            limit=limit,
            exchange=exchange,
        )
        return self._get_or_fetch(
            "get_balance_sheet",
            key,
            lambda: self._inner.get_balance_sheet(
                symbol, period, limit, exchange=exchange
            ),
        )

    def get_cash_flow_statement(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
        *,
        exchange: str | None = None,
    ) -> list[CashFlowStatement]:
        """Get cash-flow statements for a symbol."""
        key = _cache_key(
            "get_cash_flow_statement",
            symbol=symbol,
            period=period,
            limit=limit,
            exchange=exchange,
        )
        return self._get_or_fetch(
            "get_cash_flow_statement",
            key,
            lambda: self._inner.get_cash_flow_statement(
                symbol, period, limit, exchange=exchange
            ),
        )

    def get_key_metrics(
        self,
        symbol: str,
        *,
        exchange: str | None = None,
    ) -> KeyMetrics:
        """Get the key metrics / valuation snapshot for a symbol."""
        key = _cache_key("get_key_metrics", symbol=symbol, exchange=exchange)
        return self._get_or_fetch(
            "get_key_metrics",
            key,
            lambda: self._inner.get_key_metrics(symbol, exchange=exchange),
        )

    def get_financial_ratios(
        self,
        symbol: str,
        period: str = "annual",
        *,
        exchange: str | None = None,
    ) -> FinancialRatios:
        """Get financial ratios for a symbol."""
        key = _cache_key(
            "get_financial_ratios",
            symbol=symbol,
            period=period,
            exchange=exchange,
        )
        return self._get_or_fetch(
            "get_financial_ratios",
            key,
            lambda: self._inner.get_financial_ratios(symbol, period, exchange=exchange),
        )

    def get_options_chain(
        self,
        symbol: str,
        *,
        expiration: date | None = None,
        contract_type: Literal["call", "put"] | None = None,
        strike_min: Decimal | None = None,
        strike_max: Decimal | None = None,
    ) -> OptionsChain:
        """Get the options chain for an underlying symbol."""
        key = _cache_key(
            "get_options_chain",
            symbol=symbol,
            expiration=expiration,
            contract_type=contract_type,
            strike_min=strike_min,
            strike_max=strike_max,
        )
        return self._get_or_fetch(
            "get_options_chain",
            key,
            lambda: self._inner.get_options_chain(
                symbol,
                expiration=expiration,
                contract_type=contract_type,
                strike_min=strike_min,
                strike_max=strike_max,
            ),
        )
