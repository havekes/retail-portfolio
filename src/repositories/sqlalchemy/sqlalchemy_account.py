from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from svcs import Container

from src.models.account import Account as AccountModel
from src.repositories.account import AccountRepository
from src.schemas import Account


class SqlAlchemyAccountRepostory(AccountRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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


async def sqlalchemy_account_repository_factory(
    container: Container,
) -> SqlAlchemyAccountRepostory:
    return SqlAlchemyAccountRepostory(session=await container.aget(AsyncSession))
