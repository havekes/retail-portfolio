"""Endpoint-level response cache for the service-to-service data endpoints.

This is a distinct layer above the gateway-level cache in
:mod:`src.market.cache`: ``CachedMarketGateway`` caches raw provider reads
inside the gateway, while :class:`EndpointResponseCache` caches the unified
JSON responses the data endpoints (T08/T09) return. Both may be active.

Endpoints run on the event loop, so unlike the gateway wrapper this cache is
async-native: it awaits ``redis_manager.client()`` directly instead of using the
synchronous ``_CacheBridge`` (which would block the loop). Every Redis failure
degrades to a live fetch and never propagates.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, time
from typing import Any, TypeVar

from pydantic import BaseModel

from src.config.settings import settings
from src.core.redis import redis_manager
from src.market.cache import (
    _NULL_SENTINEL,
    _canonicalize,
    _canonicalize_datetime,
    _normalize_query,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Readable, scan-friendly prefix so endpoint entries can be invalidated by
# pattern (``market:ep:*``) without touching the gateway-level keys.
_CACHE_KEY_PREFIX = "market:ep"

# data class -> Settings field holding its TTL (seconds). Read at call time so
# a configuration change is honoured without restarting the process.
_TTL_SETTING_FIELDS: dict[str, str] = {
    "prices": "endpoint_ttl_prices_seconds",
    "statements": "endpoint_ttl_statements_seconds",
    "metrics": "endpoint_ttl_metrics_seconds",
    "options": "endpoint_ttl_options_seconds",
    "search": "endpoint_ttl_search_seconds",
}

# Fallback when an endpoint reports a data class without a configured TTL.
_DEFAULT_TTL_SECONDS = 3_600


def _canonicalize_param(value: Any) -> Any:
    """Canonicalize one request parameter for the endpoint cache key.

    ``datetime`` bounds keep full hour/minute precision (via
    :func:`_canonicalize_datetime`) so two intraday windows on the same day
    never collide — for an intraday data class the time range is materially
    part of the request, not noise. The one exception is a midnight
    ``datetime``: it carries no intraday information, so it collapses to its
    calendar date and stays equivalent to the matching daily ``date`` bound.
    Every other value delegates to the shared :func:`_canonicalize`.
    """
    if isinstance(value, datetime):
        if value.time() == time(0, 0):
            return _canonicalize(value)
        return _canonicalize_datetime(value)
    if isinstance(value, dict):
        return {str(key): _canonicalize_param(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_canonicalize_param(item) for item in value]
    return _canonicalize(value)


def _cache_key(data_class: str, endpoint: str, params: Mapping[str, Any]) -> str:
    """Build a deterministic, readable cache key for an endpoint response.

    ``data_class`` and ``endpoint`` stay in the clear for debugging and
    scan-based invalidation; the request parameters are content-hashed so
    equivalent inputs (``date`` vs midnight ``datetime``,
    ``Decimal("10.5")`` vs ``"10.50"``) share one entry while intraday windows
    keep their hour/minute precision.
    """
    canonical = {
        str(name): _canonicalize_param(value) for name, value in params.items()
    }
    query = canonical.get("query")
    if isinstance(query, str):
        canonical["query"] = _normalize_query(query)
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode()).hexdigest()[:40]
    return f"{_CACHE_KEY_PREFIX}:{data_class}:{endpoint}:{digest}"


def _ttl_for(data_class: str) -> int:
    """Resolve the configured TTL for a data class at call time."""
    field = _TTL_SETTING_FIELDS.get(data_class)
    if field is None:
        logger.warning(
            "No endpoint cache TTL configured for data class %r; using %ds",
            data_class,
            _DEFAULT_TTL_SECONDS,
        )
        return _DEFAULT_TTL_SECONDS
    return int(getattr(settings, field))


def _encode_payload(payload: Any) -> str:
    """Serialize an endpoint response for storage in Redis."""
    if payload is None:
        return json.dumps(_NULL_SENTINEL)
    if isinstance(payload, BaseModel):
        return json.dumps(payload.model_dump(mode="json"))
    if isinstance(payload, list):
        return json.dumps(
            [
                item.model_dump(mode="json") if isinstance(item, BaseModel) else item
                for item in payload
            ]
        )
    return json.dumps(payload)


def _decode_payload(payload: str, model: type[BaseModel] | None) -> Any:
    """Deserialize a cached payload, optionally validating it against ``model``.

    Raises on malformed payloads; the caller treats that as a cache miss.
    """
    decoded: Any = json.loads(payload)
    if decoded == _NULL_SENTINEL:
        return None
    if model is None:
        return decoded
    if isinstance(decoded, list):
        return [model.model_validate(item) for item in decoded]
    return model.model_validate(decoded)


class EndpointResponseCache:
    """Async Redis cache for unified data-endpoint responses.

    T08/T09 handlers adopt :meth:`cached_response` for the whole get-or-fetch
    behaviour, or use :meth:`get` / :meth:`set` directly when they need finer
    control. Only successful responses should be cached: the wrapper naturally
    stores just the happy path of ``fetch``, and direct callers must not call
    :meth:`set` after the gateway raised.
    """

    async def get(
        self,
        data_class: str,
        endpoint: str,
        params: Mapping[str, Any],
        *,
        model: type[BaseModel] | None = None,
    ) -> Any | None:
        """Return the cached response, or ``None`` on a miss or Redis error.

        ``model`` optionally validates the decoded payload (each list item or
        the object) into typed values. A payload that fails to decode is logged
        and treated as a miss. A cached ``None`` result also reads back as
        ``None``; use :meth:`cached_response` when the distinction matters.
        """
        hit, value = await self._lookup(_cache_key(data_class, endpoint, params), model)
        return value if hit else None

    async def set(
        self,
        data_class: str,
        endpoint: str,
        params: Mapping[str, Any],
        payload: Any,
        *,
        ttl: int | None = None,
    ) -> None:
        """Store ``payload`` under the endpoint key with the class TTL.

        Never raises: a Redis write failure is logged and the request continues
        to be served live.
        """
        await self._store(
            _cache_key(data_class, endpoint, params), data_class, payload, ttl
        )

    async def cached_response(
        self,
        data_class: str,
        endpoint: str,
        params: Mapping[str, Any],
        fetch: Callable[[], Awaitable[T]],
        *,
        model: type[BaseModel] | None = None,
    ) -> T:
        """Serve an endpoint response from cache, or fetch and cache it.

        On a hit the stored payload is returned (validated when ``model`` is
        given); on a miss ``fetch`` is awaited and its result stored. A fetch
        that raises propagates and is never cached.
        """
        key = _cache_key(data_class, endpoint, params)
        hit, value = await self._lookup(key, model)
        if hit:
            return value
        result = await fetch()
        await self._store(key, data_class, result, None)
        return result

    # -- internals -------------------------------------------------------- #

    async def _lookup(
        self, key: str, model: type[BaseModel] | None
    ) -> tuple[bool, Any]:
        """Return ``(hit, value)``; ``(False, None)`` on a miss or any error."""
        try:
            async with redis_manager.client() as client:
                payload = await client.get(key)
        except Exception as e:  # noqa: BLE001
            logger.warning("Endpoint cache read failed for %s: %s", key, e)
            return False, None

        if payload is None:
            return False, None
        if isinstance(payload, bytes):
            payload = payload.decode()
        try:
            return True, _decode_payload(payload, model)
        except Exception as e:  # noqa: BLE001
            logger.warning("Endpoint cache payload invalid for %s: %s", key, e)
            return False, None

    async def _store(
        self,
        key: str,
        data_class: str,
        payload: Any,
        ttl: int | None,
    ) -> None:
        try:
            effective_ttl = ttl if ttl is not None else _ttl_for(data_class)
            encoded = _encode_payload(payload)
            async with redis_manager.client() as client:
                await client.setex(key, effective_ttl, encoded)
        except Exception as e:  # noqa: BLE001
            logger.warning("Endpoint cache write failed for %s: %s", key, e)


def endpoint_response_cache_factory() -> EndpointResponseCache:
    """Create the endpoint-level response cache (Redis is resolved per call)."""
    return EndpointResponseCache()
