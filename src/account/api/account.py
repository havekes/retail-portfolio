import uuid
from typing import cast

import svcs
from svcs import Container

from src.account.api_types import Account
from src.account.repository import AccountRepository
from src.account.schema import AccountSchema
from src.auth.api_types import UserId
from src.integration.api_types import IntegrationUserId
from src.integration.brokers.api_types import BrokerAccount


class AccountApi:
    _account_repository: AccountRepository

    def __init__(self, account_repository: AccountRepository) -> None:
        self._account_repository = account_repository

    async def get_all(self, user_id: UserId) -> list[Account]:
        """Get all accounts for a user."""
        return [
            Account.model_validate(a)
            for a in await self._account_repository.get_by_user(user_id)
        ]

    async def get_by_id(self, account_id: uuid.UUID) -> Account | None:
        """Get an account by ID."""
        account = await self._account_repository.get(account_id)
        return Account.model_validate(account) if account else None

    async def get_broker_id_by_id(self, account_id: uuid.UUID) -> str | None:
        """Get the broker ID for an account."""
        account = await self._account_repository.get(account_id)
        return account.external_id if account else None

    async def rename(self, account_id: uuid.UUID, name: str) -> Account:
        """Rename an account."""
        account = await self._account_repository.rename(account_id, name)
        return Account.model_validate(account)

    async def import_from_broker(
        self,
        broker_accounts: list[BrokerAccount],
        user_id: UserId,
        integration_user_id: IntegrationUserId,
    ) -> list[Account]:
        """Import accounts from a broker, avoiding duplicates for the user."""
        accounts: list[Account] = []

        for broker_account in broker_accounts:
            exists = await self._account_repository.exists_by_user_and_broker_id(
                user_id=user_id,
                broker_id=broker_account.id,
            )
            # TODO This method should update the account `net_deposits`
            # when it already exists
            if exists is True:
                continue

            account = AccountSchema.from_broker(
                broker_account, user_id, integration_user_id
            )
            accounts.append(
                Account.model_validate(await self._account_repository.create(account))
            )

        return accounts


async def account_api_factory(container: Container) -> AccountApi:
    return AccountApi(
        account_repository=await container.aget(AccountRepository),
    )
