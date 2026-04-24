import hashlib
import json
import logging
from datetime import timedelta
from typing import Any

import redis.asyncio as aioredis
from redis.asyncio.client import Redis

from src.config.settings import settings

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

    def _get_cache_key(
        self, security_id: str, indicators: list[str], price_count: int
    ) -> str:
        """
        Generate cache key based on security, indicators, and data range.

        Args:
            security_id: Security identifier
            indicators: List of requested indicator types
            price_count: Number of price data points (to invalidate on new data)

        Returns:
            Cache key string
        """
        key_parts = [
            "indicators",
            security_id,
            ",".join(sorted(indicators)),
            str(price_count),
        ]
        key_string = "|".join(key_parts)
        digest = hashlib.md5(key_string.encode(), usedforsecurity=False).hexdigest()
        return f"indicators:{digest}"

    async def get(
        self, security_id: str, indicators: list[str], price_count: int
    ) -> Any:
        """
        Get cached indicator data.

        Args:
            security_id: Security identifier
            indicators: List of requested indicator types
            price_count: Number of price data points

        Returns:
            Cached indicator data or None if not found
        """
        if not indicators:
            return None

        cache_key = self._get_cache_key(security_id, indicators, price_count)

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

    async def set(
        self,
        security_id: str,
        indicators: list[str],
        price_count: int,
        data: dict,
    ) -> None:
        """
        Cache indicator data.

        Args:
            security_id: Security identifier
            indicators: List of requested indicator types
            price_count: Number of price data points
            data: Indicator data to cache
        """
        if not indicators:
            return

        cache_key = self._get_cache_key(security_id, indicators, price_count)

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


async def indicator_cache_factory() -> IndicatorCache:
    """Factory function to create indicator cache instance."""
    redis_client = aioredis.from_url(
        settings.redis_url, encoding="utf-8", decode_responses=False
    )
    return IndicatorCache(redis_client)
