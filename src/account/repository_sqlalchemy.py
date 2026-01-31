from typing import override

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from svcs.fastapi import DepContainer

from src.account.api_types import AccountId
from src.account.model import AccountModel, PositionModel
from src.account.repository import AccountRepository, PositionRepository
from src.account.schema import AccountSchema, PositionSchema
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
