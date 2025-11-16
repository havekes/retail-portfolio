from abc import ABC, abstractmethod

from src.schemas.account_type import AccountType


class AccountTypeRepository(ABC):
    @abstractmethod
    async def get_account_type(self, account_type_id: int) -> AccountType | None:
        pass
