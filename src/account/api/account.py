from svcs import Container

from src.account.api_types import Account, AccountId
from src.account.repository import AccountRepository
from src.account.schema import AccountSchema
from src.auth.api_types import UserId
from src.integration.brokers.api_types import BrokerAccount


class AccountApi:
    _account_repository: AccountRepository

    def __init__(self, account_repository: AccountRepository) -> None:
        self._account_repository = account_repository

    async def get_by_id(self, account_id: AccountId) -> Account | None:
        account = await self._account_repository.get(account_id)
        if account is None:
            return None
        return Account.model_validate(account)

    async def get_broker_id_by_id(self, account_id: AccountId):
        account = await self._account_repository.get(account_id)
        if account is None:
            return None
        return account.external_id

    async def import_from_broker(
        self, broker_accounts: list[BrokerAccount], user_id: UserId
    ) -> list[Account]:
        accounts: list[Account] = []
        for broker_account in broker_accounts:
            exists = await self._account_repository.exists_by_user_and_broker_id(
                user_id=user_id,
                broker_id=broker_account.id,
            )
            if exists is True:
                continue

            account = AccountSchema.from_broker(broker_account, user_id)
            accounts.append(
                Account.model_validate(await self._account_repository.create(account))
            )

        return accounts


async def account_api_factory(container: Container) -> AccountApi:
    return AccountApi(
        account_repository=await container.aget(AccountRepository),
    )
