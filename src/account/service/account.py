from svcs import Container

from src.account.api_types import AccountId
from src.account.exception import AccountNotFoundError, AccountsDoNotBelongToUserError
from src.account.repository import (
    AccountRepository,
)
from src.account.schema import AccountSchema
from src.auth.api_types import UserId


class AccountService:
    _account_repository: AccountRepository

    def __init__(
        self,
        account_repository: AccountRepository,
    ):
        self._account_repository = account_repository

    async def get_account(self, account_id: AccountId) -> AccountSchema:
        """Get an account by its ID."""
        account = await self._account_repository.get(account_id)
        if not account:
            raise AccountNotFoundError(account_id)
        return account

    async def check_accounts_belong_to_user(
        self,
        account_ids: list[AccountId],
        user_id: UserId,
    ) -> None:
        """Verify that the provided account IDs belong to the specified user."""
        user_accounts = await self._account_repository.get_by_user(user_id)
        user_account_ids = {account.id for account in user_accounts}
        if not user_account_ids.issuperset(set(account_ids)):
            raise AccountsDoNotBelongToUserError(account_ids=account_ids)

    async def delete_account(self, account_id: AccountId) -> None:
        """Delete an account by its ID."""
        await self._account_repository.delete(account_id)


async def account_service_factory(container: Container) -> AccountService:
    return AccountService(
        account_repository=await container.aget(AccountRepository),
    )
