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
from src.market.composite import (
    CompositeMarketGateway,
    composite_market_gateway_factory,
)
from src.market.fmp import FmpGateway, FmpHttpClient
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
async def test_live_registration_resolves_bare_composite():
    resolved = await _resolve(register_market_services, DataPlaneMarketGateway)

    assert isinstance(resolved, CompositeMarketGateway)
    assert isinstance(resolved._fmp, StubFmpGateway)
    assert isinstance(resolved._polygon, StubPolygonGateway)


@pytest.mark.anyio
async def test_stub_registration_resolves_bare_composite():
    resolved = await _resolve(register_market_stub_services, DataPlaneMarketGateway)

    assert isinstance(resolved, CompositeMarketGateway)
    assert isinstance(resolved._fmp, StubFmpGateway)
    assert isinstance(resolved._polygon, StubPolygonGateway)


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


def test_data_plane_gateway_writes_no_gateway_cache_keys(
    monkeypatch, mock_redis_storage: FakeRedis
):
    counting = CountingFmpGateway()
    monkeypatch.setattr("src.market.composite.fmp_gateway_factory", lambda: counting)

    generator = composite_market_gateway_factory()
    gateway = next(generator)
    try:
        assert isinstance(gateway, CompositeMarketGateway)

        first = gateway.get_key_metrics("AAPL")
        second = gateway.get_key_metrics("AAPL")

        assert first == second
        # The gateway caches nothing itself: both reads reach the provider.
        # Caching happens once, above the gateway, in ``EndpointResponseCache``.
        assert counting.calls["get_key_metrics"] == 2
        assert not any(key.startswith("market:gw:") for key in mock_redis_storage.data)
    finally:
        generator.close()


@pytest.mark.anyio
async def test_data_plane_gateway_resolves_through_sync_container_get():
    """The key must be resolvable with sync ``Container.get`` (data_router's path).

    ``src/market/data_router.py`` resolves ``DataPlaneMarketGateway`` via
    ``services.get(...)`` (sync), so the factory must be a *sync* generator —
    an async factory would raise ``TypeError: Use aget() for async factories.``
    """
    registry = svcs.Registry()
    register_market_services(registry)
    async with svcs.Container(registry) as container:
        gateway = container.get(DataPlaneMarketGateway)

    assert isinstance(gateway, CompositeMarketGateway)


class ClosableStubFmpGateway(StubFmpGateway):
    """Stub FMP gateway that records teardown."""

    def __init__(self) -> None:
        super().__init__(api_key="stub")
        self.closed = False

    def close(self) -> None:
        self.closed = True


class ClosableStubPolygonGateway(StubPolygonGateway):
    """Stub Polygon gateway that records teardown."""

    def __init__(self) -> None:
        super().__init__(api_key="stub")
        self.closed = False

    def close(self) -> None:
        self.closed = True


@pytest.mark.anyio
async def test_container_teardown_releases_both_providers(monkeypatch):
    """Exiting the svcs container closes both composed providers (AC2)."""
    fmp = ClosableStubFmpGateway()
    polygon = ClosableStubPolygonGateway()
    monkeypatch.setattr("src.market.composite.fmp_gateway_factory", lambda: fmp)
    monkeypatch.setattr("src.market.composite.polygon_gateway_factory", lambda: polygon)

    registry = svcs.Registry()
    register_market_services(registry)
    async with svcs.Container(registry) as container:
        gateway = await container.aget(DataPlaneMarketGateway)
        assert isinstance(gateway, CompositeMarketGateway)
        assert not fmp.closed
        assert not polygon.closed

    assert fmp.closed
    assert polygon.closed


@pytest.mark.anyio
async def test_container_teardown_closes_fmp_http_client(monkeypatch):
    """The composed gateway's FMP HTTP client is closed on container teardown."""
    closed: list[bool] = []

    def _close(self: FmpHttpClient) -> None:
        closed.append(True)
        self._client.close()

    monkeypatch.setattr(FmpHttpClient, "close", _close)
    monkeypatch.setattr(
        "src.market.composite.fmp_gateway_factory",
        lambda: FmpGateway(api_key="live-key"),
    )
    monkeypatch.setattr(
        "src.market.composite.polygon_gateway_factory",
        lambda: ClosableStubPolygonGateway(),
    )

    registry = svcs.Registry()
    register_market_services(registry)
    async with svcs.Container(registry) as container:
        await container.aget(DataPlaneMarketGateway)
        assert closed == []

    assert closed == [True]
