"""In-memory Redis fake so tests never depend on a running Redis service.

The application talks to Redis through the ``src.core.redis.redis_manager``
singleton (auth token denylist, 2FA/passkey challenges, security search cache,
account sync status). The autouse ``fake_redis_manager`` fixture replaces that
singleton's client with an in-memory fake, so the whole suite runs without a
Redis server or DNS. Tests that need to inspect stored keys can request the
``mock_redis_storage`` fixture.
"""

from __future__ import annotations

import asyncio
import builtins
import contextlib
import fnmatch
from collections.abc import AsyncIterator
from typing import Any

import pytest


class FakePubSub:
    """In-memory pub/sub stand-in for ``redis.asyncio.client.PubSub``.

    Subscriptions are registered on the owning :class:`FakeRedis`, which fans
    published messages out to every subscriber's queue. This lets tests drive a
    real ``ConnectionManager`` listener without a Redis server.
    """

    def __init__(self, redis: FakeRedis) -> None:
        self._redis = redis
        self._channels: set[str] = set()
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.closed = False

    async def subscribe(self, *channels: str) -> None:
        for channel in channels:
            self._channels.add(channel)
            self._redis._subscribers.setdefault(channel, set()).add(self)

    async def unsubscribe(self, *channels: str) -> None:
        targets = set(channels) if channels else set(self._channels)
        for channel in targets:
            self._channels.discard(channel)
            subscribers = self._redis._subscribers.get(channel)
            if subscribers is not None:
                subscribers.discard(self)
                if not subscribers:
                    self._redis._subscribers.pop(channel, None)

    async def listen(self) -> AsyncIterator[dict[str, Any]]:
        while True:
            yield await self._queue.get()

    async def aclose(self) -> None:
        self.closed = True
        await self.unsubscribe()

    def _deliver(self, channel: str, data: str) -> None:
        self._queue.put_nowait({"type": "message", "channel": channel, "data": data})


class FakeRedis:
    """Minimal async Redis stand-in backed by a plain dict."""

    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self._sets: dict[str, set[str]] = {}
        self._subscribers: dict[str, set[FakePubSub]] = {}

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def set(
        self,
        key: str,
        value: str,
        *,
        ex: int | None = None,
        nx: bool = False,
        **_kwargs: object,
    ) -> bool | None:
        if nx and key in self.data:
            return None
        self.data[key] = value
        return True

    async def setex(self, key: str, ttl: int, value: str) -> bool:
        self.data[key] = value
        return True

    async def getdel(self, key: str) -> str | None:
        return self.data.pop(key, None)

    async def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if self.data.pop(key, None) is not None:
                removed += 1
            if self._sets.pop(key, None) is not None:
                removed += 1
        return removed

    async def incr(self, key: str) -> int:
        value = int(self.data.get(key, 0)) + 1
        self.data[key] = str(value)
        return value

    async def expire(self, key: str, ttl: int) -> bool:
        return key in self.data or key in self._sets

    async def scan(
        self,
        cursor: int = 0,
        match: str | None = None,
        count: int | None = None,
    ) -> tuple[int, list[str]]:
        keys = [key for key in self.data if match is None or fnmatch.fnmatch(key, match)]
        return 0, keys

    async def ping(self) -> bool:
        return True

    async def publish(self, channel: str, message: str) -> int:
        subscribers = tuple(self._subscribers.get(channel, ()))
        for subscriber in subscribers:
            subscriber._deliver(channel, message)
        return len(subscribers)

    def pubsub(self) -> FakePubSub:
        return FakePubSub(self)

    async def sadd(self, key: str, *members: str) -> int:
        bucket = self._sets.setdefault(key, set())
        before = len(bucket)
        bucket.update(members)
        return len(bucket) - before

    async def srem(self, key: str, *members: str) -> int:
        bucket = self._sets.get(key)
        if not bucket:
            return 0
        removed = 0
        for member in members:
            if member in bucket:
                bucket.remove(member)
                removed += 1
        return removed

    async def smembers(self, key: str) -> builtins.set[str]:
        return set(self._sets.get(key, set()))

    async def aclose(self) -> None:
        subscribers = {s for group in self._subscribers.values() for s in group}
        for subscriber in subscribers:
            await subscriber.aclose()
        self._subscribers.clear()


class FakeRedisManager:
    """Drop-in replacement for ``src.core.redis.RedisManager``."""

    def __init__(self, redis_client: FakeRedis | None = None) -> None:
        self.redis = redis_client if redis_client is not None else FakeRedis()

    @contextlib.asynccontextmanager
    async def client(self) -> AsyncIterator[FakeRedis]:
        yield self.redis


@pytest.fixture(autouse=True)
def fake_redis_manager(monkeypatch: pytest.MonkeyPatch) -> FakeRedisManager:
    """Replace the shared Redis singleton's client for every test.

    All modules (auth api/service, market cache, integration sync status)
    import the same ``src.core.redis.redis_manager`` object, so patching its
    instance attribute covers every call site. Tests that exercise the real
    ``RedisManager`` instantiate their own instance and are unaffected.
    """
    manager = FakeRedisManager()

    @contextlib.asynccontextmanager
    async def _fake_client() -> AsyncIterator[FakeRedis]:
        yield manager.redis

    monkeypatch.setattr("src.core.redis.redis_manager.client", _fake_client)
    monkeypatch.setattr("src.auth.api.default_redis_manager.client", _fake_client)
    monkeypatch.setattr("src.auth.service.default_redis_manager.client", _fake_client)
    return manager


@pytest.fixture
def mock_redis_storage(fake_redis_manager: FakeRedisManager) -> FakeRedis:
    """Expose the in-memory Redis backing store for assertions."""
    return fake_redis_manager.redis
