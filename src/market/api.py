from stockholm import Money
from svcs import Container

from src.market.api_types import Security, SecurityId
from src.market.eodhd import EodhdGateway, eodhd_gateway_factory
from src.market.repository import PriceRepository, SecurityRepository
from src.market.repository_eodhd import eodhd_price_repository_factory
from src.market.repository_sqlalchemy import sqlalchemy_security_repository_factory


class MarketPricesApi:
    _eodhd: EodhdGateway
    _price_repository: PriceRepository
    _security_repository: SecurityRepository

    def __init__(
        self,
        eodhd: EodhdGateway,
        price_repository: PriceRepository,
        security_repository: SecurityRepository,
    ):
        self._eodhd = eodhd
        self._price_repository = price_repository
        self._security_repository = security_repository

    async def get_latest_close(self, security_id: SecurityId) -> Money | None:
        security = await self._security_repository.get_by_id(security_id)
        latest_price = await self._price_repository.get_latest_price(security)

        if latest_price is None:
            return None

        return Money(latest_price.close, security.currency)


class SecurityApi:
    _security_repository: SecurityRepository

    def __init__(self, security_repository: SecurityRepository) -> None:
        self._security_repository = security_repository

    async def get_by_id(self, security_id: SecurityId) -> Security:
        security = await self._security_repository.get_by_id(security_id)
        return Security.model_validate(security)


async def market_prices_factory(container: Container) -> MarketPricesApi:
    return MarketPricesApi(
        eodhd=eodhd_gateway_factory(),
        price_repository=await eodhd_price_repository_factory(container),
        security_repository=await sqlalchemy_security_repository_factory(container),
    )
