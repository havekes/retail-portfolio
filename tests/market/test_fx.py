"""Tests for the ECB FX rate provider and its daily refresh.

All Redis access is the in-memory fake from ``tests/fixtures/redis.py`` and all
HTTP access is mocked — no test touches a real Redis or network.
"""

import base64
import asyncio
import io
import logging
import zipfile
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from currency_converter import ECB_URL, CurrencyConverter
from redis.exceptions import RedisError
from svcs import Container, Registry

from src.account.repository import PositionRepository
from src.account.service.account import AccountService
from src.account.service.position import PositionService, position_service_factory
from src.core.redis import redis_manager
from src.integration.api import IntegrationAccountApi, IntegrationUserApi
from src.market.api import MarketPricesApi, SecurityApi
from src.market.fx import (
    ECB_FETCHED_AT_KEY,
    ECB_ZIP_KEY,
    FxRateProvider,
    fx_rate_provider_factory,
    refresh_fx_rates,
)
from src.market.task import _daily_fx_refresh, daily_fx_refresh
from src.worker import huey

USD = "USD"


def _make_zip(rows: list[tuple[date, str]]) -> bytes:
    """Build a minimal ECB-style history zip from ``(date, USD rate)`` rows."""
    lines = ["Date,USD,GBP"]
    lines.extend(f"{day.isoformat()},{usd_rate},0.85" for day, usd_rate in rows)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("eurofxref-hist.csv", "\n".join(lines) + "\n")
    return buffer.getvalue()


def _seed_redis(store, zip_bytes: bytes, fetched_at: str) -> None:
    store.data[ECB_ZIP_KEY] = base64.b64encode(zip_bytes).decode("ascii")
    store.data[ECB_FETCHED_AT_KEY] = fetched_at


def _usd_last_date(converter: CurrencyConverter) -> date:
    bounds = cast("dict[str, Any]", converter.bounds)
    return bounds[USD].last_date


def _bundled_last_date() -> date:
    return _usd_last_date(CurrencyConverter())


@pytest.mark.anyio
async def test_refresh_fx_rates_stores_zip_bytes_and_fetch_date():
    """The refresh stores base64 zip bytes plus today's fetch date."""
    zip_bytes = _make_zip([(date(2026, 10, 1), "1.10")])
    redis = AsyncMock()
    http_client = AsyncMock()
    http_client.get = AsyncMock(
        return_value=httpx.Response(
            200, content=zip_bytes, request=httpx.Request("GET", ECB_URL)
        )
    )

    await refresh_fx_rates(redis, http_client)

    http_client.get.assert_awaited_once_with(ECB_URL)
    stored = {call.args[0]: call.args[1] for call in redis.set.await_args_list}
    assert set(stored) == {ECB_ZIP_KEY, ECB_FETCHED_AT_KEY}
    assert base64.b64decode(stored[ECB_ZIP_KEY]) == zip_bytes
    assert stored[ECB_FETCHED_AT_KEY] == datetime.now(UTC).date().isoformat()


@pytest.mark.anyio
async def test_provider_builds_converter_from_redis(mock_redis_storage):
    """A Redis zip with last date D yields bounds last_date D and as_of D."""
    last_date = date(2026, 10, 1)
    _seed_redis(mock_redis_storage, _make_zip([(last_date, "1.10")]), "2026-10-02")
    provider = FxRateProvider(redis_manager=redis_manager)

    converter = await provider.converter()

    assert _usd_last_date(converter) == last_date
    assert await provider.as_of() == last_date


@pytest.mark.anyio
async def test_provider_falls_back_when_redis_empty(mock_redis_storage, caplog):
    """With no cached data the bundled converter is returned and a warning logged."""
    provider = FxRateProvider(redis_manager=redis_manager)

    with caplog.at_level(logging.WARNING, logger="src.market.fx"):
        converter = await provider.converter()

    assert _usd_last_date(converter) == _bundled_last_date()
    assert any("falling back" in record.message for record in caplog.records)


@pytest.mark.anyio
async def test_provider_falls_back_when_redis_unavailable(
    mock_redis_storage, monkeypatch, caplog
):
    """A RedisError makes the provider fall back to the bundled converter."""

    async def _raise(_key):
        raise RedisError("connection refused")

    monkeypatch.setattr(mock_redis_storage, "get", _raise)
    provider = FxRateProvider(redis_manager=redis_manager)

    with caplog.at_level(logging.WARNING, logger="src.market.fx"):
        converter = await provider.converter()

    assert _usd_last_date(converter) == _bundled_last_date()
    assert any("falling back" in record.message for record in caplog.records)


@pytest.mark.anyio
async def test_provider_warns_when_rates_are_stale(mock_redis_storage, caplog):
    """A last date older than 3 business days logs a stale-rates warning."""
    old_date = datetime.now(UTC).date() - timedelta(days=10)
    _seed_redis(mock_redis_storage, _make_zip([(old_date, "1.10")]), "2026-10-02")
    provider = FxRateProvider(redis_manager=redis_manager)

    with caplog.at_level(logging.WARNING, logger="src.market.fx"):
        await provider.converter()

    assert any("stale" in record.message.lower() for record in caplog.records)


@pytest.mark.anyio
async def test_provider_reuses_converter_until_fetched_at_changes(
    mock_redis_storage,
):
    """An unchanged fetch date reuses the parsed converter exactly once."""
    first_date = date(2026, 10, 1)
    _seed_redis(mock_redis_storage, _make_zip([(first_date, "1.10")]), "2026-10-02")
    provider = FxRateProvider(redis_manager=redis_manager)

    first = await provider.converter()
    second = await provider.converter()
    assert first is second

    fresh_date = date(2026, 10, 2)
    _seed_redis(mock_redis_storage, _make_zip([(fresh_date, "1.20")]), "2026-10-03")
    third = await provider.converter()

    assert third is not first
    assert _usd_last_date(third) == fresh_date


@pytest.mark.anyio
async def test_position_service_factory_uses_provider_converter(mock_redis_storage):
    """PositionService resolved from the container uses the provider's converter."""
    last_date = date(2026, 10, 1)
    _seed_redis(mock_redis_storage, _make_zip([(last_date, "1.10")]), "2026-10-02")

    registry = Registry()
    registry.register_factory(FxRateProvider, fx_rate_provider_factory)
    registry.register_value(MarketPricesApi, AsyncMock())
    registry.register_value(PositionRepository, AsyncMock())
    registry.register_value(SecurityApi, AsyncMock())
    registry.register_value(AccountService, AsyncMock())
    registry.register_value(IntegrationUserApi, AsyncMock())
    registry.register_value(IntegrationAccountApi, AsyncMock())
    registry.register_factory(PositionService, position_service_factory)

    async with Container(registry) as container:
        service: PositionService = await container.aget(PositionService)

    assert _usd_last_date(service._fx_rates) == last_date  # noqa: SLF001


def test_daily_fx_refresh_is_periodic_task():
    """The refresh must be registered as a Huey periodic task."""
    task_names = {item.name for item in huey._registry.periodic_tasks}
    assert "daily_fx_refresh" in task_names


def test_daily_fx_refresh_calls_async_logic():
    """The periodic wrapper runs the async logic via asyncio.run."""
    huey.immediate = True
    with patch("src.market.task.asyncio.run") as mock_run:
        daily_fx_refresh()
        mock_run.assert_called_once()
        args = mock_run.call_args[0]
        assert asyncio.iscoroutine(args[0])
        args[0].close()
    huey.immediate = False


@pytest.mark.anyio
async def test_daily_fx_refresh_delegates_to_refresh_fx_rates(monkeypatch):
    """The task hands the Redis client and an HTTP client to refresh_fx_rates."""
    calls: dict[str, object] = {}

    async def _fake_refresh(redis, http_client):
        calls["redis"] = redis
        calls["http_client"] = http_client

    monkeypatch.setattr("src.market.task.refresh_fx_rates", _fake_refresh)

    await _daily_fx_refresh()

    assert "redis" in calls
    assert "http_client" in calls
