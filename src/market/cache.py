import hashlib
import json
import logging
from collections.abc import Sequence
from typing import Any

import redis.asyncio as aioredis
from pydantic import BaseModel
from redis.asyncio.client import Redis

from src.config.settings import settings
from src.market.schema import IndicatorSpecSchema

logger = logging.getLogger(__name__)


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
