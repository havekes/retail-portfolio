import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from datetime import datetime, UTC
from decimal import Decimal
from typing import cast

import pytest
from stockholm import Currency

from src.account.api_types import Account
from src.account.enum import AccountTypeEnum, InstitutionEnum
from src.integration.brokers import BrokerApiGateway
from src.integration.brokers.api_types import BrokerPosition
from src.integration.exception import (
    AccountPositionsSyncError,
    IntegrationUserNotFoundError,
)
from src.integration.repository import IntegrationUserRepository
from src.integration.schema import IntegrationUserSchema
from src.integration.task import _sync_account_positions_task, sync_account_positions_task
from src.market.api import SecurityApi
from src.market.api_types import Security
from src.worker import huey

@pytest.fixture
def mock_account():
    return Account(
        id=uuid4(),
        name="Test Account",
        user_id=uuid4(),
        integration_user_id=uuid4(),
        account_type_id=AccountTypeEnum.TFSA,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        currency=Currency.CAD,
    )

@pytest.fixture
def mock_integration_user(mock_account):
    return IntegrationUserSchema(
        id=mock_account.integration_user_id,
        user_id=mock_account.user_id,
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        external_user_id="external-id",
    )

@pytest.mark.asyncio
async def test_sync_account_positions_task_success(mock_account, mock_integration_user):
    user_id = mock_account.user_id
    broker_account_id = "broker-account-id"
    broker_class = cast(type[BrokerApiGateway], MagicMock())

    mock_security_api = AsyncMock(spec=SecurityApi)
    mock_integration_user_repo = AsyncMock(spec=IntegrationUserRepository)
    mock_broker = AsyncMock()

    mock_integration_user_repo.get.return_value = mock_integration_user
    
    mock_security = Security(
        id=uuid4(),
        symbol="AAPL",
        exchange="NASDAQ",
        name="Apple Inc.",
        currency=Currency.USD,
        isin=None,
        is_active=True,
        updated_at=datetime.now(UTC)
    )
    mock_security_api.get_or_create_from_broker.return_value = mock_security

    mock_broker_position = BrokerPosition(
        broker_account_id=broker_account_id,
        name="Apple Inc.",
        symbol="AAPL",
        exchange="NASDAQ",
        quantity=Decimal("10"),
        average_cost=Decimal("150"),
    )
    mock_broker.get_positions_by_account.return_value = [mock_broker_position]

    mock_container = AsyncMock()
    async def mock_aget(clazz):
        if clazz == SecurityApi:
            return mock_security_api
        if clazz == IntegrationUserRepository:
            return mock_integration_user_repo
        if clazz == broker_class:
            return mock_broker
        return None
    mock_container.aget.side_effect = mock_aget

    with (
        patch("src.integration.task.huey.svcs_container", mock_container),
        patch("src.integration.task.ws_manager", AsyncMock()) as mock_ws,
    ):
        await _sync_account_positions_task(
            user_id, mock_account, broker_account_id, broker_class
        )

        mock_integration_user_repo.get.assert_awaited_once_with(
            mock_account.integration_user_id
        )
        mock_broker.get_positions_by_account.assert_awaited_once_with(
            integration_user=mock_integration_user,
            broker_account_id=broker_account_id,
        )
        mock_security_api.get_or_create_from_broker.assert_awaited_once()
        
        # Verify websocket messages
        assert mock_ws.send_personal_message.await_count == 2
        calls = mock_ws.send_personal_message.await_args_list
        assert calls[0][0][0]["type"] == "sync_started"
        assert calls[1][0][0]["type"] == "sync_finished"

@pytest.mark.asyncio
async def test_sync_account_positions_task_raises_if_no_container():
    with patch("src.integration.task.huey.svcs_container", None):
        with pytest.raises(RuntimeError, match="Worker registry not initialized"):
            await _sync_account_positions_task(
                uuid4(), cast(Account, MagicMock()), "broker-id", cast(type[BrokerApiGateway], MagicMock())
            )

@pytest.mark.asyncio
async def test_sync_account_positions_task_raises_if_no_integration_user_id(mock_account):
    mock_account.integration_user_id = None
    mock_container = AsyncMock()
    
    with patch("src.integration.task.huey.svcs_container", mock_container):
        with pytest.raises(AccountPositionsSyncError, match="Account does not have an integration user"):
            await _sync_account_positions_task(
                mock_account.user_id, mock_account, "broker-id", cast(type[BrokerApiGateway], MagicMock())
            )

@pytest.mark.asyncio
async def test_sync_account_positions_task_raises_if_integration_user_not_found(mock_account):
    mock_integration_user_repo = AsyncMock(spec=IntegrationUserRepository)
    mock_integration_user_repo.get.return_value = None
    
    mock_container = AsyncMock()
    async def mock_aget(clazz):
        if clazz == IntegrationUserRepository:
            return mock_integration_user_repo
        return AsyncMock()
    mock_container.aget.side_effect = mock_aget

    with patch("src.integration.task.huey.svcs_container", mock_container):
        with pytest.raises(IntegrationUserNotFoundError):
            await _sync_account_positions_task(
                mock_account.user_id, mock_account, "broker-id", cast(type[BrokerApiGateway], MagicMock())
            )

def test_sync_account_positions_task_calls_async_logic():
    huey.immediate = True
    user_id = uuid4()
    account = MagicMock(spec=Account)
    broker_account_id = "broker-id"
    broker_class = cast(type[BrokerApiGateway], MagicMock())

    with patch("src.integration.task.asyncio.run") as mock_run:
        sync_account_positions_task(user_id, account, broker_account_id, broker_class)
        mock_run.assert_called_once()
        args = mock_run.call_args[0]
        assert asyncio.iscoroutine(args[0])
        args[0].close()

    huey.immediate = False
