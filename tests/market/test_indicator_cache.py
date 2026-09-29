# ruff: noqa: PLR2004, SLF001
import fnmatch
import json
from datetime import date, datetime
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from redis.asyncio.client import Redis

from src.config.settings import Settings
from src.market.cache import IndicatorCache
from src.market.schema import IndicatorSpecSchema
from src.observability import bootstrap_observability, reset_observability


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


@pytest.fixture(autouse=True)
def _cleanup_observability():
    yield
    reset_observability()


@pytest.fixture
def span_exporter() -> InMemorySpanExporter:
    exporter = InMemorySpanExporter()
    bootstrap_observability(
        service_name="backend",
        settings=Settings(
            environment="test",
            deploy_id="deploy-abc123",
            service_version="1.2.3",
        ),
        span_processor=SimpleSpanProcessor(exporter),
    )
    return exporter


def _cache_attributes(exporter: InMemorySpanExporter) -> dict[str, Any]:
    spans = [
        span
        for span in exporter.get_finished_spans()
        if span.name == "market.cache.accessed"
    ]
    assert len(spans) == 1, f"expected one cache event, got {len(spans)}"
    attributes = spans[0].attributes
    assert attributes is not None
    return dict(attributes)


def _assert_raw_key_absent(exporter: InMemorySpanExporter, raw_key: str) -> None:
    for span in exporter.get_finished_spans():
        for name, value in (span.attributes or {}).items():
            assert raw_key not in str(name)
            assert raw_key not in str(value)


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


def test_get_cache_key_includes_date_window(indicator_cache: IndicatorCache):
    spec = IndicatorSpecSchema(type="SMA", period=20)

    key_no_window = indicator_cache._get_cache_key(
        security_id="sec-1", indicators=[spec]
    )
    key_jan = indicator_cache._get_cache_key(
        security_id="sec-1",
        indicators=[spec],
        from_date=date(2026, 1, 1),
        to_date=date(2026, 1, 31),
    )
    key_jan_again = indicator_cache._get_cache_key(
        security_id="sec-1",
        indicators=[spec],
        from_date=date(2026, 1, 1),
        to_date=date(2026, 1, 31),
    )
    key_feb = indicator_cache._get_cache_key(
        security_id="sec-1",
        indicators=[spec],
        from_date=date(2026, 2, 1),
        to_date=date(2026, 2, 28),
    )

    assert key_jan == key_jan_again
    assert key_jan != key_no_window
    assert key_jan != key_feb


def test_get_cache_key_equivalent_date_and_datetime(indicator_cache: IndicatorCache):
    spec = IndicatorSpecSchema(type="SMA", period=20)

    key_date = indicator_cache._get_cache_key(
        security_id="sec-1",
        indicators=[spec],
        from_date=date(2026, 1, 1),
        to_date=date(2026, 1, 31),
    )
    key_datetime = indicator_cache._get_cache_key(
        security_id="sec-1",
        indicators=[spec],
        from_date=datetime(2026, 1, 1, 9, 30),
        to_date=datetime(2026, 1, 31, 16, 0),
    )

    assert key_date == key_datetime


@pytest.mark.anyio
async def test_cache_window_isolation(indicator_cache: IndicatorCache):
    spec = IndicatorSpecSchema(type="SMA", period=20)
    data_jan = {"indicators": {"SMA": [{"time": "2026-01-31", "value": 1.0}]}}
    data_feb = {"indicators": {"SMA": [{"time": "2026-02-28", "value": 2.0}]}}

    await indicator_cache.set(
        security_id="sec-1",
        indicators=[spec],
        interval="1d",
        from_date=date(2026, 1, 1),
        to_date=date(2026, 1, 31),
        data=data_jan,
    )
    await indicator_cache.set(
        security_id="sec-1",
        indicators=[spec],
        interval="1d",
        from_date=date(2026, 2, 1),
        to_date=date(2026, 2, 28),
        data=data_feb,
    )

    assert (
        await indicator_cache.get(
            security_id="sec-1",
            indicators=[spec],
            interval="1d",
            from_date=date(2026, 1, 1),
            to_date=date(2026, 1, 31),
        )
        == data_jan
    )
    assert (
        await indicator_cache.get(
            security_id="sec-1",
            indicators=[spec],
            interval="1d",
            from_date=date(2026, 2, 1),
            to_date=date(2026, 2, 28),
        )
        == data_feb
    )
    assert (
        await indicator_cache.get(
            security_id="sec-1",
            indicators=[spec],
            interval="1d",
            from_date=date(2026, 3, 1),
            to_date=date(2026, 3, 31),
        )
        is None
    )


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


# ============================================================================
# Wide events: market.cache.accessed
# ============================================================================


@pytest.mark.anyio
async def test_cache_miss_emits_wide_event(
    indicator_cache: IndicatorCache,
    fake_redis: FakeRedis,
    span_exporter: InMemorySpanExporter,
):
    spec = IndicatorSpecSchema(type="SMA", period=20)

    assert await indicator_cache.get("sec-1", [spec], interval="1d") is None

    attributes = _cache_attributes(span_exporter)
    assert attributes["event.name"] == "market.cache.accessed"
    assert attributes["cache_kind"] == "indicator"
    assert attributes["key_class"] == "indicator"
    assert attributes["outcome"] == "miss"
    assert attributes["ttl_seconds"] == 3600
    assert "error_slug" not in attributes

    raw_key = indicator_cache._get_cache_key(security_id="sec-1", indicators=[spec])
    _assert_raw_key_absent(span_exporter, raw_key)
    assert fake_redis.storage == {}


@pytest.mark.anyio
async def test_cache_hit_emits_wide_event(
    indicator_cache: IndicatorCache,
    fake_redis: FakeRedis,
    span_exporter: InMemorySpanExporter,
):
    spec = IndicatorSpecSchema(id="SMA_20", type="SMA", period=20)
    data = {"indicators": {"SMA_20": [{"time": "2026-01-01", "value": 100.0}]}}
    raw_key = indicator_cache._get_cache_key(
        security_id="sec-1", indicators=[spec], interval="1d"
    )
    fake_redis.storage[raw_key] = json.dumps(data)

    assert await indicator_cache.get("sec-1", [spec], interval="1d") == data

    attributes = _cache_attributes(span_exporter)
    assert attributes["cache_kind"] == "indicator"
    assert attributes["key_class"] == "indicator"
    assert attributes["outcome"] == "hit"
    assert attributes["ttl_seconds"] == 3600
    _assert_raw_key_absent(span_exporter, raw_key)


@pytest.mark.anyio
async def test_cached_empty_payload_emits_negative_outcome(
    indicator_cache: IndicatorCache,
    fake_redis: FakeRedis,
    span_exporter: InMemorySpanExporter,
):
    spec = IndicatorSpecSchema(type="SMA", period=20)
    raw_key = indicator_cache._get_cache_key(security_id="sec-1", indicators=[spec])
    fake_redis.storage[raw_key] = json.dumps({})

    assert await indicator_cache.get("sec-1", [spec], interval="1d") == {}

    attributes = _cache_attributes(span_exporter)
    assert attributes["outcome"] == "negative"
    assert attributes["cache_kind"] == "indicator"
    assert attributes["key_class"] == "indicator"
    _assert_raw_key_absent(span_exporter, raw_key)


@pytest.mark.anyio
async def test_cache_write_emits_wide_event(
    indicator_cache: IndicatorCache,
    span_exporter: InMemorySpanExporter,
):
    spec = IndicatorSpecSchema(type="SMA", period=20)

    await indicator_cache.set(
        security_id="sec-1",
        indicators=[spec],
        interval="1d",
        data={"indicators": {}},
    )

    attributes = _cache_attributes(span_exporter)
    assert attributes["cache_kind"] == "indicator"
    assert attributes["key_class"] == "indicator"
    assert attributes["outcome"] == "write"
    assert attributes["ttl_seconds"] == 3600

    raw_key = indicator_cache._get_cache_key(
        security_id="sec-1", indicators=[spec], interval="1d"
    )
    _assert_raw_key_absent(span_exporter, raw_key)


@pytest.mark.anyio
async def test_cache_redis_error_emits_miss_with_error_slug(
    span_exporter: InMemorySpanExporter,
):
    broken_redis = AsyncMock()
    broken_redis.get.side_effect = RuntimeError("Redis down")
    cache = IndicatorCache(redis_client=broken_redis)

    assert await cache.get("sec-1", [IndicatorSpecSchema(type="SMA", period=20)]) is None

    attributes = _cache_attributes(span_exporter)
    assert attributes["outcome"] == "miss"
    assert attributes["cache_kind"] == "indicator"
    assert attributes["key_class"] == "indicator"
    assert attributes["error_slug"] == "cache_error"


@pytest.mark.anyio
async def test_no_event_when_no_cache_access_happens(
    indicator_cache: IndicatorCache,
    span_exporter: InMemorySpanExporter,
):
    assert await indicator_cache.get("sec-1", []) is None
    await indicator_cache.set("sec-1", [], data={"foo": "bar"})

    assert span_exporter.get_finished_spans() == ()
