import uuid
from datetime import UTC, datetime

from stockholm import Money
from svcs import Container

from src.account.enum import InstitutionEnum
from src.market.api_types import Security, SecurityId
from src.market.eodhd import EodhdGateway, eodhd_gateway_factory
from src.market.repository import (
    PriceRepository,
    SecurityBrokerRepository,
    SecurityRepository,
)
from src.market.repository_eodhd import eodhd_price_repository_factory
from src.market.repository_sqlalchemy import (
    sqlalchemy_security_broker_repository_factory,
    sqlalchemy_security_repository_factory,
)
from src.market.schema import SecurityBrokerSchema, SecuritySchema


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


async def market_prices_factory(container: Container) -> MarketPricesApi:
    return MarketPricesApi(
        eodhd=eodhd_gateway_factory(),
        price_repository=await eodhd_price_repository_factory(container),
        security_repository=await sqlalchemy_security_repository_factory(container),
    )


class SecurityApi:
    _eodhd: EodhdGateway
    _market_prices_api: MarketPricesApi
    _security_broker_repository: SecurityBrokerRepository
    _security_repository: SecurityRepository

    def __init__(
        self,
        eodhd: EodhdGateway,
        market_prices_api: MarketPricesApi,
        security_broker_repository: SecurityBrokerRepository,
        security_repository: SecurityRepository,
    ) -> None:
        self._eodhd = eodhd
        self._market_prices_api = market_prices_api
        self._security_broker_repository = security_broker_repository
        self._security_repository = security_repository

    async def get_by_id(self, security_id: SecurityId) -> Security:
        security = await self._security_repository.get_by_id(security_id)
        return Security.model_validate(security)

    async def get_or_create_from_broker(
        self,
        institution_id: InstitutionEnum,
        broker_symbol: str,
        broker_exchange: str,
        broker_name: str,
    ) -> Security:
        mapped_symbol = self._map_eodhd_symbol(broker_symbol)
        mapped_exchange = self._map_eodhd_exchange(broker_exchange)
        search_results = self._eodhd.search(query=f"{mapped_symbol}.{mapped_exchange}")

        result = search_results[0]

        security = await self._security_repository.get_or_create(
            SecuritySchema(
                id=uuid.uuid4(),
                symbol=result["Code"],
                exchange=result["Exchange"],
                currency="USD",
                name=result["Name"],
                isin=result["ISIN"],
                updated_at=datetime.now(UTC),
            )
        )

        _ = await self._market_prices_api.get_latest_close(security.id)

        _ = await self._security_broker_repository.get_or_create(
            SecurityBrokerSchema(
                institution_id=institution_id,
                broker_symbol=broker_symbol,
                mapped_symbol=mapped_symbol,
                broker_exchange=broker_exchange,
                mapped_exchange=mapped_exchange,
                broker_name=broker_name,
                security_id=security.id,
                search_results=search_results,
            )
        )

        return Security.model_validate(security)

    def _map_eodhd_symbol(self, broker_symbol: str) -> str:
        return broker_symbol.replace(".", "-")

    def _map_eodhd_exchange(self, broker_exchange: str) -> str:
        replacements = {
            "CSE": "CA",
            "TSX": "TO",
            "NYSE": "US",
            "NASDAQ": "US",
        }

        try:
            return replacements[broker_exchange]
        except KeyError:
            return broker_exchange


async def security_api_factory(container: Container) -> SecurityApi:
    return SecurityApi(
        eodhd=eodhd_gateway_factory(),
        market_prices_api=await market_prices_factory(container),
        security_broker_repository=await sqlalchemy_security_broker_repository_factory(
            container
        ),
        security_repository=await sqlalchemy_security_repository_factory(container),
    )
