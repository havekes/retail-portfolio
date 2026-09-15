"""In-memory Redis fake so tests never depend on a running Redis service.

The application talks to Redis through the ``src.core.redis.redis_manager``
singleton (auth token denylist, 2FA/passkey challenges, security search cache,
account sync status). The autouse ``fake_redis_manager`` fixture replaces that
singleton's client with an in-memory fake, so the whole suite runs without a
Redis server or DNS. Tests that need to inspect stored keys can request the
``mock_redis_storage`` fixture.
"""

from __future__ import annotations

import builtins
import contextlib
import fnmatch
from collections.abc import AsyncIterator

import pytest


class FakeRedis:
    """Minimal async Redis stand-in backed by a plain dict."""

    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self._sets: dict[str, set[str]] = {}

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
        return 0

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
        return None


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
