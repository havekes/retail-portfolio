from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from stockholm import Money
from src.core.enum import InstitutionEnum
from src.market.api import MarketPricesApi, SecurityApi
from src.market.api_types import Security, SecuritySearchResult
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
def security_api(
    mock_gateway: MagicMock,
    mock_market_prices_api: AsyncMock,
    mock_market_service: AsyncMock,
    mock_price_repo: AsyncMock,
    mock_security_broker_repo: AsyncMock,
    mock_security_repo: AsyncMock,
) -> SecurityApi:
    return SecurityApi(
        gateway=mock_gateway,
        market_prices_api=mock_market_prices_api,
        market_service=mock_market_service,
        price_repository=mock_price_repo,
        security_broker_repository=mock_security_broker_repo,
        security_repository=mock_security_repo,
    )


@pytest.mark.anyio
async def test_get_or_create_from_broker_returns_cached_mapping_without_search(
    security_api: SecurityApi,
    mock_gateway: MagicMock,
    mock_market_prices_api: AsyncMock,
    mock_security_broker_repo: AsyncMock,
    mock_security_repo: AsyncMock,
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
    mock_market_prices_api.get_latest_close.assert_not_called()
    mock_security_repo.get_or_create.assert_not_called()
    mock_security_broker_repo.get_or_create.assert_not_called()


@pytest.mark.anyio
async def test_get_or_create_from_broker_performs_search_when_no_mapping_found(
    security_api: SecurityApi,
    mock_gateway: MagicMock,
    mock_market_prices_api: AsyncMock,
    mock_security_broker_repo: AsyncMock,
    mock_security_repo: AsyncMock,
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
    mock_gateway.search.assert_called_once_with(query="VGRO.TO")
    mock_security_repo.get_or_create.assert_awaited_once()
    mock_market_prices_api.get_latest_close.assert_awaited_once_with(sec_id)
    mock_security_broker_repo.get_or_create.assert_awaited_once()
