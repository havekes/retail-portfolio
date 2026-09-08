import contextlib
import hashlib
import json
import logging
from collections.abc import AsyncIterator, Sequence
from datetime import timedelta
from typing import Any

import redis.asyncio as aioredis
from pydantic import BaseModel
from redis.asyncio.client import Redis

from src.config.settings import settings
from src.core.redis import RedisManager, redis_manager
from src.market.api_types import SecuritySearchResult
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

    def _compute_indicator_digest(
        self,
        indicators: Sequence[str | IndicatorSpecSchema | dict[str, Any]],
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
        canonical_payload = json.dumps(sorted(serialized_items))
        return hashlib.sha256(canonical_payload.encode()).hexdigest()

    def _get_cache_key(
        self,
        security_id: str,
        indicators: Sequence[str | IndicatorSpecSchema | dict[str, Any]],
        price_count: int | None = None,
        interval: str = "1d",
        chart_style: str = "candlestick",
    ) -> str:
        """
        Generate cache key based on security, interval, chart style, and indicators.

        Args:
            security_id: Security identifier
            indicators: Sequence of requested indicators (specs, dicts, or strings)
            price_count: Optional number of price data points
            interval: Chart interval (default '1d')
            chart_style: Chart style (default 'candlestick')

        Returns:
            Cache key string
        """
        digest = self._compute_indicator_digest(indicators)
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

    async def get(
        self,
        security_id: str,
        indicators: Sequence[str | IndicatorSpecSchema | dict[str, Any]],
        price_count: int | None = None,
        interval: str = "1d",
        chart_style: str = "candlestick",
    ) -> Any:
        """
        Get cached indicator data.

        Args:
            security_id: Security identifier
            indicators: Sequence of requested indicators
            price_count: Optional number of price data points
            interval: Candle interval
            chart_style: Chart style

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
        """
        if not indicators or data is None:
            return

        cache_key = self._get_cache_key(
            security_id=security_id,
            indicators=indicators,
            price_count=price_count,
            interval=interval,
            chart_style=chart_style,
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
