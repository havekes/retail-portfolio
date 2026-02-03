from datetime import date
from typing import override

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from svcs.fastapi import DepContainer

from src.market.api_types import SecurityId
from src.market.model import PriceModel, SecurityModel
from src.market.repository import (
    PriceRepository,
    SecurityBrokerRepository,
    SecurityRepository,
)
from src.market.schema import PriceSchema, SecurityBrokerSchema, SecuritySchema


class SqlAlchemySecurityRepository(SecurityRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    @override
    async def get_by_id(self, security_id: SecurityId) -> SecuritySchema:
        security_model = await self._session.get(SecurityModel, security_id)
        assert security_model is not None
        result = SecuritySchema.model_validate(security_model)
        await self._session.commit()
        return result

    @override
    async def get_or_create(self, security: SecuritySchema) -> SecuritySchema:
        # First check if a security exists with this symbol and exchange
        existing = await self._session.execute(
            select(SecurityModel)
            .where(SecurityModel.symbol == security.symbol)
            .where(SecurityModel.exchange == security.exchange)
            .limit(1)
        )
        existing_security = existing.scalar_one_or_none()

        if existing_security:
            result = SecuritySchema.model_validate(existing_security)
            await self._session.commit()
            return result

        # If not exists, insert the new security
        values = security.model_dump()
        _ = await self._session.execute(insert(SecurityModel).values(values))
        await self._session.commit()

        # Fetch the newly created security
        security_model = await self._session.execute(
            select(SecurityModel)
            .where(SecurityModel.symbol == security.symbol)
            .where(SecurityModel.exchange == security.exchange)
            .limit(1)
        )
        security_model = security_model.scalar_one()
        result = SecuritySchema.model_validate(security_model)
        await self._session.commit()
        return result


async def sqlalchemy_security_repository_factory(
    container: DepContainer,
) -> SqlAlchemySecurityRepository:
    return SqlAlchemySecurityRepository(session=await container.aget(AsyncSession))


class SqlAlchemySecurityBrokerRepository(SecurityBrokerRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    @override
    async def get_or_create(
        self, security_broker: SecurityBrokerSchema
    ) -> SecurityBrokerSchema:
        raise NotImplementedError


async def sqlalchemy_security_broker_repository_factory(
    container: DepContainer,
) -> SqlAlchemySecurityBrokerRepository:
    return SqlAlchemySecurityBrokerRepository(
        session=await container.aget(AsyncSession)
    )


class SqlAlchemyPriceRepository(PriceRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    @override
    async def get_prices(
        self, security: SecuritySchema, from_date: date, to_date: date
    ) -> list[PriceSchema]:
        prices = await self._session.execute(
            select(PriceModel)
            .where(PriceModel.security_id == security.id)
            .where(PriceModel.date >= from_date)
            .where(PriceModel.date <= to_date)
            .order_by(PriceModel.date)
        )
        result = [PriceSchema.model_validate(price) for price in prices.scalars()]
        await self._session.commit()
        return result

    @override
    async def get_price_on_date(
        self, security: SecuritySchema, date: date
    ) -> PriceSchema | None:
        price = await self._session.execute(
            select(PriceModel)
            .where(PriceModel.security_id == security.id)
            .where(PriceModel.date == date)
        )
        result = price.scalar_one_or_none()
        await self._session.commit()
        if result is None:
            return None
        return PriceSchema.model_validate(result)

    @override
    async def get_latest_price(self, security: SecuritySchema) -> PriceSchema | None:
        price = await self._session.execute(
            select(PriceModel)
            .where(PriceModel.security_id == security.id)
            .order_by(PriceModel.date.desc())
            .limit(1)
        )
        result = price.scalar_one_or_none()
        await self._session.commit()
        if result is None:
            return None
        return PriceSchema.model_validate(result)

    @override
    async def save_price(self, price: PriceSchema) -> PriceSchema:
        price_model = PriceModel(**price.model_dump())
        self._session.add(price_model)
        await self._session.commit()
        await self._session.refresh(price_model)
        return PriceSchema.model_validate(price_model)

    @override
    async def save_prices(self, prices: list[PriceSchema]) -> list[PriceSchema]:
        price_models = [PriceModel(**price.model_dump()) for price in prices]
        self._session.add_all(price_models)
        await self._session.commit()
        for price_model in price_models:
            await self._session.refresh(price_model)
        return [PriceSchema.model_validate(price_model) for price_model in price_models]


async def sqlalchemy_price_repository_factory(
    container: DepContainer,
) -> SqlAlchemyPriceRepository:
    return SqlAlchemyPriceRepository(
        session=await container.aget(AsyncSession),
    )
