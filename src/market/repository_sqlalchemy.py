import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import override
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from svcs import Container

from src.auth.api_types import UserId
from src.core.enum import InstitutionEnum
from src.market.api_types import SecurityId, WatchlistId
from src.market.enum import WatchlistSortMode
from src.market.exception import (
    SecurityNotFoundError,
    WatchlistDuplicateNameError,
    WatchlistNotFoundError,
    WatchlistOrderIdentityError,
)
from src.market.model import (
    ChartSnapshotModel,
    IntradayPriceModel,
    PriceAlertModel,
    PriceModel,
    SecurityBrokerModel,
    SecurityDocumentModel,
    SecurityModel,
    SecurityNoteModel,
    SecurityValuationModel,
    WatchlistModel,
    WatchlistsSecuritiesModel,
)
from src.market.repository import (
    ChartSnapshotRepository,
    IntradayPriceRepository,
    PriceAlertRepository,
    PriceRepository,
    SecurityBrokerRepository,
    SecurityDocumentRepository,
    SecurityNoteRepository,
    SecurityRepository,
    SecurityValuationRepository,
    WatchlistRepository,
)
from src.market.schema import (
    AlertForEvaluation,
    ChartSnapshotCreate,
    ChartSnapshotRead,
    IntradayPriceSchema,
    PriceAlertRead,
    PriceAlertWrite,
    PriceSchema,
    SecurityBrokerSchema,
    SecurityDocumentRead,
    SecurityDocumentWrite,
    SecurityNoteRead,
    SecurityNoteWrite,
    SecuritySchema,
    SecurityValuationRead,
    SecurityValuationWrite,
    WatchlistRead,
    WatchlistSecuritySchema,
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
        values = security.model_dump(
            exclude={
                "current_price",
                "daily_price_change",
                "daily_price_change_percent",
            }
        )
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
    async def get_by_broker(
        self, institution_id: InstitutionEnum, broker_symbol: str, broker_exchange: str
    ) -> SecurityBrokerSchema | None:
        inst_val = (
            institution_id.value
            if hasattr(institution_id, "value")
            else int(institution_id)
        )
        existing = await self._session.execute(
            select(SecurityBrokerModel)
            .where(SecurityBrokerModel.institution_id == inst_val)
            .where(SecurityBrokerModel.broker_symbol == broker_symbol)
            .where(SecurityBrokerModel.broker_exchange == broker_exchange)
            .limit(1)
        )
        existing_broker = existing.scalar_one_or_none()

        if existing_broker is None:
            return None

        return SecurityBrokerSchema.model_validate(existing_broker)

    @override
    async def get_or_create(
        self, security_broker: SecurityBrokerSchema
    ) -> SecurityBrokerSchema:
        existing = await self.get_by_broker(
            institution_id=security_broker.institution_id,
            broker_symbol=security_broker.broker_symbol,
            broker_exchange=security_broker.broker_exchange,
        )

        if existing:
            return existing

        values = {
            k: v
            for k, v in security_broker.model_dump().items()
            if k not in ("id", "created_at")
        }
        values["institution_id"] = (
            security_broker.institution_id.value
            if hasattr(security_broker.institution_id, "value")
            else int(security_broker.institution_id)
        )
        await self._session.execute(insert(SecurityBrokerModel).values(values))
        await self._session.commit()

        created = await self.get_by_broker(
            institution_id=security_broker.institution_id,
            broker_symbol=security_broker.broker_symbol,
            broker_exchange=security_broker.broker_exchange,
        )
        assert created is not None
        return created


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
        self,
        security: SecuritySchema,
        from_date: date,
        to_date: date,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[PriceSchema], int]:
        base_query = (
            select(PriceModel)
            .where(PriceModel.security_id == security.id)
            .where(PriceModel.date >= from_date)
            .where(PriceModel.date <= to_date)
        )
        total = await self._session.scalar(
            select(func.count()).select_from(base_query.subquery())
        )
        prices = await self._session.execute(
            base_query.order_by(PriceModel.date).offset(offset).limit(limit)
        )
        return [
            PriceSchema.model_validate(price) for price in prices.scalars()
        ], total or 0

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


class SqlAlchemyIntradayPriceRepository(IntradayPriceRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    @override
    async def get_intraday_prices(
        self,
        security_id: SecurityId,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[IntradayPriceSchema]:
        stmt = select(IntradayPriceModel).where(
            IntradayPriceModel.security_id == security_id
        )
        if start_time is not None:
            stmt = stmt.where(IntradayPriceModel.timestamp >= start_time)
        if end_time is not None:
            stmt = stmt.where(IntradayPriceModel.timestamp <= end_time)
        stmt = stmt.order_by(IntradayPriceModel.timestamp.asc())
        result = await self._session.execute(stmt)
        return [IntradayPriceSchema.model_validate(model) for model in result.scalars()]

    @override
    async def save_intraday_price(
        self, price: IntradayPriceSchema
    ) -> IntradayPriceSchema:
        saved = await self.save_intraday_prices([price])
        return saved[0]

    @override
    async def save_intraday_prices(
        self, prices: list[IntradayPriceSchema]
    ) -> list[IntradayPriceSchema]:
        if not prices:
            return []

        price_dicts = [p.model_dump(exclude={"id"}) for p in prices]

        chunk_size = 1000
        schemas = []
        for i in range(0, len(price_dicts), chunk_size):
            chunk = price_dicts[i : i + chunk_size]
            stmt = insert(IntradayPriceModel).values(chunk)
            stmt = stmt.on_conflict_do_update(
                constraint="intraday_price_security_timestamp_unique",
                set_={
                    "open": stmt.excluded.open,
                    "high": stmt.excluded.high,
                    "low": stmt.excluded.low,
                    "close": stmt.excluded.close,
                    "volume": stmt.excluded.volume,
                },
            ).returning(IntradayPriceModel)

            result = await self._session.execute(stmt)
            schemas.extend(
                [
                    IntradayPriceSchema.model_validate(model)
                    for model in result.scalars()
                ]
            )

        await self._session.commit()
        return schemas

    @override
    async def get_latest_intraday_close_by_security(
        self,
    ) -> dict[SecurityId, Decimal]:
        # DISTINCT ON guarantees one row per security even if two bars
        # share the same timestamp.
        stmt = (
            select(
                IntradayPriceModel.security_id,
                IntradayPriceModel.close,
            )
            .distinct(IntradayPriceModel.security_id)
            .order_by(
                IntradayPriceModel.security_id,
                IntradayPriceModel.timestamp.desc(),
            )
        )

        result = await self._session.execute(stmt)
        return {row.security_id: row.close for row in result.mappings().all()}


async def sqlalchemy_intraday_price_repository_factory(
    container: Container,
) -> SqlAlchemyIntradayPriceRepository:
    return SqlAlchemyIntradayPriceRepository(
        session=await container.aget(AsyncSession),
    )


@dataclass(frozen=True)
class PriceMetrics:
    current_price: Decimal | None = None
    daily_price_change: Decimal | None = None
    daily_price_change_percent: Decimal | None = None


_LATEST_PRICES_LIMIT = 2


class SqlAlchemyWatchlistRepository(WatchlistRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    async def _fetch_price_metrics(
        self, security_ids: Iterable[SecurityId]
    ) -> dict[SecurityId, PriceMetrics]:
        id_list = list(security_ids)
        if not id_list:
            return {}

        rn_col = (
            func.row_number()
            .over(
                partition_by=PriceModel.security_id,
                order_by=(PriceModel.date.desc(), PriceModel.id.desc()),
            )
            .label("rn")
        )
        subq = (
            select(
                PriceModel.security_id,
                PriceModel.close,
                rn_col,
            )
            .where(PriceModel.security_id.in_(id_list))
            .subquery()
        )
        stmt = (
            select(
                subq.c.security_id,
                subq.c.close,
                subq.c.rn,
            )
            .where(subq.c.rn <= _LATEST_PRICES_LIMIT)
            .order_by(subq.c.security_id, subq.c.rn.asc())
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        prices_by_sec: dict[SecurityId, list[Decimal]] = {}
        for sec_id, close, _rn in rows:
            prices_by_sec.setdefault(sec_id, []).append(close)

        metrics: dict[SecurityId, PriceMetrics] = {}
        for sec_id, closes in prices_by_sec.items():
            if not closes:
                continue
            latest_close = closes[0]
            if len(closes) == 1:
                metrics[sec_id] = PriceMetrics(
                    current_price=latest_close,
                    daily_price_change=None,
                    daily_price_change_percent=None,
                )
            else:
                prev_close = closes[1]
                daily_change = latest_close - prev_close
                daily_change_pct = (
                    ((latest_close - prev_close) / prev_close) * Decimal(100)
                    if prev_close != Decimal(0)
                    else None
                )
                metrics[sec_id] = PriceMetrics(
                    current_price=latest_close,
                    daily_price_change=daily_change,
                    daily_price_change_percent=daily_change_pct,
                )

        return metrics

    def _enrich_security(
        self, security: SecuritySchema, metrics: dict[SecurityId, PriceMetrics]
    ) -> SecuritySchema:
        metric = metrics.get(security.id)
        if metric is None:
            return security
        return security.model_copy(
            update={
                "current_price": metric.current_price,
                "daily_price_change": metric.daily_price_change,
                "daily_price_change_percent": metric.daily_price_change_percent,
            }
        )

    async def _enrich_securities(
        self, securities: list[SecuritySchema]
    ) -> list[SecuritySchema]:
        if not securities:
            return securities
        metrics = await self._fetch_price_metrics({s.id for s in securities})
        return [self._enrich_security(s, metrics) for s in securities]

    async def _enrich_watchlists(
        self, watchlists: list[WatchlistRead]
    ) -> list[WatchlistRead]:
        if not watchlists:
            return watchlists
        all_securities = [s for w in watchlists for s in w.securities]
        if not all_securities:
            return watchlists
        metrics = await self._fetch_price_metrics({s.id for s in all_securities})
        return [
            watchlist.model_copy(
                update={
                    "securities": [
                        self._enrich_security(s, metrics) for s in watchlist.securities
                    ]
                }
            )
            for watchlist in watchlists
        ]

    async def _enrich_watchlist(self, watchlist: WatchlistRead) -> WatchlistRead:
        enriched = await self._enrich_watchlists([watchlist])
        return enriched[0]

    def _to_watchlist_security(
        self, security: SecurityModel, added_at: datetime, position: int
    ) -> WatchlistSecuritySchema:
        """Combine a security row with its membership metadata."""
        return WatchlistSecuritySchema(
            **SecuritySchema.model_validate(security).model_dump(),
            added_at=added_at,
            position=position,
        )

    async def _load_memberships(
        self, watchlist_ids: Iterable[WatchlistId]
    ) -> dict[WatchlistId, list[WatchlistSecuritySchema]]:
        """Load each watchlist's memberships ordered by ``position`` ascending.

        The ``secondary`` relationship cannot order by or carry the association
        columns (``position`` / ``added_at``), so the association table is
        queried explicitly, joined to the security rows.
        """
        id_list = list(watchlist_ids)
        if not id_list:
            return {}

        result = await self._session.execute(
            select(
                WatchlistsSecuritiesModel.watchlist_id,
                SecurityModel,
                WatchlistsSecuritiesModel.added_at,
                WatchlistsSecuritiesModel.position,
            )
            .join(
                SecurityModel,
                SecurityModel.id == WatchlistsSecuritiesModel.security_id,
            )
            .where(WatchlistsSecuritiesModel.watchlist_id.in_(id_list))
            .order_by(
                WatchlistsSecuritiesModel.position.asc(),
                WatchlistsSecuritiesModel.added_at.asc(),
            )
        )

        memberships: dict[WatchlistId, list[WatchlistSecuritySchema]] = {}
        for watchlist_id, security, added_at, position in result.all():
            memberships.setdefault(watchlist_id, []).append(
                self._to_watchlist_security(security, added_at, position)
            )
        return memberships

    async def _build_watchlist_reads(
        self, watchlist_models: Iterable[WatchlistModel]
    ) -> list[WatchlistRead]:
        """Build read schemas carrying ``sort`` and ordered membership metadata."""
        models = list(watchlist_models)
        memberships = await self._load_memberships(model.id for model in models)
        return [
            WatchlistRead(
                id=model.id,
                user_id=model.user_id,
                name=model.name,
                sort=model.sort,
                securities=memberships.get(model.id, []),
            )
            for model in models
        ]

    async def _build_watchlist_read(
        self, watchlist_model: WatchlistModel
    ) -> WatchlistRead:
        reads = await self._build_watchlist_reads([watchlist_model])
        return reads[0]

    @override
    async def get_by_user(self, user_id: UserId) -> list[WatchlistRead]:
        result = await self._session.execute(
            select(WatchlistModel).where(WatchlistModel.user_id == user_id)
        )
        watchlists = await self._build_watchlist_reads(result.scalars())
        return await self._enrich_watchlists(watchlists)

    async def _get_owned(
        self, watchlist_id: WatchlistId, user_id: UserId
    ) -> WatchlistModel:
        """Load a watchlist owned by ``user_id`` or raise ``WatchlistNotFoundError``."""
        result = await self._session.execute(
            select(WatchlistModel)
            .options(selectinload(WatchlistModel.securities))
            .where(WatchlistModel.id == watchlist_id)
            .where(WatchlistModel.user_id == user_id)
            .limit(1)
        )
        watchlist_model = result.scalar_one_or_none()
        if watchlist_model is None:
            raise WatchlistNotFoundError(watchlist_id)
        return watchlist_model

    async def _get_default_watchlist(self, user_id: UserId) -> WatchlistModel | None:
        """Load the user's ``Default`` watchlist, or ``None`` when absent."""
        result = await self._session.execute(
            select(WatchlistModel)
            .where(WatchlistModel.user_id == user_id)
            .where(WatchlistModel.name == "Default")
            .limit(1)
        )
        return result.scalar_one_or_none()

    @override
    async def create(self, user_id: UserId, name: str) -> WatchlistRead:
        watchlist = WatchlistModel(
            id=uuid.uuid4(),
            user_id=user_id,
            name=name,
            securities=[],
        )
        self._session.add(watchlist)
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise WatchlistDuplicateNameError(name) from None

        # reload to load relationships correctly
        result = await self._session.execute(
            select(WatchlistModel)
            .options(selectinload(WatchlistModel.securities))
            .where(WatchlistModel.id == watchlist.id)
        )
        watchlist_model = result.scalar_one()
        return await self._build_watchlist_read(watchlist_model)

    @override
    async def rename(
        self, watchlist_id: WatchlistId, user_id: UserId, name: str
    ) -> WatchlistRead:
        watchlist_model = await self._get_owned(watchlist_id, user_id)
        watchlist_model.name = name
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise WatchlistDuplicateNameError(name) from None

        return await self._enrich_watchlist(
            await self._build_watchlist_read(watchlist_model)
        )

    @override
    async def update_sort(
        self, watchlist_id: WatchlistId, user_id: UserId, sort: WatchlistSortMode
    ) -> WatchlistRead:
        watchlist_model = await self._get_owned(watchlist_id, user_id)
        watchlist_model.sort = sort.value
        await self._session.commit()

        return await self._enrich_watchlist(
            await self._build_watchlist_read(watchlist_model)
        )

    @override
    async def set_security_order(
        self,
        watchlist_id: WatchlistId,
        user_id: UserId,
        ordered_security_ids: list[SecurityId],
    ) -> WatchlistRead:
        watchlist_model = await self._get_owned(watchlist_id, user_id)

        result = await self._session.execute(
            select(
                WatchlistsSecuritiesModel.security_id,
                WatchlistsSecuritiesModel.position,
            ).where(WatchlistsSecuritiesModel.watchlist_id == watchlist_model.id)
        )
        memberships = result.all()
        current_ids = [security_id for security_id, _ in memberships]

        # ``set`` collapses duplicates, so the length check is what rejects a
        # payload that repeats a membership id. Validate everything *before*
        # writing so a rejected payload leaves every position untouched.
        if len(ordered_security_ids) != len(current_ids) or set(
            ordered_security_ids
        ) != set(current_ids):
            raise WatchlistOrderIdentityError

        current_order = [
            security_id
            for security_id, _ in sorted(
                memberships, key=lambda membership: membership[1]
            )
        ]
        if current_order != ordered_security_ids:
            for position, security_id in enumerate(ordered_security_ids):
                await self._session.execute(
                    update(WatchlistsSecuritiesModel)
                    .where(WatchlistsSecuritiesModel.watchlist_id == watchlist_model.id)
                    .where(WatchlistsSecuritiesModel.security_id == security_id)
                    .values(position=position)
                )
            await self._session.commit()

        return await self._enrich_watchlist(
            await self._build_watchlist_read(watchlist_model)
        )

    @override
    async def delete(self, watchlist_id: WatchlistId, user_id: UserId) -> None:
        watchlist_model = await self._get_owned(watchlist_id, user_id)
        await self._session.delete(watchlist_model)
        await self._session.commit()

    @override
    async def create_default(self, user_id: UserId) -> WatchlistRead:
        watchlist = WatchlistModel(
            id=uuid.uuid4(),
            user_id=user_id,
            name="Default",
            securities=[],
        )
        self._session.add(watchlist)
        await self._session.commit()

        # reload to load relationships correctly
        result = await self._session.execute(
            select(WatchlistModel)
            .options(selectinload(WatchlistModel.securities))
            .where(WatchlistModel.id == watchlist.id)
        )
        watchlist_model = result.scalar_one()
        return await self._enrich_watchlist(
            await self._build_watchlist_read(watchlist_model)
        )

    @override
    async def add_security_to_watchlist(
        self, watchlist_id: WatchlistId, user_id: UserId, security_id: SecurityId
    ) -> WatchlistRead:
        security_model = await self._session.get(SecurityModel, security_id)
        if security_model is None:
            raise SecurityNotFoundError(security_id)

        watchlist_model = await self._get_owned(watchlist_id, user_id)

        # The ``securities`` relationship cannot write the association columns
        # (``added_at`` / ``position``), so the membership is inserted explicitly.
        existing_membership = await self._session.scalar(
            select(WatchlistsSecuritiesModel.security_id)
            .where(WatchlistsSecuritiesModel.watchlist_id == watchlist_model.id)
            .where(WatchlistsSecuritiesModel.security_id == security_id)
            .limit(1)
        )
        if existing_membership is None:
            # ``position`` is application-managed: append after the watchlist's
            # current maximum. Not concurrency-safe under simultaneous adds,
            # which is acceptable for single-user watchlists.
            next_position = (
                select(
                    func.coalesce(func.max(WatchlistsSecuritiesModel.position), 0) + 1
                )
                .where(WatchlistsSecuritiesModel.watchlist_id == watchlist_model.id)
                .scalar_subquery()
            )
            await self._session.execute(
                insert(WatchlistsSecuritiesModel).values(
                    watchlist_id=watchlist_model.id,
                    security_id=security_id,
                    added_at=func.now(),
                    position=next_position,
                )
            )
            await self._session.commit()

        # Reload the watchlist so the ORM collection reflects the explicit
        # INSERT above (the loaded collection is stale otherwise).
        result = await self._session.execute(
            select(WatchlistModel)
            .options(selectinload(WatchlistModel.securities))
            .where(WatchlistModel.id == watchlist_model.id)
            .execution_options(populate_existing=True)
        )
        return await self._enrich_watchlist(
            await self._build_watchlist_read(result.scalar_one())
        )

    @override
    async def remove_security_from_watchlist(
        self, watchlist_id: WatchlistId, user_id: UserId, security_id: SecurityId
    ) -> WatchlistRead:
        security_model = await self._session.get(SecurityModel, security_id)
        if security_model is None:
            raise SecurityNotFoundError(security_id)

        watchlist_model = await self._get_owned(watchlist_id, user_id)

        if security_model in watchlist_model.securities:
            watchlist_model.securities.remove(security_model)
            await self._session.commit()

        # Reload with ``populate_existing`` so the in-session collection (stale
        # after the membership removal) reflects the persisted rows.
        result = await self._session.execute(
            select(WatchlistModel)
            .options(selectinload(WatchlistModel.securities))
            .where(WatchlistModel.id == watchlist_model.id)
            .execution_options(populate_existing=True)
        )
        return await self._enrich_watchlist(
            await self._build_watchlist_read(result.scalar_one())
        )

    @override
    async def add_security(
        self, user_id: UserId, security_id: SecurityId
    ) -> WatchlistRead:
        security_model = await self._session.get(SecurityModel, security_id)
        if security_model is None:
            raise SecurityNotFoundError(security_id)

        watchlist_model = await self._get_default_watchlist(user_id)
        if watchlist_model is None:
            watchlist_model = WatchlistModel(
                id=uuid.uuid4(),
                user_id=user_id,
                name="Default",
                securities=[],
            )
            self._session.add(watchlist_model)
            try:
                await self._session.flush()
            except IntegrityError:
                await self._session.rollback()
                existing = await self._get_default_watchlist(user_id)
                if existing is None:  # pragma: no cover - defensive re-raise
                    raise
                watchlist_model = existing

        return await self.add_security_to_watchlist(
            watchlist_model.id, user_id, security_id
        )

    @override
    async def remove_security(
        self, user_id: UserId, security_id: SecurityId
    ) -> WatchlistRead:
        security_model = await self._session.get(SecurityModel, security_id)
        if security_model is None:
            raise SecurityNotFoundError(security_id)

        watchlist_model = await self._get_default_watchlist(user_id)
        if watchlist_model is None:
            raise WatchlistNotFoundError(uuid.UUID(int=0))

        return await self.remove_security_from_watchlist(
            watchlist_model.id, user_id, security_id
        )

    @override
    async def get_securities(
        self, watchlist_id: uuid.UUID, user_id: UserId, offset: int = 0, limit: int = 50
    ) -> tuple[list[SecuritySchema], int]:
        # Validate that the watchlist belongs to the user
        result = await self._session.execute(
            select(WatchlistModel.id)
            .where(WatchlistModel.id == watchlist_id)
            .where(WatchlistModel.user_id == user_id)
            .limit(1)
        )
        found_watchlist_id = result.scalar_one_or_none()
        if not found_watchlist_id:
            raise WatchlistNotFoundError(watchlist_id)

        base_query = (
            select(SecurityModel)
            .join(WatchlistModel.securities)
            .where(WatchlistModel.id == found_watchlist_id)
        )
        total = await self._session.scalar(
            select(func.count()).select_from(base_query.subquery())
        )
        securities = await self._session.execute(
            base_query.order_by(SecurityModel.symbol).offset(offset).limit(limit)
        )
        sec_list = [SecuritySchema.model_validate(sec) for sec in securities.scalars()]
        enriched = await self._enrich_securities(sec_list)
        return enriched, total or 0


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
        self, security_id: SecurityId, user_id: UserId, offset: int = 0, limit: int = 50
    ) -> tuple[list[PriceAlertRead], int]:
        base_query = (
            select(PriceAlertModel)
            .where(PriceAlertModel.security_id == security_id)
            .where(PriceAlertModel.user_id == user_id)
        )
        total = await self._session.scalar(
            select(func.count()).select_from(base_query.subquery())
        )
        result = await self._session.execute(
            base_query.order_by(PriceAlertModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return [
            PriceAlertRead.model_validate(alert) for alert in result.scalars()
        ], total or 0

    @override
    async def create(
        self, alert: PriceAlertWrite, security_id: SecurityId, user_id: UserId
    ) -> PriceAlertRead:
        alert_model = PriceAlertModel(
            security_id=security_id,
            user_id=user_id,
            target_price=alert.target_price,
            condition=alert.condition,
            source=alert.source,
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

    @override
    async def get_active_alerts_for_evaluation(self) -> list[AlertForEvaluation]:
        result = await self._session.execute(
            select(
                PriceAlertModel.id,
                PriceAlertModel.security_id,
                PriceAlertModel.user_id,
                PriceAlertModel.target_price,
                PriceAlertModel.condition,
                SecurityModel.symbol,
                SecurityModel.name,
            )
            .join(
                SecurityModel,
                PriceAlertModel.security_id == SecurityModel.id,
            )
            .where(PriceAlertModel.triggered_at.is_(None))
        )
        return [
            AlertForEvaluation(
                alert_id=row.id,
                security_id=row.security_id,
                security_symbol=row.symbol,
                security_name=row.name,
                user_id=row.user_id,
                target_price=row.target_price,
                condition=row.condition,
            )
            for row in result.mappings().all()
        ]

    @override
    async def mark_triggered(self, alert_id: int, at: datetime) -> None:
        await self._session.execute(
            update(PriceAlertModel)
            .where(PriceAlertModel.id == alert_id)
            .values(triggered_at=at)
        )
        await self._session.commit()

    @override
    async def get_by_id(self, alert_id: int) -> PriceAlertRead | None:
        result = await self._session.execute(
            select(PriceAlertModel).where(PriceAlertModel.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        if alert is None:
            return None
        return PriceAlertRead.model_validate(alert)


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
        self, security_id: SecurityId, user_id: UserId, offset: int = 0, limit: int = 50
    ) -> tuple[list[SecurityNoteRead], int]:
        base_query = (
            select(SecurityNoteModel)
            .where(SecurityNoteModel.security_id == security_id)
            .where(SecurityNoteModel.user_id == user_id)
        )
        total = await self._session.scalar(
            select(func.count()).select_from(base_query.subquery())
        )
        result = await self._session.execute(
            base_query.order_by(SecurityNoteModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return [
            SecurityNoteRead.model_validate(note) for note in result.scalars()
        ], total or 0

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


class SqlAlchemyChartSnapshotRepository(ChartSnapshotRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    @override
    async def get_by_security_and_user(
        self, security_id: SecurityId, user_id: UserId
    ) -> list[ChartSnapshotRead]:
        result = await self._session.execute(
            select(ChartSnapshotModel)
            .where(ChartSnapshotModel.security_id == security_id)
            .where(ChartSnapshotModel.user_id == user_id)
            .order_by(ChartSnapshotModel.captured_at.asc())
        )
        return [
            ChartSnapshotRead.model_validate(snapshot) for snapshot in result.scalars()
        ]

    @override
    async def create(
        self, snapshot: ChartSnapshotCreate, security_id: SecurityId, user_id: UserId
    ) -> ChartSnapshotRead:
        captured_at = snapshot.captured_at or datetime.now(UTC)
        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=UTC)

        snapshot_model = ChartSnapshotModel(
            security_id=security_id,
            user_id=user_id,
            drawings=snapshot.drawings,
            data_window=snapshot.data_window,
            captured_at=captured_at,
        )
        self._session.add(snapshot_model)
        await self._session.commit()
        await self._session.refresh(snapshot_model)
        return ChartSnapshotRead.model_validate(snapshot_model)

    @override
    async def delete(self, snapshot_id: UUID, user_id: UserId) -> None:
        await self._session.execute(
            delete(ChartSnapshotModel)
            .where(ChartSnapshotModel.id == snapshot_id)
            .where(ChartSnapshotModel.user_id == user_id)
        )
        await self._session.commit()


async def sqlalchemy_chart_snapshot_repository_factory(
    container: Container,
) -> SqlAlchemyChartSnapshotRepository:
    return SqlAlchemyChartSnapshotRepository(
        session=await container.aget(AsyncSession),
    )


class SqlAlchemySecurityValuationRepository(SecurityValuationRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    @override
    async def get_by_security_and_user(
        self, security_id: SecurityId, user_id: UserId
    ) -> SecurityValuationRead | None:
        result = await self._session.execute(
            select(SecurityValuationModel)
            .where(SecurityValuationModel.security_id == security_id)
            .where(SecurityValuationModel.user_id == user_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return SecurityValuationRead.model_validate(model)

    @override
    async def upsert(
        self,
        valuation: SecurityValuationWrite,
        security_id: SecurityId,
        user_id: UserId,
    ) -> SecurityValuationRead:
        result = await self._session.execute(
            select(SecurityValuationModel)
            .where(SecurityValuationModel.security_id == security_id)
            .where(SecurityValuationModel.user_id == user_id)
        )
        model = result.scalar_one_or_none()
        now = datetime.now(UTC)
        if model is not None:
            model.lower_bound = valuation.lower_bound
            model.upper_bound = valuation.upper_bound
            model.updated_at = now
        else:
            model = SecurityValuationModel(
                security_id=security_id,
                user_id=user_id,
                lower_bound=valuation.lower_bound,
                upper_bound=valuation.upper_bound,
                created_at=now,
                updated_at=now,
            )
            self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return SecurityValuationRead.model_validate(model)

    @override
    async def get_batch_by_user_and_securities(
        self, security_ids: list[SecurityId], user_id: UserId
    ) -> list[SecurityValuationRead]:
        if not security_ids:
            return []
        result = await self._session.execute(
            select(SecurityValuationModel)
            .where(SecurityValuationModel.user_id == user_id)
            .where(SecurityValuationModel.security_id.in_(security_ids))
        )
        return [SecurityValuationRead.model_validate(m) for m in result.scalars()]


async def sqlalchemy_security_valuation_repository_factory(
    container: Container,
) -> SqlAlchemySecurityValuationRepository:
    return SqlAlchemySecurityValuationRepository(
        session=await container.aget(AsyncSession),
    )
