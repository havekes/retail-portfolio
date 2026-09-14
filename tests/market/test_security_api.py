from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from stockholm import Money

from src.core.enum import InstitutionEnum
from src.market.api import MarketPricesApi, SecurityApi
from src.market.api_types import Security, SecuritySearchResult
from src.market.cache import SecuritySearchCache
from src.market.gateway import MarketGateway
from src.market.repository import (
    PriceRepository,
    SecurityBrokerRepository,
    SecurityRepository,
)
from src.market.schema import SecurityBrokerSchema, SecuritySchema
from src.market.service import MarketService


@pytest.fixture
def mock_gateway() -> MagicMock:
    return MagicMock(spec=MarketGateway)


@pytest.fixture
def mock_market_prices_api() -> AsyncMock:
    return AsyncMock(spec=MarketPricesApi)


@pytest.fixture
def mock_market_service() -> AsyncMock:
    return AsyncMock(spec=MarketService)


@pytest.fixture
def mock_price_repo() -> AsyncMock:
    return AsyncMock(spec=PriceRepository)


@pytest.fixture
def mock_security_broker_repo() -> AsyncMock:
    return AsyncMock(spec=SecurityBrokerRepository)


@pytest.fixture
def mock_security_repo() -> AsyncMock:
    return AsyncMock(spec=SecurityRepository)


@pytest.fixture
def mock_search_cache() -> AsyncMock:
    cache = AsyncMock(spec=SecuritySearchCache)
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=None)
    return cache


@pytest.fixture
def security_api(  # noqa: PLR0913, PLR0917
    mock_gateway: MagicMock,
    mock_market_prices_api: AsyncMock,
    mock_market_service: AsyncMock,
    mock_price_repo: AsyncMock,
    mock_security_broker_repo: AsyncMock,
    mock_security_repo: AsyncMock,
    mock_search_cache: AsyncMock,
) -> SecurityApi:
    return SecurityApi(
        gateway=mock_gateway,
        market_prices_api=mock_market_prices_api,
        market_service=mock_market_service,
        price_repository=mock_price_repo,
        security_broker_repository=mock_security_broker_repo,
        security_repository=mock_security_repo,
        search_cache=mock_search_cache,
    )


@pytest.mark.anyio
async def test_get_or_create_from_broker_returns_cached_mapping_without_search(  # noqa: PLR0913, PLR0917
    security_api: SecurityApi,
    mock_gateway: MagicMock,
    mock_market_prices_api: AsyncMock,
    mock_security_broker_repo: AsyncMock,
    mock_security_repo: AsyncMock,
    mock_search_cache: AsyncMock,
) -> None:
    sec_id = uuid4()
    cached_mapping = SecurityBrokerSchema(
        id=1,
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        broker_symbol="SHOP",
        mapped_symbol="SHOP",
        broker_exchange="TSX",
        mapped_exchange="TO",
        broker_name="Shopify Inc",
        security_id=sec_id,
        search_results=[],
    )
    mock_security_broker_repo.get_by_broker.return_value = cached_mapping

    expected_security = SecuritySchema(
        id=sec_id,
        symbol="SHOP",
        exchange="TO",
        currency="CAD",
        name="Shopify Inc",
        isin="CA82509L1076",
        is_active=True,
        updated_at=datetime.now(UTC),
    )
    mock_security_repo.get_by_id_or_fail.return_value = expected_security

    result = await security_api.get_or_create_from_broker(
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        broker_symbol="SHOP",
        broker_exchange="TSX",
        broker_name="Shopify Inc",
    )

    assert isinstance(result, Security)
    assert result.id == sec_id
    assert result.symbol == "SHOP"
    assert result.exchange == "TO"
    assert result.currency == "CAD"

    mock_security_broker_repo.get_by_broker.assert_awaited_once_with(
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        broker_symbol="SHOP",
        broker_exchange="TSX",
    )
    mock_security_repo.get_by_id_or_fail.assert_awaited_once_with(sec_id)
    mock_gateway.search.assert_not_called()
    mock_search_cache.get.assert_not_called()
    mock_market_prices_api.get_latest_close.assert_not_called()
    mock_security_repo.get_or_create.assert_not_called()
    mock_security_broker_repo.get_or_create.assert_not_called()


@pytest.mark.anyio
async def test_get_or_create_from_broker_performs_search_when_no_mapping_found(  # noqa: PLR0913, PLR0917
    security_api: SecurityApi,
    mock_gateway: MagicMock,
    mock_market_prices_api: AsyncMock,
    mock_security_broker_repo: AsyncMock,
    mock_security_repo: AsyncMock,
    mock_search_cache: AsyncMock,
) -> None:
    mock_security_broker_repo.get_by_broker.return_value = None

    search_result = SecuritySearchResult(
        code="VGRO",
        exchange="TO",
        name="Vanguard Growth ETF Portfolio",
        currency="CAD",
        security_type="ETF",
        isin="CA92203J1093",
        country="Canada",
    )
    mock_gateway.search.return_value = [search_result]

    sec_id = uuid4()
    created_security = SecuritySchema(
        id=sec_id,
        symbol="VGRO",
        exchange="TO",
        currency="CAD",
        name="Vanguard Growth ETF Portfolio",
        isin="CA92203J1093",
        is_active=True,
        updated_at=datetime.now(UTC),
    )
    mock_security_repo.get_or_create.return_value = created_security
    mock_market_prices_api.get_latest_close.return_value = Money(
        Decimal("35.50"), "CAD"
    )

    saved_broker_mapping = SecurityBrokerSchema(
        id=10,
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        broker_symbol="VGRO",
        mapped_symbol="VGRO",
        broker_exchange="TSX",
        mapped_exchange="TO",
        broker_name="Vanguard Growth",
        security_id=sec_id,
        search_results=[search_result],
    )
    mock_security_broker_repo.get_or_create.return_value = saved_broker_mapping

    result = await security_api.get_or_create_from_broker(
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        broker_symbol="VGRO",
        broker_exchange="TSX",
        broker_name="Vanguard Growth",
    )

    assert isinstance(result, Security)
    assert result.id == sec_id
    assert result.symbol == "VGRO"
    assert result.exchange == "TO"

    mock_security_broker_repo.get_by_broker.assert_awaited_once_with(
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        broker_symbol="VGRO",
        broker_exchange="TSX",
    )
    mock_search_cache.get.assert_awaited_once_with("VGRO.TO")
    mock_gateway.search.assert_called_once_with(query="VGRO.TO")
    mock_search_cache.set.assert_awaited_once_with("VGRO.TO", [search_result])
    mock_security_repo.get_or_create.assert_awaited_once()
    mock_market_prices_api.get_latest_close.assert_awaited_once_with(sec_id)
    mock_security_broker_repo.get_or_create.assert_awaited_once()


@pytest.mark.anyio
async def test_get_or_create_from_broker_uses_search_cache_hit_when_no_broker_mapping(  # noqa: PLR0913, PLR0917
    security_api: SecurityApi,
    mock_gateway: MagicMock,
    mock_market_prices_api: AsyncMock,
    mock_security_broker_repo: AsyncMock,
    mock_security_repo: AsyncMock,
    mock_search_cache: AsyncMock,
) -> None:
    mock_security_broker_repo.get_by_broker.return_value = None

    search_result = SecuritySearchResult(
        code="VGRO",
        exchange="TO",
        name="Vanguard Growth ETF Portfolio",
        currency="CAD",
        security_type="ETF",
        isin="CA92203J1093",
        country="Canada",
    )
    mock_search_cache.get.return_value = [search_result]

    sec_id = uuid4()
    created_security = SecuritySchema(
        id=sec_id,
        symbol="VGRO",
        exchange="TO",
        currency="CAD",
        name="Vanguard Growth ETF Portfolio",
        isin="CA92203J1093",
        is_active=True,
        updated_at=datetime.now(UTC),
    )
    mock_security_repo.get_or_create.return_value = created_security
    mock_market_prices_api.get_latest_close.return_value = Money(
        Decimal("35.50"), "CAD"
    )

    saved_broker_mapping = SecurityBrokerSchema(
        id=10,
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        broker_symbol="VGRO",
        mapped_symbol="VGRO",
        broker_exchange="TSX",
        mapped_exchange="TO",
        broker_name="Vanguard Growth",
        security_id=sec_id,
        search_results=[search_result],
    )
    mock_security_broker_repo.get_or_create.return_value = saved_broker_mapping

    result = await security_api.get_or_create_from_broker(
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        broker_symbol="VGRO",
        broker_exchange="TSX",
        broker_name="Vanguard Growth",
    )

    assert isinstance(result, Security)
    assert result.id == sec_id
    assert result.symbol == "VGRO"
    assert result.exchange == "TO"

    mock_security_broker_repo.get_by_broker.assert_awaited_once_with(
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        broker_symbol="VGRO",
        broker_exchange="TSX",
    )
    mock_search_cache.get.assert_awaited_once_with("VGRO.TO")
    mock_gateway.search.assert_not_called()
    mock_search_cache.set.assert_not_called()
    mock_security_repo.get_or_create.assert_awaited_once()
    mock_market_prices_api.get_latest_close.assert_awaited_once_with(sec_id)
    mock_security_broker_repo.get_or_create.assert_awaited_once()


@pytest.mark.anyio
async def test_get_or_create_from_broker_populates_search_cache_on_cache_miss(  # noqa: PLR0913, PLR0917
    security_api: SecurityApi,
    mock_gateway: MagicMock,
    mock_market_prices_api: AsyncMock,
    mock_security_broker_repo: AsyncMock,
    mock_security_repo: AsyncMock,
    mock_search_cache: AsyncMock,
) -> None:
    mock_security_broker_repo.get_by_broker.return_value = None
    mock_search_cache.get.return_value = None

    search_result = SecuritySearchResult(
        code="XEQT",
        exchange="TO",
        name="iShares Core Equity ETF Portfolio",
        currency="CAD",
        security_type="ETF",
        isin="CA46434G1037",
        country="Canada",
    )
    mock_gateway.search.return_value = [search_result]

    sec_id = uuid4()
    created_security = SecuritySchema(
        id=sec_id,
        symbol="XEQT",
        exchange="TO",
        currency="CAD",
        name="iShares Core Equity ETF Portfolio",
        isin="CA46434G1037",
        is_active=True,
        updated_at=datetime.now(UTC),
    )
    mock_security_repo.get_or_create.return_value = created_security
    mock_market_prices_api.get_latest_close.return_value = Money(
        Decimal("30.00"), "CAD"
    )

    saved_broker_mapping = SecurityBrokerSchema(
        id=11,
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        broker_symbol="XEQT",
        mapped_symbol="XEQT",
        broker_exchange="TSX",
        mapped_exchange="TO",
        broker_name="iShares Core Equity",
        security_id=sec_id,
        search_results=[search_result],
    )
    mock_security_broker_repo.get_or_create.return_value = saved_broker_mapping

    result = await security_api.get_or_create_from_broker(
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        broker_symbol="XEQT",
        broker_exchange="TSX",
        broker_name="iShares Core Equity",
    )

    assert isinstance(result, Security)
    assert result.id == sec_id
    assert result.symbol == "XEQT"

    mock_search_cache.get.assert_awaited_once_with("XEQT.TO")
    mock_gateway.search.assert_called_once_with(query="XEQT.TO")
    mock_search_cache.set.assert_awaited_once_with("XEQT.TO", [search_result])


@pytest.mark.anyio
async def test_get_or_create_from_broker_without_search_cache_compatibility(  # noqa: PLR0913, PLR0917
    mock_gateway: MagicMock,
    mock_market_prices_api: AsyncMock,
    mock_market_service: AsyncMock,
    mock_price_repo: AsyncMock,
    mock_security_broker_repo: AsyncMock,
    mock_security_repo: AsyncMock,
) -> None:
    api_without_cache = SecurityApi(
        gateway=mock_gateway,
        market_prices_api=mock_market_prices_api,
        market_service=mock_market_service,
        price_repository=mock_price_repo,
        security_broker_repository=mock_security_broker_repo,
        security_repository=mock_security_repo,
        search_cache=None,
    )

    mock_security_broker_repo.get_by_broker.return_value = None

    search_result = SecuritySearchResult(
        code="VCN",
        exchange="TO",
        name="Vanguard FTSE Canada All Cap Index ETF",
        currency="CAD",
        security_type="ETF",
        isin="CA92203E1030",
        country="Canada",
    )
    mock_gateway.search.return_value = [search_result]

    sec_id = uuid4()
    created_security = SecuritySchema(
        id=sec_id,
        symbol="VCN",
        exchange="TO",
        currency="CAD",
        name="Vanguard FTSE Canada All Cap Index ETF",
        isin="CA92203E1030",
        is_active=True,
        updated_at=datetime.now(UTC),
    )
    mock_security_repo.get_or_create.return_value = created_security
    mock_market_prices_api.get_latest_close.return_value = Money(
        Decimal("42.00"), "CAD"
    )

    saved_broker_mapping = SecurityBrokerSchema(
        id=12,
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        broker_symbol="VCN",
        mapped_symbol="VCN",
        broker_exchange="TSX",
        mapped_exchange="TO",
        broker_name="Vanguard Canada",
        security_id=sec_id,
        search_results=[search_result],
    )
    mock_security_broker_repo.get_or_create.return_value = saved_broker_mapping

    result = await api_without_cache.get_or_create_from_broker(
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        broker_symbol="VCN",
        broker_exchange="TSX",
        broker_name="Vanguard Canada",
    )

    assert isinstance(result, Security)
    assert result.id == sec_id
    mock_gateway.search.assert_called_once_with(query="VCN.TO")
