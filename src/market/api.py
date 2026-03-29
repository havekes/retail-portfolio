import json
import logging
import uuid
from datetime import UTC, datetime

from pydantic import ValidationError
from stockholm import Money
from svcs import Container

from src.account.enum import InstitutionEnum
from src.market.api_types import (
    Security,
    SecurityId,
    SecuritySearchResult,
)
from src.market.eodhd import eodhd_gateway_factory
from src.market.gateway import MarketGateway
from src.market.repository import (
    PriceRepository,
    SecurityBrokerRepository,
    SecurityRepository,
)
from src.market.schema import SecurityBrokerSchema, SecuritySchema

logger = logging.getLogger(__name__)


class MarketPricesApi:
    _gateway: MarketGateway
    _price_repository: PriceRepository
    _security_repository: SecurityRepository

    def __init__(
        self,
        gateway: MarketGateway,
        price_repository: PriceRepository,
        security_repository: SecurityRepository,
    ):
        self._gateway = gateway
        self._price_repository = price_repository
        self._security_repository = security_repository

    async def get_latest_close(self, security_id: SecurityId) -> Money | None:
        security = await self._security_repository.get_by_id_or_fail(security_id)
        latest_price = await self._price_repository.get_latest_price(security)

        if latest_price is None:
            return None

        return Money(latest_price.close, security.currency)


async def market_prices_factory(container: Container) -> MarketPricesApi:
    return MarketPricesApi(
        gateway=eodhd_gateway_factory(),
        price_repository=await container.aget(PriceRepository),
        security_repository=await container.aget(SecurityRepository),
    )


class SecurityApi:
    _gateway: MarketGateway
    _market_prices_api: MarketPricesApi
    _security_broker_repository: SecurityBrokerRepository
    _security_repository: SecurityRepository

    def __init__(
        self,
        gateway: MarketGateway,
        market_prices_api: MarketPricesApi,
        security_broker_repository: SecurityBrokerRepository,
        security_repository: SecurityRepository,
    ) -> None:
        self._gateway = gateway
        self._market_prices_api = market_prices_api
        self._security_broker_repository = security_broker_repository
        self._security_repository = security_repository

    async def get_by_id(self, security_id: SecurityId) -> Security:
        security = await self._security_repository.get_by_id_or_fail(security_id)
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
        search_results = self._gateway.search(
            query=f"{mapped_symbol}.{mapped_exchange}"
        )
        logger.debug(
            "Search results for %s.%s (%s): %s",
            mapped_symbol,
            mapped_exchange,
            broker_name,
            json.dumps([r.model_dump() for r in search_results]),
        )

        if len(search_results) == 0:
            msg = f"No search results for {mapped_symbol}.{mapped_exchange} ({broker_name})"  # noqa: E501
            raise ValueError(msg)

        result = search_results[0]

        try:
            security = await self._security_repository.get_or_create(
                SecuritySchema(
                    id=uuid.uuid4(),
                    symbol=result.code,
                    exchange=result.exchange,
                    currency=result.currency,
                    name=result.name,
                    isin=result.isin,
                    updated_at=datetime.now(UTC),
                )
            )
        except ValidationError:
            logger.exception(
                "Failed to create security from search results: %s",
                json.dumps(result.model_dump()),
            )
            raise

        _ = await self._market_prices_api.get_latest_close(security.id)

        try:
            security_broker = SecurityBrokerSchema(
                institution_id=institution_id,
                broker_symbol=broker_symbol,
                mapped_symbol=mapped_symbol,
                broker_exchange=broker_exchange,
                mapped_exchange=mapped_exchange,
                broker_name=broker_name,
                security_id=security.id,
                search_results=search_results,
            )
        except ValidationError:
            logger.exception(
                "Failed to create security broker from search results: %s",
                json.dumps([r.model_dump() for r in search_results]),
            )
            raise

        _ = await self._security_broker_repository.get_or_create(security_broker)

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

        return replacements.get(broker_exchange, broker_exchange)


async def security_api_factory(container: Container) -> SecurityApi:
    return SecurityApi(
        gateway=eodhd_gateway_factory(),
        market_prices_api=await container.aget(MarketPricesApi),
        security_broker_repository=await container.aget(SecurityBrokerRepository),
        security_repository=await container.aget(SecurityRepository),
    )
