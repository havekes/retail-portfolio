from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from svcs import Container

from src.models.account import Account as AccountModel
from src.repositories.account import AccountRepository
from src.schemas import Account


class SqlAlchemyAccountRepository(AccountRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, account_id: UUID) -> Account | None:
        q = select(AccountModel).where(AccountModel.id == account_id)
        result = await self._session.execute(q)
        account_model = result.scalar_one_or_none()
        if account_model is None:
            return None
        return Account.model_validate(account_model)

    async def create_account(self, account: Account) -> Account:
        account_model = AccountModel(**account.model_dump())
        self._session.add(account_model)
        await self._session.commit()
        return account

    async def exists_by_user_and_external_id(
        self, user_id: UUID, external_id: str
    ) -> bool:
        q = select(AccountModel).where(
            AccountModel.user_id == user_id, AccountModel.external_id == external_id
        )

        return bool(await self._session.scalar(select(q.exists())))

    async def get_by_user(self, user_id: UUID) -> list[Account]:
        q = select(AccountModel).where(AccountModel.user_id == user_id)
        result = await self._session.execute(q)
        account_models = result.scalars().all()
        return [
            Account.model_validate(account_model) for account_model in account_models
        ]


async def sqlalchemy_account_repository_factory(
    container: Container,
) -> SqlAlchemyAccountRepository:
    return SqlAlchemyAccountRepository(session=await container.aget(AsyncSession))
