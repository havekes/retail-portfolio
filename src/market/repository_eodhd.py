from datetime import UTC, date, datetime, timedelta
from typing import override

from svcs import Container

from src.market.eodhd import EodhdGateway, eodhd_gateway_factory
from src.market.repository import PriceRepository
from src.market.repository_sqlalchemy import sqlalchemy_price_repository_factory
from src.market.schema import PriceSchema, SecuritySchema


class EodhdPriceRepository(PriceRepository):
    _db_repository: PriceRepository
    _eodhd: EodhdGateway

    def __init__(self, db_repository: PriceRepository, eodhd: EodhdGateway):
        self._db_repository = db_repository
        self._eodhd = eodhd

    @override
    async def get_prices(
        self, security: SecuritySchema, from_date: date, to_date: date
    ) -> list[PriceSchema]:
        existing_prices = await self._db_repository.get_prices(
            security, from_date, to_date
        )

        # TODO make it smarter to account for non-trading days
        if existing_prices and existing_prices[-1].date == to_date:
            return existing_prices

        new_prices_eodhd = self._eodhd.get_prices(security, from_date, to_date)
        new_prices = [
            PriceSchema.from_historical_price(price) for price in new_prices_eodhd
        ]
        return await self._db_repository.save_prices(new_prices)

    @override
    async def get_latest_price(self, security: SecuritySchema) -> PriceSchema | None:
        latest_price = await self._db_repository.get_latest_price(security)
        latest_close_date = datetime.now(UTC).date() - timedelta(days=1)

        # TODO make it smarter to account for non-trading days
        if latest_price is not None and latest_price.date == latest_close_date:
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

        new_price_eodhd = self._eodhd.get_price_on_date(security, date)
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
        eodhd=eodhd_gateway_factory(),
    )
