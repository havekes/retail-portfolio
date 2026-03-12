import uuid
from datetime import date
from typing import override

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from svcs import Container

from src.auth.api_types import UserId
from src.market.api_types import SecurityId
from src.market.exception import SecurityNotFoundError
from src.market.model import (
    PriceModel,
    SecurityBrokerModel,
    SecurityModel,
    WatchlistModel,
)
from src.market.repository import (
    PriceRepository,
    SecurityBrokerRepository,
    SecurityRepository,
    WatchlistRepository,
)
from src.market.schema import (
    PriceSchema,
    SecurityBrokerSchema,
    SecuritySchema,
    WatchlistRead,
)


class SqlAlchemySecurityRepository(SecurityRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    @override
    async def get_by_id_or_fail(self, security_id: SecurityId) -> SecuritySchema:
        security_model = await self._session.get(SecurityModel, security_id)

        if security_model is None:
            raise SecurityNotFoundError(security_id)

        return SecuritySchema.model_validate(security_model)

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
            return SecuritySchema.model_validate(existing_security)

        # If not exists, insert the new security
        values = security.model_dump()
        if values.get("id") is None:
            values["id"] = uuid.uuid4()
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
        return SecuritySchema.model_validate(security_model)

    @override
    async def get_all_active_securities(self) -> list[SecuritySchema]:
        securities = await self._session.execute(
            select(SecurityModel).where(SecurityModel.is_active)
        )
        return [
            SecuritySchema.model_validate(security) for security in securities.scalars()
        ]


async def sqlalchemy_security_repository_factory(
    container: Container,
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
        existing = await self._session.execute(
            select(SecurityBrokerModel)
            .where(
                SecurityBrokerModel.institution_id
                == security_broker.institution_id.value
            )
            .where(SecurityBrokerModel.broker_symbol == security_broker.broker_symbol)
            .where(
                SecurityBrokerModel.broker_exchange == security_broker.broker_exchange
            )
            .limit(1)
        )
        existing_broker = existing.scalar_one_or_none()

        if existing_broker:
            return SecurityBrokerSchema.model_validate(existing_broker)

        values = {
            k: v
            for k, v in security_broker.model_dump().items()
            if k not in ("id", "created_at")
        }
        values["institution_id"] = security_broker.institution_id.value
        await self._session.execute(insert(SecurityBrokerModel).values(values))
        await self._session.commit()

        security_broker_model = await self._session.execute(
            select(SecurityBrokerModel)
            .where(
                SecurityBrokerModel.institution_id
                == security_broker.institution_id.value
            )
            .where(SecurityBrokerModel.broker_symbol == security_broker.broker_symbol)
            .where(
                SecurityBrokerModel.broker_exchange == security_broker.broker_exchange
            )
            .limit(1)
        )
        security_broker_model = security_broker_model.scalar_one()
        return SecurityBrokerSchema.model_validate(security_broker_model)


async def sqlalchemy_security_broker_repository_factory(
    container: Container,
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
        return [PriceSchema.model_validate(price) for price in prices.scalars()]

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
        if result is None:
            return None
        return PriceSchema.model_validate(result)

    @override
    async def save_price(self, price: PriceSchema) -> PriceSchema:
        price_dict = {k: v for k, v in price.model_dump().items() if k != "id"}
        price_model = PriceModel(**price_dict)
        self._session.add(price_model)
        await self._session.commit()
        await self._session.refresh(price_model)
        return PriceSchema.model_validate(price_model)

    @override
    async def save_prices(self, prices: list[PriceSchema]) -> list[PriceSchema]:
        if not prices:
            return []

        price_dicts = [
            {k: v for k, v in p.model_dump().items() if k != "id"} for p in prices
        ]
        stmt = insert(PriceModel).values(price_dicts)
        stmt = stmt.on_conflict_do_update(
            constraint="price_security_date_unique",
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "adjusted_close": stmt.excluded.adjusted_close,
                "volume": stmt.excluded.volume,
            },
        ).returning(PriceModel)

        result = await self._session.execute(stmt)
        schemas = [PriceSchema.model_validate(model) for model in result.scalars()]
        await self._session.commit()
        return schemas


async def sqlalchemy_price_repository_factory(
    container: Container,
) -> SqlAlchemyPriceRepository:
    return SqlAlchemyPriceRepository(
        session=await container.aget(AsyncSession),
    )


class SqlAlchemyWatchlistRepository(WatchlistRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    @override
    async def get_all_for_user(self, user_id: UserId) -> list[WatchlistRead]:
        result = await self._session.execute(
            select(WatchlistModel)
            .options(selectinload(WatchlistModel.securities))
            .where(WatchlistModel.user_id == user_id)
        )
        return [
            WatchlistRead.model_validate(watchlist) for watchlist in result.scalars()
        ]


async def sqlalchemy_watchlist_repository_factory(
    container: Container,
) -> SqlAlchemyWatchlistRepository:
    return SqlAlchemyWatchlistRepository(
        session=await container.aget(AsyncSession),
    )
