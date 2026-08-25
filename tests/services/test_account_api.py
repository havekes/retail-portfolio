from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from stockholm import Currency

from src.account.api.account import AccountApi
from src.account.repository import AccountRepository
from src.account.schema import AccountSchema
from src.core.enum import AccountTypeEnum, InstitutionEnum


@pytest.mark.asyncio
async def test_update_net_deposits_delegates_to_repository():
    mock_repo = AsyncMock(spec=AccountRepository)
    api = AccountApi(account_repository=mock_repo)
    account_id = uuid4()
    net_deposits = 12500.50

    await api.update_net_deposits(account_id, net_deposits)

    mock_repo.update_net_deposits.assert_awaited_once_with(account_id, net_deposits)


@pytest.mark.asyncio
async def test_update_net_deposits_with_none_delegates_to_repository():
    mock_repo = AsyncMock(spec=AccountRepository)
    api = AccountApi(account_repository=mock_repo)
    account_id = uuid4()

    await api.update_net_deposits(account_id, None)

    mock_repo.update_net_deposits.assert_awaited_once_with(account_id, None)


@pytest.mark.asyncio
async def test_update_last_sync_at_delegates_to_repository():
    mock_repo = AsyncMock(spec=AccountRepository)
    api = AccountApi(account_repository=mock_repo)
    account_id = uuid4()

    await api.update_last_sync_at(account_id)

    mock_repo.update_last_sync_at.assert_awaited_once_with(account_id)


@pytest.mark.asyncio
async def test_get_all_delegates_to_repository():
    mock_repo = AsyncMock(spec=AccountRepository)
    user_id = uuid4()
    account_schema = AccountSchema(
        id=uuid4(),
        external_id="broker-123",
        name="TFSA Account",
        user_id=user_id,
        account_type_id=AccountTypeEnum.TFSA,
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        currency=Currency.CAD,
    )
    mock_repo.get_by_user.return_value = [account_schema]
    api = AccountApi(account_repository=mock_repo)

    accounts = await api.get_all(user_id)

    mock_repo.get_by_user.assert_awaited_once_with(user_id)
    assert len(accounts) == 1
    assert accounts[0].id == account_schema.id


@pytest.mark.asyncio
async def test_get_by_id_delegates_to_repository():
    mock_repo = AsyncMock(spec=AccountRepository)
    account_id = uuid4()
    account_schema = AccountSchema(
        id=account_id,
        external_id="broker-123",
        name="TFSA Account",
        user_id=uuid4(),
        account_type_id=AccountTypeEnum.TFSA,
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        currency=Currency.CAD,
    )
    mock_repo.get.return_value = account_schema
    api = AccountApi(account_repository=mock_repo)

    account = await api.get_by_id(account_id)

    mock_repo.get.assert_awaited_once_with(account_id)
    assert account is not None
    assert account.id == account_id
