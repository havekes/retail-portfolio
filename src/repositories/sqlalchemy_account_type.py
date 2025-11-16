from sqlalchemy.ext.asyncio import AsyncSession

from src.models.account_type import AccountType as AccountTypeModel
from src.repositories.account_type import AccountTypeRepository
from src.schemas.account_type import AccountType


class SqlAlchemyAccountTypeRepository(AccountTypeRepository):
    session: AsyncSession

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_account_type(self, account_type_id: int) -> AccountType | None:
        result = await self.session.get(AccountTypeModel, account_type_id)
        if result:
            return AccountType.model_validate(result)
        return None
