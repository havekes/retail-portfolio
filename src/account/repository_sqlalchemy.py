from typing import override

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from svcs.fastapi import DepContainer

from src.account.api_types import AccountId, PortfolioId
from src.account.model import (
    AccountModel,
    PortfolioAccountModel,
    PortfolioModel,
    PositionModel,
)
from src.account.repository import (
    AccountRepository,
    PortfolioRepository,
    PositionRepository,
)
from src.account.schema import (
    AccountSchema,
    PortfolioCreate,
    PortfolioRead,
    PositionSchema,
)
from src.auth.api_types import UserId
from src.integration.brokers.api_types import BrokerAccountId


class SqlAlchemyAccountRepository(AccountRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @override
    async def get(self, account_id: AccountId) -> AccountSchema | None:
        q = select(AccountModel).where(AccountModel.id == account_id)
        result = await self._session.execute(q)
        account_model = result.scalar_one_or_none()
        if account_model is None:
            return None
        return AccountSchema.model_validate(account_model)

    @override
    async def create(self, account: AccountSchema) -> AccountSchema:
        account_model = AccountModel(**account.model_dump())
        self._session.add(account_model)
        await self._session.commit()
        return AccountSchema.model_validate(account_model)

    @override
    async def rename(self, account_id: AccountId, new_name: str) -> AccountSchema:
        account_model = await self._session.get(AccountModel, account_id)
        if account_model is None:
            error = f"Account with id {account_id} not found"
            raise ValueError(error)

        account_model.name = new_name
        await self._session.commit()
        await self._session.refresh(account_model)

        return AccountSchema.model_validate(account_model)

    @override
    async def exists_by_user_and_broker_id(
        self, user_id: UserId, broker_id: BrokerAccountId
    ) -> bool:
        q = select(AccountModel).where(
            AccountModel.user_id == user_id, AccountModel.external_id == broker_id
        )

        return bool(await self._session.scalar(select(q.exists())))

    @override
    async def get_by_user(self, user_id: UserId) -> list[AccountSchema]:
        q = select(AccountModel).where(AccountModel.user_id == user_id)
        result = await self._session.execute(q)
        account_models = result.scalars().all()
        return [
            AccountSchema.model_validate(account_model)
            for account_model in account_models
        ]


async def sqlalchemy_account_repository_factory(
    container: DepContainer,
) -> SqlAlchemyAccountRepository:
    return SqlAlchemyAccountRepository(session=await container.aget(AsyncSession))


class SqlAlchemyPositionRepository(PositionRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @override
    async def get_by_account(self, account_id: AccountId) -> list[PositionSchema]:
        query = select(PositionModel).where(
            PositionModel.account_id == account_id,
        )
        result = await self._session.execute(query)
        position_models = result.scalars().all()
        return [
            PositionSchema.model_validate(position_model)
            for position_model in position_models
        ]


async def sqlalchemy_position_repository_factory(
    container: DepContainer,
) -> SqlAlchemyPositionRepository:
    return SqlAlchemyPositionRepository(session=await container.aget(AsyncSession))


class SqlAlchemyPortfolioRepository(PortfolioRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @override
    async def get(self, portfolio_id: PortfolioId) -> PortfolioRead | None:
        q = (
            select(PortfolioModel)
            .where(PortfolioModel.id == portfolio_id)
            .options(
                selectinload(PortfolioModel.portfolio_accounts).selectinload(
                    PortfolioAccountModel.account
                )
            )
        )
        result = await self._session.execute(q)
        portfolio_model = result.scalar_one_or_none()
        if portfolio_model is None:
            return None
        return self._to_portfolio_read_schema(portfolio_model)

    @override
    async def get_by_user(self, user_id: UserId) -> list[PortfolioRead]:
        q = (
            select(PortfolioModel)
            .where(PortfolioModel.user_id == user_id)
            .options(
                selectinload(PortfolioModel.portfolio_accounts).selectinload(
                    PortfolioAccountModel.account
                )
            )
        )
        result = await self._session.execute(q)
        portfolio_models = result.scalars().all()
        return [self._to_portfolio_read_schema(pm) for pm in portfolio_models]

    @override
    async def create(
        self, user_id: UserId, portfolio_create: PortfolioCreate
    ) -> PortfolioRead:
        portfolio_model = PortfolioModel(user_id=user_id, name=portfolio_create.name)
        self._session.add(portfolio_model)
        await self._session.flush()  # To get portfolio_model.id

        for account_id in portfolio_create.accounts:
            portfolio_account = PortfolioAccountModel(
                portfolio_id=portfolio_model.id, account_id=account_id
            )
            self._session.add(portfolio_account)

        await self._session.commit()
        await self._session.refresh(portfolio_model)  # Refresh to load relationships

        # Fetch the newly created portfolio with its accounts
        portfolio = await self.get(portfolio_model.id)
        assert portfolio is not None, "Portfolio should exist after creation"
        return portfolio

    @override
    async def update_accounts(
        self, portfolio_id: PortfolioId, account_ids: list[AccountId]
    ) -> PortfolioRead:
        # Delete existing portfolio accounts
        await self._session.run_sync(
            lambda session: (
                _ := session.query(PortfolioAccountModel)
                .filter(PortfolioAccountModel.portfolio_id == portfolio_id)
                .delete(),
                None,
            )[1]
        )

        # Add new portfolio accounts
        for account_id in account_ids:
            portfolio_account = PortfolioAccountModel(
                portfolio_id=portfolio_id, account_id=account_id
            )
            self._session.add(portfolio_account)

        await self._session.commit()
        portfolio = await self.get(portfolio_id)
        assert portfolio is not None, "Portfolio should exist after update"
        return portfolio

    @override
    async def delete(self, portfolio_id: PortfolioId) -> None:
        portfolio_model = await self._session.get(PortfolioModel, portfolio_id)
        if portfolio_model:
            await self._session.delete(portfolio_model)
            await self._session.commit()

    def _to_portfolio_read_schema(
        self, portfolio_model: PortfolioModel
    ) -> PortfolioRead:
        accounts = [
            AccountSchema.model_validate(pa.account)
            for pa in portfolio_model.portfolio_accounts
        ]
        return PortfolioRead(
            id=portfolio_model.id,
            user_id=portfolio_model.user_id,
            name=portfolio_model.name,
            created_at=portfolio_model.created_at,
            deleted_at=portfolio_model.deleted_at,
            accounts=accounts,
        )


async def sqlalchemy_portfolio_repository_factory(
    container: DepContainer,
) -> SqlAlchemyPortfolioRepository:
    return SqlAlchemyPortfolioRepository(session=await container.aget(AsyncSession))
