import json
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from redis.exceptions import ConnectionError as RedisConnectionError

from src.config.settings import Settings
from src.core.redis import RedisManager
from src.market.api_types import SecuritySearchResult
from src.market.cache import (
    DEFAULT_SEARCH_CACHE_TTL,
    SecuritySearchCache,
    security_search_cache_factory,
)
from src.observability import bootstrap_observability, reset_observability

EXPECTED_COUNT = 2
CUSTOM_TTL = 86400
OVERRIDE_TTL = 3600
EXPECTED_DEFAULT_TTL = 2_592_000


@pytest.fixture
def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def search_cache(mock_redis: AsyncMock) -> SecuritySearchCache:
    return SecuritySearchCache(redis_client=mock_redis)


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


@pytest.fixture
def sample_search_results() -> list[SecuritySearchResult]:
    return [
        SecuritySearchResult(
            code="AAPL",
            exchange="US",
            name="Apple Inc.",
            currency="USD",
            security_type="Common Stock",
            isin="US0378331005",
            country="USA",
        ),
        SecuritySearchResult(
            code="AAPL.TO",
            exchange="TO",
            name="Apple CDR",
            currency="CAD",
            security_type="CDR",
            isin="CA0378331005",
            country="Canada",
        ),
    ]


# ============================================================================
# 1. Key Normalization
# ============================================================================


def test_normalize_query(search_cache: SecuritySearchCache) -> None:
    assert search_cache._normalize_query("  AAPL  ") == "aapl"  # noqa: SLF001
    assert search_cache._normalize_query("AaPl") == "aapl"  # noqa: SLF001
    assert search_cache._normalize_query("  AAPL   US  ") == "aapl us"  # noqa: SLF001
    assert search_cache._normalize_query("") == ""  # noqa: SLF001
    assert search_cache._normalize_query("   ") == ""  # noqa: SLF001


def test_get_cache_key(search_cache: SecuritySearchCache) -> None:
    assert search_cache._get_cache_key("AAPL") == "market:search:aapl"  # noqa: SLF001
    assert search_cache._get_cache_key("  AAPL   ") == "market:search:aapl"  # noqa: SLF001
    assert search_cache._get_cache_key("AAPL  US") == "market:search:aapl us"  # noqa: SLF001


# ============================================================================
# 2. Cache Hit and Miss
# ============================================================================


@pytest.mark.anyio
async def test_get_empty_or_whitespace_query_returns_none(
    search_cache: SecuritySearchCache,
    mock_redis: AsyncMock,
) -> None:
    assert await search_cache.get("") is None
    assert await search_cache.get("   ") is None
    mock_redis.get.assert_not_called()


@pytest.mark.anyio
async def test_set_empty_or_whitespace_query_is_noop(
    search_cache: SecuritySearchCache,
    mock_redis: AsyncMock,
    sample_search_results: list[SecuritySearchResult],
) -> None:
    await search_cache.set("", sample_search_results)
    await search_cache.set("   ", sample_search_results)
    mock_redis.setex.assert_not_called()


@pytest.mark.anyio
async def test_get_cache_miss_returns_none(
    search_cache: SecuritySearchCache,
    mock_redis: AsyncMock,
) -> None:
    mock_redis.get.return_value = None
    result = await search_cache.get("MSFT")

    assert result is None
    mock_redis.get.assert_awaited_once_with("market:search:msft")


@pytest.mark.anyio
async def test_get_cache_hit_returns_validated_results(
    search_cache: SecuritySearchCache,
    mock_redis: AsyncMock,
    sample_search_results: list[SecuritySearchResult],
) -> None:
    payload = json.dumps([r.model_dump(mode="json") for r in sample_search_results])
    mock_redis.get.return_value = payload

    results = await search_cache.get("  AAPL  ")

    assert results is not None
    assert len(results) == EXPECTED_COUNT
    assert results[0].code == "AAPL"
    assert results[0].exchange == "US"
    assert results[0].currency == "USD"
    assert results[1].code == "AAPL.TO"
    assert results[1].country == "Canada"
    mock_redis.get.assert_awaited_once_with("market:search:aapl")


@pytest.mark.anyio
async def test_cache_key_normalization_symmetry(
    search_cache: SecuritySearchCache,
    mock_redis: AsyncMock,
    sample_search_results: list[SecuritySearchResult],
) -> None:
    await search_cache.set("  SHOP   TO ", sample_search_results)
    mock_redis.setex.assert_awaited_once()
    assert mock_redis.setex.call_args[0][0] == "market:search:shop to"


# ============================================================================
# 3. TTL Verification
# ============================================================================


@pytest.mark.anyio
async def test_set_uses_default_ttl(
    search_cache: SecuritySearchCache,
    mock_redis: AsyncMock,
    sample_search_results: list[SecuritySearchResult],
) -> None:
    assert DEFAULT_SEARCH_CACHE_TTL == EXPECTED_DEFAULT_TTL

    await search_cache.set("AAPL", sample_search_results)

    mock_redis.setex.assert_awaited_once()
    cache_key, ttl, payload = mock_redis.setex.call_args[0]
    assert cache_key == "market:search:aapl"
    assert ttl == DEFAULT_SEARCH_CACHE_TTL
    parsed = json.loads(payload)
    assert len(parsed) == EXPECTED_COUNT


@pytest.mark.anyio
async def test_set_uses_custom_instance_ttl(
    mock_redis: AsyncMock,
    sample_search_results: list[SecuritySearchResult],
) -> None:
    cache = SecuritySearchCache(redis_client=mock_redis, cache_ttl=CUSTOM_TTL)
    await cache.set("AAPL", sample_search_results)

    mock_redis.setex.assert_awaited_once()
    _, ttl, _ = mock_redis.setex.call_args[0]
    assert ttl == CUSTOM_TTL


@pytest.mark.anyio
async def test_set_uses_explicit_ttl_override(
    search_cache: SecuritySearchCache,
    mock_redis: AsyncMock,
    sample_search_results: list[SecuritySearchResult],
) -> None:
    await search_cache.set("AAPL", sample_search_results, ttl=OVERRIDE_TTL)

    mock_redis.setex.assert_awaited_once()
    _, ttl, _ = mock_redis.setex.call_args[0]
    assert ttl == OVERRIDE_TTL


# ============================================================================
# 4. Redis Error Resilience
# ============================================================================


@pytest.mark.anyio
async def test_redis_error_on_get_returns_none_and_logs_warning(
    search_cache: SecuritySearchCache,
    mock_redis: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_redis.get.side_effect = RedisConnectionError("Connection timed out")

    with caplog.at_level(logging.WARNING):
        result = await search_cache.get("AAPL")

    assert result is None
    assert any(
        "Cache get error for query AAPL" in record.message for record in caplog.records
    )


@pytest.mark.anyio
async def test_redis_error_on_set_logs_warning_and_does_not_raise(
    search_cache: SecuritySearchCache,
    mock_redis: AsyncMock,
    sample_search_results: list[SecuritySearchResult],
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_redis.setex.side_effect = RedisConnectionError("Write failure")

    with caplog.at_level(logging.WARNING):
        await search_cache.set("AAPL", sample_search_results)

    assert any(
        "Cache set error for query AAPL" in record.message for record in caplog.records
    )


# ============================================================================
# 5. Corrupted Cache Payload Handling
# ============================================================================


@pytest.mark.anyio
async def test_corrupted_json_payload_returns_none_and_logs_warning(
    search_cache: SecuritySearchCache,
    mock_redis: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_redis.get.return_value = "invalid json {"

    with caplog.at_level(logging.WARNING):
        result = await search_cache.get("AAPL")

    assert result is None
    assert any(
        "Cache get error for query AAPL" in record.message for record in caplog.records
    )


@pytest.mark.anyio
async def test_non_list_json_payload_returns_none_and_logs_warning(
    search_cache: SecuritySearchCache,
    mock_redis: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_redis.get.return_value = json.dumps({"not": "a list"})

    with caplog.at_level(logging.WARNING):
        result = await search_cache.get("AAPL")

    assert result is None
    assert any(
        "Invalid cache payload format for query AAPL: expected list" in record.message
        for record in caplog.records
    )


@pytest.mark.anyio
async def test_corrupted_item_schema_returns_none_and_logs_warning(
    search_cache: SecuritySearchCache,
    mock_redis: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Missing required fields like code, exchange, name, etc.
    mock_redis.get.return_value = json.dumps([{"corrupt_field": "corrupt_value"}])

    with caplog.at_level(logging.WARNING):
        result = await search_cache.get("AAPL")

    assert result is None
    assert any(
        "Cache get error for query AAPL" in record.message for record in caplog.records
    )


# ============================================================================
# 6. RedisManager Integration & Factory
# ============================================================================


@pytest.mark.anyio
async def test_search_cache_with_redis_manager(
    sample_search_results: list[SecuritySearchResult],
) -> None:
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=None)
    mock_client.setex = AsyncMock(return_value=True)

    mock_manager = MagicMock(spec=RedisManager)

    class MockContextManager:
        async def __aenter__(self):
            return mock_client

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    mock_manager.client.return_value = MockContextManager()

    cache = SecuritySearchCache(redis_manager=mock_manager)
    await cache.set("GOOG", sample_search_results)
    mock_client.setex.assert_awaited_once()

    res = await cache.get("GOOG")
    assert res is None
    mock_client.get.assert_awaited_once_with("market:search:goog")


@pytest.mark.anyio
async def test_security_search_cache_factory() -> None:
    cache = await security_search_cache_factory()
    assert isinstance(cache, SecuritySearchCache)
    assert cache._cache_ttl == DEFAULT_SEARCH_CACHE_TTL  # noqa: SLF001
    assert cache._redis_manager is not None  # noqa: SLF001


# ============================================================================
# 7. Wide events: market.cache.accessed
# ============================================================================


@pytest.mark.anyio
async def test_get_cache_miss_emits_wide_event(
    search_cache: SecuritySearchCache,
    mock_redis: AsyncMock,
    span_exporter: InMemorySpanExporter,
) -> None:
    mock_redis.get.return_value = None

    assert await search_cache.get("AAPL") is None

    attributes = _cache_attributes(span_exporter)
    assert attributes["event.name"] == "market.cache.accessed"
    assert attributes["cache_kind"] == "security_search"
    assert attributes["key_class"] == "security_search"
    assert attributes["outcome"] == "miss"
    assert attributes["ttl_seconds"] == DEFAULT_SEARCH_CACHE_TTL
    assert "error_slug" not in attributes
    _assert_raw_key_absent(span_exporter, "market:search:aapl")


@pytest.mark.anyio
async def test_get_cache_hit_emits_wide_event(
    search_cache: SecuritySearchCache,
    mock_redis: AsyncMock,
    sample_search_results: list[SecuritySearchResult],
    span_exporter: InMemorySpanExporter,
) -> None:
    mock_redis.get.return_value = json.dumps(
        [r.model_dump(mode="json") for r in sample_search_results]
    )

    results = await search_cache.get("  AAPL  ")

    assert results is not None
    assert len(results) == EXPECTED_COUNT
    attributes = _cache_attributes(span_exporter)
    assert attributes["cache_kind"] == "security_search"
    assert attributes["key_class"] == "security_search"
    assert attributes["outcome"] == "hit"
    assert attributes["ttl_seconds"] == DEFAULT_SEARCH_CACHE_TTL
    _assert_raw_key_absent(span_exporter, "market:search:aapl")


@pytest.mark.anyio
async def test_cached_empty_result_emits_negative_outcome(
    search_cache: SecuritySearchCache,
    mock_redis: AsyncMock,
    span_exporter: InMemorySpanExporter,
) -> None:
    mock_redis.get.return_value = json.dumps([])

    assert await search_cache.get("AAPL") == []

    attributes = _cache_attributes(span_exporter)
    assert attributes["outcome"] == "negative"
    assert attributes["cache_kind"] == "security_search"
    assert attributes["key_class"] == "security_search"
    _assert_raw_key_absent(span_exporter, "market:search:aapl")


@pytest.mark.anyio
async def test_redis_error_emits_miss_with_error_slug(
    search_cache: SecuritySearchCache,
    mock_redis: AsyncMock,
    span_exporter: InMemorySpanExporter,
) -> None:
    mock_redis.get.side_effect = RedisConnectionError("Connection timed out")

    assert await search_cache.get("AAPL") is None

    attributes = _cache_attributes(span_exporter)
    assert attributes["outcome"] == "miss"
    assert attributes["cache_kind"] == "security_search"
    assert attributes["key_class"] == "security_search"
    assert attributes["error_slug"] == "cache_error"


@pytest.mark.anyio
async def test_set_emits_write_event_with_default_ttl(
    search_cache: SecuritySearchCache,
    mock_redis: AsyncMock,
    sample_search_results: list[SecuritySearchResult],
    span_exporter: InMemorySpanExporter,
) -> None:
    await search_cache.set("AAPL", sample_search_results)

    attributes = _cache_attributes(span_exporter)
    assert attributes["cache_kind"] == "security_search"
    assert attributes["key_class"] == "security_search"
    assert attributes["outcome"] == "write"
    assert attributes["ttl_seconds"] == DEFAULT_SEARCH_CACHE_TTL
    _assert_raw_key_absent(span_exporter, "market:search:aapl")


@pytest.mark.anyio
async def test_set_emits_write_event_with_override_ttl(
    search_cache: SecuritySearchCache,
    mock_redis: AsyncMock,
    sample_search_results: list[SecuritySearchResult],
    span_exporter: InMemorySpanExporter,
) -> None:
    await search_cache.set("AAPL", sample_search_results, ttl=OVERRIDE_TTL)

    attributes = _cache_attributes(span_exporter)
    assert attributes["outcome"] == "write"
    assert attributes["ttl_seconds"] == OVERRIDE_TTL


@pytest.mark.anyio
async def test_no_event_when_query_is_empty(
    search_cache: SecuritySearchCache,
    mock_redis: AsyncMock,
    span_exporter: InMemorySpanExporter,
) -> None:
    assert await search_cache.get("   ") is None

    assert span_exporter.get_finished_spans() == ()
