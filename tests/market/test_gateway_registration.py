# ruff: noqa: SLF001
"""svcs container-level tests for the data-plane gateway registration.

Runs entirely offline: the suite's autouse in-memory Redis fake backs the
cache, and ``STUB_EXTERNAL_API=true`` (set in ``tests/conftest.py``) makes both
provider factories return their deterministic stubs.
"""

from collections import defaultdict

import pytest
import svcs

from src.config.services import register_market_stub_services
from src.market import register_market_services
from src.market.cache import CachedMarketGateway
from src.market.composite import (
    CompositeMarketGateway,
    composite_market_gateway_factory,
)
from src.market.gateway import DataPlaneMarketGateway, MarketGateway
from src.stubs.eodhd import StubEodhdGateway
from src.stubs.fmp import StubFmpGateway
from src.stubs.polygon import StubPolygonGateway
from tests.fixtures.redis import FakeRedis


async def _resolve(register, key):
    registry = svcs.Registry()
    register(registry)
    async with svcs.Container(registry) as container:
        return await container.aget(key)


def test_data_plane_key_is_a_distinct_market_gateway_key():
    assert issubclass(DataPlaneMarketGateway, MarketGateway)
    assert DataPlaneMarketGateway is not MarketGateway


@pytest.mark.anyio
async def test_live_registration_resolves_cache_wrapped_composite():
    resolved = await _resolve(register_market_services, DataPlaneMarketGateway)

    assert isinstance(resolved, CachedMarketGateway)
    composite = resolved._inner
    assert isinstance(composite, CompositeMarketGateway)
    assert isinstance(composite._fmp, StubFmpGateway)
    assert isinstance(composite._polygon, StubPolygonGateway)


@pytest.mark.anyio
async def test_stub_registration_resolves_cache_wrapped_composite():
    resolved = await _resolve(register_market_stub_services, DataPlaneMarketGateway)

    assert isinstance(resolved, CachedMarketGateway)
    composite = resolved._inner
    assert isinstance(composite, CompositeMarketGateway)
    assert isinstance(composite._fmp, StubFmpGateway)
    assert isinstance(composite._polygon, StubPolygonGateway)


@pytest.mark.anyio
async def test_legacy_market_gateway_registration_stays_on_eodhd():
    registry = svcs.Registry()
    register_market_services(registry)
    async with svcs.Container(registry) as container:
        legacy = await container.aget(MarketGateway)
        data_plane = await container.aget(DataPlaneMarketGateway)

    # The legacy key still resolves the EODHD factory's gateway (its stub in
    # stub mode) — never the composed FMP/Polygon gateway.
    assert isinstance(legacy, StubEodhdGateway)
    assert not isinstance(legacy, CompositeMarketGateway)
    assert data_plane is not legacy


class CountingFmpGateway(StubFmpGateway):
    """Stub FMP gateway that counts capability invocations."""

    def __init__(self) -> None:
        super().__init__(api_key="stub")
        self.calls: dict[str, int] = defaultdict(int)

    def get_key_metrics(self, symbol: str, *, exchange=None):
        self.calls["get_key_metrics"] += 1
        return super().get_key_metrics(symbol, exchange=exchange)


def test_data_plane_gateway_is_cache_wrapped(monkeypatch, mock_redis_storage: FakeRedis):
    counting = CountingFmpGateway()
    monkeypatch.setattr("src.market.composite.fmp_gateway_factory", lambda: counting)

    gateway = composite_market_gateway_factory()
    assert isinstance(gateway, CachedMarketGateway)

    first = gateway.get_key_metrics("AAPL")
    second = gateway.get_key_metrics("AAPL")

    assert first == second
    # The provider is hit exactly once; the second read is served from cache.
    assert counting.calls["get_key_metrics"] == 1
    assert any(
        key.startswith("market:gw:get_key_metrics:")
        for key in mock_redis_storage.data
    )
