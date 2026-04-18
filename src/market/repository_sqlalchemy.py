import uuid
from datetime import date
from typing import override

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from svcs import Container

from src.auth.api_types import UserId
from src.market.api_types import SecurityId
from src.market.exception import SecurityNotFoundError
from src.market.model import (
    IndicatorPreferencesModel,
    PriceAlertModel,
    PriceModel,
    SecurityBrokerModel,
    SecurityDocumentModel,
    SecurityModel,
    SecurityNoteModel,
    WatchlistModel,
)
from src.market.repository import (
    IndicatorPreferencesRepository,
    PriceAlertRepository,
    PriceRepository,
    SecurityBrokerRepository,
    SecurityDocumentRepository,
    SecurityNoteRepository,
    SecurityRepository,
    WatchlistRepository,
)
from src.market.schema import (
    IndicatorPreferencesRead,
    IndicatorPreferencesWrite,
    PriceAlertRead,
    PriceAlertWrite,
    PriceSchema,
    SecurityBrokerSchema,
    SecurityDocumentRead,
    SecurityDocumentWrite,
    SecurityNoteRead,
    SecurityNoteWrite,
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

    @override
    async def get_by_code_and_exchange(
        self, code: str, exchange: str
    ) -> SecuritySchema | None:
        result = await self._session.execute(
            select(SecurityModel)
            .where(SecurityModel.symbol == code)
            .where(SecurityModel.exchange == exchange)
            .limit(1)
        )
        security_model = result.scalar_one_or_none()
        if security_model is None:
            return None
        return SecuritySchema.model_validate(security_model)


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
    async def get_by_security(self, security_id: SecurityId) -> list[PriceSchema]:
        prices = await self._session.execute(
            select(PriceModel)
            .where(PriceModel.security_id == security_id)
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

        chunk_size = 1000
        schemas = []
        for i in range(0, len(price_dicts), chunk_size):
            chunk = price_dicts[i : i + chunk_size]
            stmt = insert(PriceModel).values(chunk)
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
            schemas.extend(
                [PriceSchema.model_validate(model) for model in result.scalars()]
            )

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
    async def get_by_user(self, user_id: UserId) -> list[WatchlistRead]:
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


class SqlAlchemyPriceAlertRepository(PriceAlertRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    @override
    async def get_by_security_and_user(
        self, security_id: SecurityId, user_id: UserId
    ) -> list[PriceAlertRead]:
        result = await self._session.execute(
            select(PriceAlertModel)
            .where(PriceAlertModel.security_id == security_id)
            .where(PriceAlertModel.user_id == user_id)
            .order_by(PriceAlertModel.created_at.desc())
        )
        return [PriceAlertRead.model_validate(alert) for alert in result.scalars()]

    @override
    async def create(
        self, alert: PriceAlertWrite, security_id: SecurityId, user_id: UserId
    ) -> PriceAlertRead:
        alert_model = PriceAlertModel(
            security_id=security_id,
            user_id=user_id,
            target_price=alert.target_price,
            condition=alert.condition,
        )
        self._session.add(alert_model)
        await self._session.commit()
        await self._session.refresh(alert_model)
        return PriceAlertRead.model_validate(alert_model)

    @override
    async def delete(self, alert_id: int, user_id: UserId) -> None:
        await self._session.execute(
            delete(PriceAlertModel)
            .where(PriceAlertModel.id == alert_id)
            .where(PriceAlertModel.user_id == user_id)
        )
        await self._session.commit()


async def sqlalchemy_price_alert_repository_factory(
    container: Container,
) -> SqlAlchemyPriceAlertRepository:
    return SqlAlchemyPriceAlertRepository(
        session=await container.aget(AsyncSession),
    )


class SqlAlchemySecurityNoteRepository(SecurityNoteRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    @override
    async def get_by_security_and_user(
        self, security_id: SecurityId, user_id: UserId
    ) -> list[SecurityNoteRead]:
        result = await self._session.execute(
            select(SecurityNoteModel)
            .where(SecurityNoteModel.security_id == security_id)
            .where(SecurityNoteModel.user_id == user_id)
            .order_by(SecurityNoteModel.created_at.desc())
        )
        return [SecurityNoteRead.model_validate(note) for note in result.scalars()]

    @override
    async def get_by_id(self, note_id: int) -> SecurityNoteRead | None:
        result = await self._session.execute(
            select(SecurityNoteModel).where(SecurityNoteModel.id == note_id)
        )
        note = result.scalar_one_or_none()
        return SecurityNoteRead.model_validate(note) if note else None

    @override
    async def create(
        self, note: SecurityNoteWrite, security_id: SecurityId, user_id: UserId
    ) -> SecurityNoteRead:
        note_model = SecurityNoteModel(
            security_id=security_id,
            user_id=user_id,
            title=note.title,
            content=note.content,
        )
        self._session.add(note_model)
        await self._session.commit()
        await self._session.refresh(note_model)
        return SecurityNoteRead.model_validate(note_model)

    @override
    async def update(
        self, note_id: int, note: SecurityNoteWrite, user_id: UserId
    ) -> SecurityNoteRead:
        result = await self._session.execute(
            select(SecurityNoteModel)
            .where(SecurityNoteModel.id == note_id)
            .where(SecurityNoteModel.user_id == user_id)
        )
        note_model = result.scalar_one_or_none()
        if note_model is None:
            msg = f"Note {note_id} not found"
            raise ValueError(msg)
        if note.title is not None:
            note_model.title = note.title
        note_model.content = note.content
        await self._session.commit()
        await self._session.refresh(note_model)
        return SecurityNoteRead.model_validate(note_model)

    @override
    async def update_title(self, note_id: int, title: str) -> None:
        result = await self._session.execute(
            select(SecurityNoteModel).where(SecurityNoteModel.id == note_id)
        )
        note_model = result.scalar_one_or_none()
        if note_model:
            note_model.title = title
            await self._session.commit()

    @override
    async def delete(self, note_id: int, user_id: UserId) -> None:
        await self._session.execute(
            delete(SecurityNoteModel)
            .where(SecurityNoteModel.id == note_id)
            .where(SecurityNoteModel.user_id == user_id)
        )
        await self._session.commit()


async def sqlalchemy_security_note_repository_factory(
    container: Container,
) -> SqlAlchemySecurityNoteRepository:
    return SqlAlchemySecurityNoteRepository(
        session=await container.aget(AsyncSession),
    )


class SqlAlchemySecurityDocumentRepository(SecurityDocumentRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    @override
    async def get_by_security_and_user(
        self, security_id: SecurityId, user_id: UserId
    ) -> list[SecurityDocumentRead]:
        result = await self._session.execute(
            select(SecurityDocumentModel)
            .where(SecurityDocumentModel.security_id == security_id)
            .where(SecurityDocumentModel.user_id == user_id)
            .order_by(SecurityDocumentModel.created_at.desc())
        )
        return [SecurityDocumentRead.model_validate(doc) for doc in result.scalars()]

    @override
    async def create(
        self,
        document: SecurityDocumentWrite,
        security_id: SecurityId,
        user_id: UserId,
    ) -> SecurityDocumentRead:
        doc_model = SecurityDocumentModel(
            security_id=security_id,
            user_id=user_id,
            filename=document.filename,
            file_path=document.file_path,
            file_size=document.file_size,
            file_type=document.file_type,
        )
        self._session.add(doc_model)
        await self._session.commit()
        await self._session.refresh(doc_model)
        return SecurityDocumentRead.model_validate(doc_model)

    @override
    async def delete(self, document_id: int, user_id: UserId) -> None:
        await self._session.execute(
            delete(SecurityDocumentModel)
            .where(SecurityDocumentModel.id == document_id)
            .where(SecurityDocumentModel.user_id == user_id)
        )
        await self._session.commit()


async def sqlalchemy_security_document_repository_factory(
    container: Container,
) -> SqlAlchemySecurityDocumentRepository:
    return SqlAlchemySecurityDocumentRepository(
        session=await container.aget(AsyncSession),
    )


class SqlAlchemyIndicatorPreferencesRepository(IndicatorPreferencesRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    @override
    async def get_for_security_and_user(
        self, security_id: SecurityId, user_id: UserId
    ) -> IndicatorPreferencesRead | None:
        result = await self._session.execute(
            select(IndicatorPreferencesModel)
            .where(IndicatorPreferencesModel.security_id == security_id)
            .where(IndicatorPreferencesModel.user_id == user_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return IndicatorPreferencesRead.model_validate(model)

    @override
    async def save(
        self,
        preferences: IndicatorPreferencesWrite,
        security_id: SecurityId,
        user_id: UserId,
    ) -> IndicatorPreferencesRead:
        existing = await self.get_for_security_and_user(security_id, user_id)
        if existing:
            result = await self._session.execute(
                select(IndicatorPreferencesModel)
                .where(IndicatorPreferencesModel.security_id == security_id)
                .where(IndicatorPreferencesModel.user_id == user_id)
            )
            model = result.scalar_one()
            model.indicators_json = preferences.indicators_json
        else:
            model = IndicatorPreferencesModel(
                security_id=security_id,
                user_id=user_id,
                indicators_json=preferences.indicators_json,
            )
            self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return IndicatorPreferencesRead.model_validate(model)


async def sqlalchemy_indicator_preferences_repository_factory(
    container: Container,
) -> SqlAlchemyIndicatorPreferencesRepository:
    return SqlAlchemyIndicatorPreferencesRepository(
        session=await container.aget(AsyncSession),
    )
