from datetime import UTC, date, datetime, timedelta
from typing import override

import holidays
from svcs import Container

from src.market.api_types import SecurityId
from src.market.eodhd import eodhd_gateway_factory
from src.market.gateway import MarketGateway
from src.market.repository import PriceRepository
from src.market.repository_sqlalchemy import sqlalchemy_price_repository_factory
from src.market.schema import PriceSchema, SecuritySchema


class EodhdPriceRepository(PriceRepository):
    _db_repository: PriceRepository
    _gateway: MarketGateway

    def __init__(self, db_repository: PriceRepository, gateway: MarketGateway):
        self._db_repository = db_repository
        self._gateway = gateway

    @override
    async def get_by_security(self, security_id: SecurityId) -> list[PriceSchema]:
        return await self._db_repository.get_by_security(security_id)

    @override
    async def get_prices(
        self, security: SecuritySchema, from_date: date, to_date: date
    ) -> list[PriceSchema]:
        existing_prices = await self._db_repository.get_prices(
            security, from_date, to_date
        )

        new_prices_eodhd = self._gateway.get_prices(
            security.id, security.symbol, security.exchange, from_date, to_date
        )
        new_prices = [
            PriceSchema.from_historical_price(price) for price in new_prices_eodhd
        ]

        merged = {p.date: p for p in new_prices}
        for p in existing_prices:
            if p.date not in merged:
                merged[p.date] = p

        all_prices = list(merged.values())
        await self._db_repository.save_prices(all_prices)

        return sorted(all_prices, key=lambda p: p.date)

    @override
    async def get_latest_price(self, security: SecuritySchema) -> PriceSchema | None:
        latest_price = await self._db_repository.get_latest_price(security)

        nyse_holidays = holidays.NYSE()  # ty: ignore[unresolved-attribute]
        latest_close_date = datetime.now(UTC).date() - timedelta(days=1)

        while (
            latest_close_date.weekday() >= 5  # noqa: PLR2004
            or latest_close_date in nyse_holidays
        ):
            latest_close_date -= timedelta(days=1)

        if latest_price is not None and latest_price.date >= latest_close_date:
            return latest_price

        prices = await self.get_prices(
            security,
            from_date=datetime.now(UTC).date() - timedelta(days=7),
            to_date=latest_close_date,
        )

        return prices[-1] if prices else None

    @override
    async def get_price_on_date(
        self, security: SecuritySchema, date: date
    ) -> PriceSchema | None:
        existing_price = await self._db_repository.get_price_on_date(security, date)

        if existing_price is not None:
            return existing_price

        new_price_eodhd = self._gateway.get_price_on_date(
            security.id, security.symbol, security.exchange, date
        )
        if new_price_eodhd is None:
            return None
        new_price = PriceSchema.model_validate(new_price_eodhd)
        return await self._db_repository.save_price(new_price)

    @override
    async def save_price(self, price: PriceSchema) -> PriceSchema:
        raise NotImplementedError

    @override
    async def save_prices(self, prices: list[PriceSchema]) -> list[PriceSchema]:
        raise NotImplementedError


async def eodhd_price_repository_factory(
    container: Container,
) -> EodhdPriceRepository:
    return EodhdPriceRepository(
        db_repository=await sqlalchemy_price_repository_factory(container),
        gateway=eodhd_gateway_factory(),
    )
