from svcs import Container

from src.account.api_types import Account, AccountId
from src.account.repository import AccountRepository
from src.account.repository_sqlalchemy import sqlalchemy_account_repository_factory


class AccountApi:
    _account_repository: AccountRepository

    def __init__(self, account_repository: AccountRepository) -> None:
        self._account_repository = account_repository

    async def get_by_id(self, account_id: AccountId):
        account = self._account_repository.get(account_id)

        return Account.model_validate(account)


async def account_api_factory(container: Container):
    return AccountApi(
        account_repository=await sqlalchemy_account_repository_factory(container),
    )
