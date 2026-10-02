import contextlib
import hashlib
import json
import logging
from collections.abc import AsyncIterator, Sequence
from datetime import date, datetime, timedelta
from typing import Any

import redis.asyncio as aioredis
from pydantic import BaseModel
from redis.asyncio.client import Redis

from src.config.settings import settings
from src.core.redis import RedisManager, redis_manager
from src.market.api_types import SecuritySearchResult
from src.market.schema import IndicatorSpecSchema
from src.observability import emit_event

logger = logging.getLogger(__name__)

DEFAULT_SEARCH_CACHE_TTL = 2_592_000  # 30 days in seconds

#: Static cache-namespace labels used as the ``key_class`` telemetry dimension.
#: These are deliberately constants: the raw user-scoped ``cache_key`` must
#: never be emitted.
CACHE_KIND_INDICATOR = "indicator"
CACHE_KIND_SECURITY_SEARCH = "security_search"

#: Failure class attached to a ``market.cache.accessed`` miss caused by Redis.
CACHE_ERROR_SLUG = "cache_error"


def _emit_cache_accessed(
    *,
    cache_kind: str,
    key_class: str,
    outcome: str,
    ttl_seconds: int | None = None,
    error_slug: str | None = None,
) -> None:
    """
    Emit one ``market.cache.accessed`` wide event, best-effort only.

    Telemetry must never change cache behaviour, so any emission failure is
    swallowed. ``key_class`` is a static cache-namespace label, never the raw
    user-scoped cache key.
    """
    try:
        emit_event(
            "market.cache.accessed",
            cache_kind=cache_kind,
            key_class=key_class,
            outcome=outcome,
            ttl_seconds=ttl_seconds,
            error_slug=error_slug,
        )
    except Exception as error:  # noqa: BLE001
        logger.debug("Cache telemetry emission failed: %s", error)


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
            _emit_cache_accessed(
                cache_kind=CACHE_KIND_INDICATOR,
                key_class=CACHE_KIND_INDICATOR,
                outcome="miss",
                ttl_seconds=self._cache_ttl,
                error_slug=CACHE_ERROR_SLUG,
            )
            return None
        else:
            if cached_data:
                logger.debug(
                    "Cache hit for security %s indicators %s", security_id, indicators
                )
                payload = json.loads(cached_data)
                _emit_cache_accessed(
                    cache_kind=CACHE_KIND_INDICATOR,
                    key_class=CACHE_KIND_INDICATOR,
                    outcome="negative" if payload == {} else "hit",
                    ttl_seconds=self._cache_ttl,
                )
                return payload
            logger.debug(
                "Cache miss for security %s indicators %s", security_id, indicators
            )
            _emit_cache_accessed(
                cache_kind=CACHE_KIND_INDICATOR,
                key_class=CACHE_KIND_INDICATOR,
                outcome="miss",
                ttl_seconds=self._cache_ttl,
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
        else:
            _emit_cache_accessed(
                cache_kind=CACHE_KIND_INDICATOR,
                key_class=CACHE_KIND_INDICATOR,
                outcome="write",
                ttl_seconds=self._cache_ttl,
            )

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
                _emit_cache_accessed(
                    cache_kind=CACHE_KIND_SECURITY_SEARCH,
                    key_class=CACHE_KIND_SECURITY_SEARCH,
                    outcome="miss",
                    ttl_seconds=self._cache_ttl,
                )
                return None

            items = json.loads(cached_data)
            if not isinstance(items, list):
                logger.warning(
                    "Invalid cache payload format for query %s: expected list, got %s",
                    query,
                    type(items).__name__,
                )
                _emit_cache_accessed(
                    cache_kind=CACHE_KIND_SECURITY_SEARCH,
                    key_class=CACHE_KIND_SECURITY_SEARCH,
                    outcome="miss",
                    ttl_seconds=self._cache_ttl,
                )
                return None

            results = [SecuritySearchResult.model_validate(item) for item in items]
        except Exception as e:  # noqa: BLE001
            logger.warning("Cache get error for query %s: %s", query, e)
            _emit_cache_accessed(
                cache_kind=CACHE_KIND_SECURITY_SEARCH,
                key_class=CACHE_KIND_SECURITY_SEARCH,
                outcome="miss",
                ttl_seconds=self._cache_ttl,
                error_slug=CACHE_ERROR_SLUG,
            )
            return None

        _emit_cache_accessed(
            cache_kind=CACHE_KIND_SECURITY_SEARCH,
            key_class=CACHE_KIND_SECURITY_SEARCH,
            outcome="negative" if not results else "hit",
            ttl_seconds=self._cache_ttl,
        )
        return results

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
        else:
            _emit_cache_accessed(
                cache_kind=CACHE_KIND_SECURITY_SEARCH,
                key_class=CACHE_KIND_SECURITY_SEARCH,
                outcome="write",
                ttl_seconds=effective_ttl,
            )


async def security_search_cache_factory() -> SecuritySearchCache:
    """Factory function to create security search cache instance."""
    return SecuritySearchCache(redis_manager=redis_manager)
