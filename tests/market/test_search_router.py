from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import status

from src.main import app
from src.market.api_types import SecuritySearchResult
from src.market.cache import SecuritySearchCache
from src.market.gateway import MarketGateway

EXPECTED_COUNT = 1


@pytest.fixture
def mock_search_cache() -> AsyncMock:
    cache = AsyncMock(spec=SecuritySearchCache)
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=None)
    return cache


@pytest.fixture
def mock_gateway() -> MagicMock:
    gateway = MagicMock(spec=MarketGateway)
    gateway.search = MagicMock(return_value=[])
    return gateway


@pytest.fixture
def sample_result() -> SecuritySearchResult:
    return SecuritySearchResult(
        code="AAPL",
        exchange="US",
        name="Apple Inc.",
        currency="USD",
        security_type="Common Stock",
        isin="US0378331005",
        country="USA",
    )


@pytest.fixture(autouse=True)
def override_services(
    mock_search_cache: AsyncMock,
    mock_gateway: MagicMock,
) -> None:
    # Ensure registry overrides are registered on app.state.svcs_registry
    if hasattr(app.state, "svcs_registry"):
        app.state.svcs_registry.register_value(SecuritySearchCache, mock_search_cache)
        app.state.svcs_registry.register_value(MarketGateway, mock_gateway)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/v1/market/search",
        "/api/v1/market/securities/search",
    ],
)
async def test_market_search_cache_hit_skips_gateway(
    auth_client,
    mock_search_cache: AsyncMock,
    mock_gateway: MagicMock,
    sample_result: SecuritySearchResult,
    endpoint: str,
) -> None:
    # Re-register values in case lifespan re-initialized svcs_registry
    app.state.svcs_registry.register_value(SecuritySearchCache, mock_search_cache)
    app.state.svcs_registry.register_value(MarketGateway, mock_gateway)

    mock_search_cache.get.return_value = [sample_result]

    response = await auth_client.get(f"{endpoint}?q=AAPL")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == EXPECTED_COUNT
    assert data[0]["code"] == "AAPL"
    assert data[0]["name"] == "Apple Inc."

    mock_search_cache.get.assert_awaited_once_with("AAPL")
    mock_gateway.search.assert_not_called()
    mock_search_cache.set.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/v1/market/search",
        "/api/v1/market/securities/search",
    ],
)
async def test_market_search_cache_miss_queries_gateway_and_sets_cache(
    auth_client,
    mock_search_cache: AsyncMock,
    mock_gateway: MagicMock,
    sample_result: SecuritySearchResult,
    endpoint: str,
) -> None:
    # Re-register values in case lifespan re-initialized svcs_registry
    app.state.svcs_registry.register_value(SecuritySearchCache, mock_search_cache)
    app.state.svcs_registry.register_value(MarketGateway, mock_gateway)

    mock_search_cache.get.return_value = None
    mock_gateway.search.return_value = [sample_result]

    response = await auth_client.get(f"{endpoint}?q=AAPL")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == EXPECTED_COUNT
    assert data[0]["code"] == "AAPL"
    assert data[0]["exchange"] == "US"

    mock_search_cache.get.assert_awaited_once_with("AAPL")
    mock_gateway.search.assert_called_once_with("AAPL")
    mock_search_cache.set.assert_awaited_once_with("AAPL", [sample_result])
