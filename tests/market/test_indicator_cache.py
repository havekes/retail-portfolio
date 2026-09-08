# ruff: noqa: PLR2004, SLF001
import fnmatch
from typing import cast
from unittest.mock import AsyncMock

import pytest
from redis.asyncio.client import Redis

from src.market.cache import IndicatorCache
from src.market.schema import IndicatorSpecSchema


class FakeRedis:
    def __init__(self):
        self.storage: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.storage.get(key)

    async def setex(self, key: str, time: int, value: str) -> None:  # noqa: ARG002
        self.storage[key] = value

    async def scan(
        self,
        cursor: int = 0,  # noqa: ARG002
        match: str | None = None,
        count: int | None = None,  # noqa: ARG002
    ) -> tuple[int, list[str]]:
        matched = [
            key for key in self.storage if match is None or fnmatch.fnmatch(key, match)
        ]
        return 0, matched

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for k in keys:
            if k in self.storage:
                del self.storage[k]
                deleted += 1
        return deleted


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def indicator_cache(fake_redis: FakeRedis) -> IndicatorCache:
    return IndicatorCache(redis_client=cast("Redis", fake_redis), cache_ttl=3600)


def test_get_cache_key_structure(indicator_cache: IndicatorCache):
    spec = IndicatorSpecSchema(id="SMA_50", type="SMA", period=50)
    key = indicator_cache._get_cache_key(
        security_id="sec-1",
        indicators=[spec],
        interval="1h",
        chart_style="heikin_ashi",
    )
    parts = key.split(":")
    assert len(parts) == 5
    assert parts[0] == "indicators"
    assert parts[1] == "sec-1"
    assert parts[2] == "1h"
    assert parts[3] == "heikin_ashi"
    assert len(parts[4]) == 64  # sha256 hex digest length


def test_get_cache_key_with_price_count(indicator_cache: IndicatorCache):
    key = indicator_cache._get_cache_key(
        security_id="sec-1",
        indicators=["ma_50_day"],
        price_count=100,
        interval="1d",
        chart_style="candlestick",
    )
    parts = key.split(":")
    assert len(parts) == 6
    assert parts[5] == "100"


def test_get_cache_key_canonical_ordering(indicator_cache: IndicatorCache):
    spec_a = IndicatorSpecSchema(id="SMA_20", type="SMA", period=20)
    spec_b = IndicatorSpecSchema(id="RSI_14", type="RSI", period=14)

    key1 = indicator_cache._get_cache_key(
        security_id="sec-1",
        indicators=[spec_a, spec_b],
    )
    key2 = indicator_cache._get_cache_key(
        security_id="sec-1",
        indicators=[spec_b, spec_a],
    )
    assert key1 == key2


def test_get_cache_key_differentiates_interval_and_style(
    indicator_cache: IndicatorCache,
):
    spec = IndicatorSpecSchema(type="SMA", period=20)

    key_1d = indicator_cache._get_cache_key(
        security_id="sec-1", indicators=[spec], interval="1d"
    )
    key_1h = indicator_cache._get_cache_key(
        security_id="sec-1", indicators=[spec], interval="1h"
    )
    key_ha = indicator_cache._get_cache_key(
        security_id="sec-1",
        indicators=[spec],
        interval="1d",
        chart_style="heikin_ashi",
    )

    assert key_1d != key_1h
    assert key_1d != key_ha


@pytest.mark.anyio
async def test_cache_miss_returns_none(indicator_cache: IndicatorCache):
    result = await indicator_cache.get(
        security_id="sec-1",
        indicators=[IndicatorSpecSchema(type="SMA", period=20)],
        interval="1d",
    )
    assert result is None


@pytest.mark.anyio
async def test_cache_hit_returns_cached_data(indicator_cache: IndicatorCache):
    spec = IndicatorSpecSchema(id="SMA_20", type="SMA", period=20)
    data = {"indicators": {"SMA_20": [{"time": "2026-01-01", "value": 100.0}]}}

    await indicator_cache.set(
        security_id="sec-1",
        indicators=[spec],
        interval="1d",
        chart_style="candlestick",
        data=data,
    )

    cached = await indicator_cache.get(
        security_id="sec-1",
        indicators=[spec],
        interval="1d",
        chart_style="candlestick",
    )
    assert cached == data


@pytest.mark.anyio
async def test_empty_indicators_noop(indicator_cache: IndicatorCache):
    assert await indicator_cache.get("sec-1", []) is None
    await indicator_cache.set("sec-1", [], data={"foo": "bar"})


@pytest.mark.anyio
async def test_cache_redis_error_handled_gracefully():
    broken_redis = AsyncMock()
    broken_redis.get.side_effect = RuntimeError("Redis down")
    cache = IndicatorCache(redis_client=broken_redis)

    result = await cache.get("sec-1", [IndicatorSpecSchema(type="SMA", period=20)])
    assert result is None


@pytest.mark.anyio
async def test_invalidate_security(indicator_cache: IndicatorCache):
    spec = IndicatorSpecSchema(type="SMA", period=20)
    data = {"indicators": {}}

    await indicator_cache.set(
        security_id="sec-1", indicators=[spec], interval="1d", data=data
    )
    await indicator_cache.set(
        security_id="sec-2", indicators=[spec], interval="1d", data=data
    )

    await indicator_cache.invalidate_security("sec-1")

    assert await indicator_cache.get("sec-1", [spec], interval="1d") is None
    assert await indicator_cache.get("sec-2", [spec], interval="1d") == data


@pytest.mark.anyio
async def test_flush_all(indicator_cache: IndicatorCache):
    spec = IndicatorSpecSchema(type="SMA", period=20)
    data = {"indicators": {}}

    await indicator_cache.set(
        security_id="sec-1", indicators=[spec], interval="1d", data=data
    )
    await indicator_cache.flush_all()
    assert await indicator_cache.get("sec-1", [spec], interval="1d") is None
