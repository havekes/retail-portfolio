from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.account import Account as AccountModel
from src.repositories.account import AccountRepository
from src.schemas import Account


class SqlAlchemyAccountRepostory(AccountRepository):
    session: AsyncSession

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_account(self, account: Account) -> Account:
        account_model = AccountModel(**account.model_dump())
        self.session.add(account_model)
        await self.session.commit()
        return account

    async def exists_account_by_user_and_external_id(
        self, user_id: UUID, external_id: str
    ) -> bool:
        q = select(AccountModel).where(
            AccountModel.user_id == user_id, AccountModel.external_id == external_id
        )

        return bool(await self.session.scalar(select(q.exists())))
