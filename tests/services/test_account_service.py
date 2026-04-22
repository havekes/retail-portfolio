from typing import override
from uuid import uuid4

import pytest
from stockholm import Currency

from src.account.api_types import AccountId
from src.account.enum import AccountTypeEnum, InstitutionEnum
from src.account.exception import AccountNotFoundError
from src.account.repository import AccountRepository
from src.account.schema import AccountSchema
from src.account.service.account import AccountService


class MockAccountRepository(AccountRepository):
    def __init__(self, accounts: list[AccountSchema] | None = None):
        self.accounts = accounts or []

    @override
    async def get(self, account_id: AccountId) -> AccountSchema | None:
        for account in self.accounts:
            if account.id == account_id:
                return account
        return None

    @override
    async def create(self, account: AccountSchema) -> AccountSchema:
        self.accounts.append(account)
        return account

    @override
    async def rename(self, account_id: AccountId, new_name: str) -> AccountSchema:
        for account in self.accounts:
            if account.id == account_id:
                account.name = new_name
                return account
        raise ValueError

    @override
    async def exists_by_user_and_broker_id(self, user_id, broker_id) -> bool:
        return False

    @override
    async def get_by_user(self, user_id) -> list[AccountSchema]:
        return []

    @override
    async def delete(self, account_id: AccountId) -> None:
        self.accounts = [a for a in self.accounts if a.id != account_id]

    @override
    async def update_net_deposits(
        self, account_id: AccountId, net_deposits: float | None
    ) -> None:
        pass


@pytest.mark.anyio
async def test_get_account_success():
    account_id = uuid4()
    account = AccountSchema(
        id=account_id,
        external_id="broker-123",
        name="Test Account",
        user_id=uuid4(),
        account_type_id=AccountTypeEnum.TFSA,
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        currency=Currency.USD,
    )
    repo = MockAccountRepository([account])
    service = AccountService(account_repository=repo)

    result = await service.get_account(account_id)

    assert result == account


@pytest.mark.anyio
async def test_get_account_not_found():
    repo = MockAccountRepository([])
    service = AccountService(account_repository=repo)
    account_id = uuid4()

    with pytest.raises(AccountNotFoundError):
        await service.get_account(account_id)
