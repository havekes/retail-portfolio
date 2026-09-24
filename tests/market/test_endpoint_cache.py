"""Offline tests for the endpoint-level response cache.

Everything runs against the autouse in-memory ``fake_redis_manager`` fixture —
no Redis server, no network. Async tests use ``@pytest.mark.anyio`` so the
cache is exercised on a running event loop, exactly as the T08/T09 endpoints
will use it.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
import svcs
from redis.exceptions import ConnectionError as RedisConnectionError

from src.config.services import register_market_stub_services
from src.config.settings import settings
from src.market import register_market_services
from src.market.api_types import HistoricalPrice
from src.market.endpoint_cache import (
    EndpointResponseCache,
    _cache_key,
    endpoint_response_cache_factory,
)
from tests.fixtures.redis import FakeRedis

PRICES_TTL = 3_600
STATEMENTS_TTL = 86_400
METRICS_TTL = 86_400
OPTIONS_TTL = 1_800
OVERRIDE_TTL = 5

PRICE_PARAMS: dict[str, Any] = {
    "symbol": "AAPL",
    "from_date": date(2024, 1, 2),
    "to_date": date(2024, 1, 5),
}


class FakeGateway:
    """Async fetch stub that counts invocations and returns a fixed result."""

    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls = 0

    async def fetch(self) -> Any:
        self.calls += 1
        return self.result


@pytest.fixture
def cache() -> EndpointResponseCache:
    return EndpointResponseCache()


def _sample_prices() -> list[HistoricalPrice]:
    return [
        HistoricalPrice(
            security_id=uuid4(),
            date=date(2024, 1, 2),
            open=Decimal("10.00"),
            high=Decimal("11.00"),
            low=Decimal("9.50"),
            close=Decimal("10.50"),
            adjusted_close=Decimal("10.50"),
            volume=1000,
        )
    ]


def _install_recording_setex(
    monkeypatch: pytest.MonkeyPatch, storage: FakeRedis
) -> list[tuple[str, int]]:
    recorded: list[tuple[str, int]] = []
    original = storage.setex

    async def recording_setex(key: str, ttl: int, value: str) -> bool:
        recorded.append((key, ttl))
        return await original(key, ttl, value)

    monkeypatch.setattr(storage, "setex", recording_setex)
    return recorded


def _endpoint_keys(storage: FakeRedis) -> list[str]:
    return sorted(key for key in storage.data if key.startswith("market:ep:"))


# --------------------------------------------------------------------------- #
# AC1: a cache hit serves the stored response without re-invoking the gateway.
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_cache_hit_avoids_refetch(
    cache: EndpointResponseCache, mock_redis_storage: FakeRedis
) -> None:
    gateway = FakeGateway({"symbol": "AAPL", "prices": [1, 2, 3]})

    first = await cache.cached_response("prices", "daily", PRICE_PARAMS, gateway.fetch)
    second = await cache.cached_response("prices", "daily", PRICE_PARAMS, gateway.fetch)

    assert first == second == {"symbol": "AAPL", "prices": [1, 2, 3]}
    assert gateway.calls == 1
    assert len(_endpoint_keys(mock_redis_storage)) == 1


@pytest.mark.anyio
async def test_get_and_set_round_trip_raw_json(
    cache: EndpointResponseCache, mock_redis_storage: FakeRedis
) -> None:
    payload = {"symbol": "AAPL", "prices": [{"close": "10.50"}]}

    assert await cache.get("prices", "daily", PRICE_PARAMS) is None

    await cache.set("prices", "daily", PRICE_PARAMS, payload)

    assert await cache.get("prices", "daily", PRICE_PARAMS) == payload


# --------------------------------------------------------------------------- #
# AC2: keys differ by data class/endpoint/params; equivalent inputs share one.
# --------------------------------------------------------------------------- #


def test_key_differs_by_data_class() -> None:
    prices = _cache_key("prices", "daily", PRICE_PARAMS)
    statements = _cache_key("statements", "daily", PRICE_PARAMS)

    assert prices != statements
    assert prices.startswith("market:ep:prices:daily:")
    assert statements.startswith("market:ep:statements:daily:")


def test_key_differs_by_endpoint() -> None:
    daily = _cache_key("prices", "daily", PRICE_PARAMS)
    intraday = _cache_key("prices", "intraday", PRICE_PARAMS)

    assert daily != intraday


def test_key_differs_by_params() -> None:
    base = _cache_key("prices", "daily", PRICE_PARAMS)
    other = _cache_key("prices", "daily", {**PRICE_PARAMS, "symbol": "MSFT"})
    other_window = _cache_key(
        "prices", "daily", {**PRICE_PARAMS, "to_date": date(2024, 2, 5)}
    )

    assert base != other
    assert base != other_window


def test_key_is_order_independent() -> None:
    reordered = {
        "to_date": PRICE_PARAMS["to_date"],
        "from_date": PRICE_PARAMS["from_date"],
        "symbol": PRICE_PARAMS["symbol"],
    }

    assert _cache_key("prices", "daily", PRICE_PARAMS) == _cache_key(
        "prices", "daily", reordered
    )


def test_equivalent_date_and_datetime_share_a_key() -> None:
    as_dates = _cache_key("prices", "daily", PRICE_PARAMS)
    as_midnight_datetimes = _cache_key(
        "prices",
        "daily",
        {
            "symbol": "AAPL",
            "from_date": datetime(2024, 1, 2, 0, 0),  # noqa: DTZ001
            "to_date": datetime(2024, 1, 5, 0, 0),  # noqa: DTZ001
        },
    )

    assert as_dates == as_midnight_datetimes


def test_distinct_intraday_windows_on_same_day_have_distinct_keys() -> None:
    morning = _cache_key(
        "prices",
        "intraday",
        {
            "symbol": "AAPL",
            "from_datetime": datetime(2024, 1, 2, 9, 30),  # noqa: DTZ001
            "to_datetime": datetime(2024, 1, 2, 12, 0),  # noqa: DTZ001
        },
    )
    afternoon = _cache_key(
        "prices",
        "intraday",
        {
            "symbol": "AAPL",
            "from_datetime": datetime(2024, 1, 2, 13, 0),  # noqa: DTZ001
            "to_datetime": datetime(2024, 1, 2, 16, 0),  # noqa: DTZ001
        },
    )
    calendar_day = _cache_key(
        "prices",
        "intraday",
        {
            "symbol": "AAPL",
            "from_datetime": date(2024, 1, 2),
            "to_datetime": date(2024, 1, 2),
        },
    )

    assert morning != afternoon
    # A non-midnight intraday bound must not collapse onto the calendar date.
    assert morning != calendar_day
    assert afternoon != calendar_day


def test_equivalent_decimal_strike_bounds_share_a_key() -> None:
    first = _cache_key("options", "chain", {"symbol": "AAPL", "strike_min": Decimal("10.50")})
    second = _cache_key("options", "chain", {"symbol": "AAPL", "strike_min": Decimal("10.5")})

    assert first == second


def test_query_param_is_normalized() -> None:
    assert _cache_key("metrics", "lookup", {"query": "  AAPL  "}) == _cache_key(
        "metrics", "lookup", {"query": "aapl"}
    )


@pytest.mark.anyio
async def test_different_params_do_not_share_an_entry(
    cache: EndpointResponseCache, mock_redis_storage: FakeRedis
) -> None:
    gateway = FakeGateway({"symbol": "AAPL"})

    await cache.cached_response("prices", "daily", PRICE_PARAMS, gateway.fetch)
    await cache.cached_response(
        "prices", "daily", {**PRICE_PARAMS, "symbol": "MSFT"}, gateway.fetch
    )

    assert gateway.calls == 2
    assert len(_endpoint_keys(mock_redis_storage)) == 2


# --------------------------------------------------------------------------- #
# AC3: per-data-class TTLs are applied and configurable.
# --------------------------------------------------------------------------- #


def test_default_ttls_are_sane() -> None:
    assert settings.endpoint_ttl_prices_seconds == PRICES_TTL
    assert settings.endpoint_ttl_statements_seconds == STATEMENTS_TTL
    assert settings.endpoint_ttl_metrics_seconds == METRICS_TTL
    assert settings.endpoint_ttl_options_seconds == OPTIONS_TTL


@pytest.mark.anyio
async def test_per_data_class_ttls_are_applied(
    cache: EndpointResponseCache,
    mock_redis_storage: FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded = _install_recording_setex(monkeypatch, mock_redis_storage)

    await cache.set("prices", "daily", PRICE_PARAMS, {"a": 1})
    await cache.set("statements", "income", {"symbol": "AAPL"}, {"a": 2})
    await cache.set("metrics", "key", {"symbol": "AAPL"}, {"a": 3})
    await cache.set("options", "chain", {"symbol": "AAPL"}, {"a": 4})

    assert [ttl for _, ttl in recorded] == [
        PRICES_TTL,
        STATEMENTS_TTL,
        METRICS_TTL,
        OPTIONS_TTL,
    ]
    assert all(key.startswith("market:ep:") for key, _ in recorded)


@pytest.mark.anyio
async def test_ttl_is_read_from_settings_at_call_time(
    cache: EndpointResponseCache,
    mock_redis_storage: FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded = _install_recording_setex(monkeypatch, mock_redis_storage)
    monkeypatch.setattr(settings, "endpoint_ttl_options_seconds", OVERRIDE_TTL)

    await cache.set("options", "chain", {"symbol": "AAPL"}, {"a": 1})

    assert [ttl for _, ttl in recorded] == [OVERRIDE_TTL]


@pytest.mark.anyio
async def test_explicit_ttl_overrides_the_class_default(
    cache: EndpointResponseCache,
    mock_redis_storage: FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded = _install_recording_setex(monkeypatch, mock_redis_storage)

    await cache.set("prices", "daily", PRICE_PARAMS, {"a": 1}, ttl=OVERRIDE_TTL)

    assert [ttl for _, ttl in recorded] == [OVERRIDE_TTL]


# --------------------------------------------------------------------------- #
# AC4: Redis failures degrade to a live fetch without raising.
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_redis_get_failure_falls_through_to_fetch(
    cache: EndpointResponseCache,
    mock_redis_storage: FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = FakeGateway({"symbol": "AAPL"})

    async def failing_get(key: str):
        raise RedisConnectionError("Connection timed out")

    monkeypatch.setattr(mock_redis_storage, "get", failing_get)

    result = await cache.cached_response("prices", "daily", PRICE_PARAMS, gateway.fetch)

    assert result == {"symbol": "AAPL"}
    assert gateway.calls == 1


@pytest.mark.anyio
async def test_redis_set_failure_does_not_raise_and_stays_uncached(
    cache: EndpointResponseCache,
    mock_redis_storage: FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = FakeGateway({"symbol": "AAPL"})

    async def failing_setex(key: str, ttl: int, value: str) -> bool:
        raise RedisConnectionError("Write failure")

    monkeypatch.setattr(mock_redis_storage, "setex", failing_setex)

    first = await cache.cached_response("prices", "daily", PRICE_PARAMS, gateway.fetch)
    second = await cache.cached_response("prices", "daily", PRICE_PARAMS, gateway.fetch)

    assert first == second == {"symbol": "AAPL"}
    assert gateway.calls == 2
    assert _endpoint_keys(mock_redis_storage) == []


@pytest.mark.anyio
async def test_corrupted_payload_is_treated_as_a_miss(
    cache: EndpointResponseCache, mock_redis_storage: FakeRedis
) -> None:
    gateway = FakeGateway({"symbol": "AAPL"})

    await cache.cached_response("prices", "daily", PRICE_PARAMS, gateway.fetch)
    keys = _endpoint_keys(mock_redis_storage)
    assert len(keys) == 1
    mock_redis_storage.data[keys[0]] = "{not json"

    assert await cache.get("prices", "daily", PRICE_PARAMS) is None
    result = await cache.cached_response("prices", "daily", PRICE_PARAMS, gateway.fetch)

    assert result == {"symbol": "AAPL"}
    assert gateway.calls == 2


# --------------------------------------------------------------------------- #
# Typed round-trip via the optional Pydantic model hook.
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_typed_payload_round_trips_through_model(
    cache: EndpointResponseCache, mock_redis_storage: FakeRedis
) -> None:
    prices = _sample_prices()

    await cache.set("prices", "daily", PRICE_PARAMS, prices)

    raw = await cache.get("prices", "daily", PRICE_PARAMS)
    assert isinstance(raw, list)
    assert isinstance(raw[0], dict)

    typed = await cache.get("prices", "daily", PRICE_PARAMS, model=HistoricalPrice)
    assert isinstance(typed, list)
    assert all(isinstance(price, HistoricalPrice) for price in typed)
    assert typed == prices


@pytest.mark.anyio
async def test_cached_response_returns_typed_value(
    cache: EndpointResponseCache,
) -> None:
    prices = _sample_prices()
    gateway = FakeGateway(prices)

    first = await cache.cached_response(
        "prices", "daily", PRICE_PARAMS, gateway.fetch, model=HistoricalPrice
    )
    second = await cache.cached_response(
        "prices", "daily", PRICE_PARAMS, gateway.fetch, model=HistoricalPrice
    )

    assert gateway.calls == 1
    assert first == prices
    assert all(isinstance(price, HistoricalPrice) for price in second)


# --------------------------------------------------------------------------- #
# Null sentinel: a legitimately-None result is cached, not re-fetched.
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_null_result_is_cached_as_a_sentinel(
    cache: EndpointResponseCache, mock_redis_storage: FakeRedis
) -> None:
    gateway = FakeGateway(None)

    first = await cache.cached_response(
        "prices", "on_date", PRICE_PARAMS, gateway.fetch
    )
    second = await cache.cached_response(
        "prices", "on_date", PRICE_PARAMS, gateway.fetch
    )

    assert first is None
    assert second is None
    # A cached "no result" is a hit, not a miss: the gateway runs exactly once.
    assert gateway.calls == 1
    keys = _endpoint_keys(mock_redis_storage)
    assert len(keys) == 1
    assert mock_redis_storage.data[keys[0]] == '{"null": true}'


# --------------------------------------------------------------------------- #
# svcs registration.
# --------------------------------------------------------------------------- #


def test_factory_returns_an_endpoint_cache() -> None:
    assert isinstance(endpoint_response_cache_factory(), EndpointResponseCache)


@pytest.mark.anyio
async def test_registered_in_market_registries() -> None:
    for register in (register_market_services, register_market_stub_services):
        registry = svcs.Registry()
        register(registry)
        async with svcs.Container(registry) as container:
            resolved = await container.aget(EndpointResponseCache)
        assert isinstance(resolved, EndpointResponseCache)
