import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from stockholm import Currency

from src.account.api.position import PositionApi
from src.account.api_types import Account
from src.account.enum import AccountTypeEnum, InstitutionEnum
from src.account.repository import AccountRepository
from src.integration.brokers import BrokerApiGateway
from src.integration.brokers.api_types import BrokerAccount, BrokerPosition
from src.integration.exception import (
    AccountPositionsSyncError,
    IntegrationUserNotFoundError,
)
from src.integration.repository import IntegrationUserRepository
from src.integration.schema import IntegrationUserSchema
from src.integration.task import (
    _sync_account_positions_task,
    sync_account_positions_task,
)
from src.market.api import SecurityApi
from src.market.api_types import Security
from src.worker import huey


@pytest.fixture
def mock_account():
    return Account(
        id=uuid4(),
        external_id="external-account-id",
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
    broker_class = cast("type[BrokerApiGateway]", MagicMock())

    mock_security_api = AsyncMock(spec=SecurityApi)
    mock_integration_user_repo = AsyncMock(spec=IntegrationUserRepository)
    mock_position_api = AsyncMock(spec=PositionApi)
    mock_account_repo = AsyncMock(spec=AccountRepository)
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
        quantity=Decimal(10),
        average_cost=Decimal(150),
        currency="USD",
    )
    mock_broker.get_positions_by_account.return_value = [mock_broker_position]

    mock_broker_account = BrokerAccount(
        id=broker_account_id,
        type=AccountTypeEnum.TFSA,
        institution=InstitutionEnum.WEALTHSIMPLE,
        currency=Currency.CAD,
        display_name="Test Account",
        broker_display_name="Test",
        value=Decimal(10000),
        net_deposits=Decimal(5000),
        created_at=datetime.now(UTC),
    )
    mock_broker.get_accounts.return_value = [mock_broker_account]

    mock_container = AsyncMock()
    async def mock_aget(clazz):
        if clazz == SecurityApi:
            return mock_security_api
        if clazz == IntegrationUserRepository:
            return mock_integration_user_repo
        if clazz == PositionApi:
            return mock_position_api
        if clazz == AccountRepository:
            return mock_account_repo
        if clazz == broker_class:
            return mock_broker
        return None
    mock_container.aget.side_effect = mock_aget
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.integration.task.huey.svcs_registry", MagicMock()),
        patch("src.integration.task.Container", return_value=mock_container),
        patch("src.integration.task.ws_manager", AsyncMock()) as mock_ws,
        patch("src.integration.task.mark_sync_started", AsyncMock()),
        patch("src.integration.task.mark_sync_finished", AsyncMock()),
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
        mock_account_repo.update_net_deposits.assert_awaited_once_with(
            mock_account.id, 5000.0
        )
        mock_account_repo.update_last_sync_at.assert_awaited_once_with(mock_account.id)

        # Verify websocket messages
        assert mock_ws.send_personal_message.await_count == 2
        calls = mock_ws.send_personal_message.await_args_list
        assert calls[0][0][0]["type"] == "sync_started"
        assert calls[1][0][0]["type"] == "sync_finished"

@pytest.mark.asyncio
async def test_sync_account_positions_task_raises_if_no_container():
    with patch("src.integration.task.huey.svcs_registry", None):
        with pytest.raises(RuntimeError, match="Worker registry not initialized"):
            await _sync_account_positions_task(
                uuid4(), cast("Account", MagicMock()), "broker-id", cast("type[BrokerApiGateway]", MagicMock())
            )

@pytest.mark.asyncio
async def test_sync_account_positions_task_raises_if_no_integration_user_id(mock_account):
    mock_account.integration_user_id = None
    mock_container = AsyncMock()
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.integration.task.huey.svcs_registry", MagicMock()),
        patch("src.integration.task.Container", return_value=mock_container),
        patch("src.integration.task.mark_sync_started", AsyncMock()),
        patch("src.integration.task.mark_sync_finished", AsyncMock()),
    ):
        with pytest.raises(AccountPositionsSyncError, match="Account does not have an integration user"):
            await _sync_account_positions_task(
                mock_account.user_id, mock_account, "broker-id", cast("type[BrokerApiGateway]", MagicMock())
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
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.integration.task.huey.svcs_registry", MagicMock()),
        patch("src.integration.task.Container", return_value=mock_container),
        patch("src.integration.task.mark_sync_started", AsyncMock()),
        patch("src.integration.task.mark_sync_finished", AsyncMock()),
    ):
        with pytest.raises(IntegrationUserNotFoundError):
            await _sync_account_positions_task(
                mock_account.user_id, mock_account, "broker-id", cast("type[BrokerApiGateway]", MagicMock())
            )

def test_sync_account_positions_task_calls_async_logic():
    huey.immediate = True
    user_id = uuid4()
    account = MagicMock(spec=Account)
    broker_account_id = "broker-id"
    broker_class = cast("type[BrokerApiGateway]", MagicMock())

    with patch("src.integration.task.asyncio.run") as mock_run:
        sync_account_positions_task(user_id, account, broker_account_id, broker_class)
        mock_run.assert_called_once()
        args = mock_run.call_args[0]
        assert asyncio.iscoroutine(args[0])
        args[0].close()

    huey.immediate = False


@pytest.mark.asyncio
async def test_sync_task_marks_sync_status_on_success(mock_account, mock_integration_user):
    user_id = mock_account.user_id
    broker_account_id = "broker-account-id"
    broker_class = cast(type[BrokerApiGateway], MagicMock())

    mock_security_api = AsyncMock(spec=SecurityApi)
    mock_integration_user_repo = AsyncMock(spec=IntegrationUserRepository)
    mock_position_api = AsyncMock(spec=PositionApi)
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
        currency="USD",
    )
    mock_broker.get_positions_by_account.return_value = [mock_broker_position]

    mock_container = AsyncMock()
    async def mock_aget(clazz):
        if clazz == SecurityApi:
            return mock_security_api
        if clazz == IntegrationUserRepository:
            return mock_integration_user_repo
        if clazz == PositionApi:
            return mock_position_api
        if clazz == broker_class:
            return mock_broker
        return None
    mock_container.aget.side_effect = mock_aget
    mock_container.__aenter__.return_value = mock_container

    mock_mark_started = AsyncMock()
    mock_mark_finished = AsyncMock()

    with (
        patch("src.integration.task.huey.svcs_registry", MagicMock()),
        patch("src.integration.task.Container", return_value=mock_container),
        patch("src.integration.task.ws_manager", AsyncMock()),
        patch("src.integration.task.mark_sync_started", mock_mark_started),
        patch("src.integration.task.mark_sync_finished", mock_mark_finished),
    ):
        await _sync_account_positions_task(
            user_id, mock_account, broker_account_id, broker_class
        )

        mock_mark_started.assert_awaited_once_with(user_id, mock_account.id)
        mock_mark_finished.assert_awaited_once_with(user_id, mock_account.id)


@pytest.mark.asyncio
async def test_sync_task_marks_sync_finished_on_failure(mock_account, mock_integration_user):
    user_id = mock_account.user_id
    broker_account_id = "broker-account-id"
    broker_class = cast(type[BrokerApiGateway], MagicMock())

    mock_security_api = AsyncMock(spec=SecurityApi)
    mock_integration_user_repo = AsyncMock(spec=IntegrationUserRepository)
    mock_position_api = AsyncMock(spec=PositionApi)
    mock_broker = AsyncMock()

    mock_integration_user_repo.get.return_value = mock_integration_user
    mock_broker.get_positions_by_account.side_effect = Exception("Broker error")

    mock_container = AsyncMock()
    async def mock_aget(clazz):
        if clazz == SecurityApi:
            return mock_security_api
        if clazz == IntegrationUserRepository:
            return mock_integration_user_repo
        if clazz == PositionApi:
            return mock_position_api
        if clazz == broker_class:
            return mock_broker
        return None
    mock_container.aget.side_effect = mock_aget
    mock_container.__aenter__.return_value = mock_container

    mock_mark_started = AsyncMock()
    mock_mark_finished = AsyncMock()

    with (
        patch("src.integration.task.huey.svcs_registry", MagicMock()),
        patch("src.integration.task.Container", return_value=mock_container),
        patch("src.integration.task.ws_manager", AsyncMock()),
        patch("src.integration.task.mark_sync_started", mock_mark_started),
        patch("src.integration.task.mark_sync_finished", mock_mark_finished),
    ):
        with pytest.raises(Exception, match="Broker error"):
            await _sync_account_positions_task(
                user_id, mock_account, broker_account_id, broker_class
            )

        mock_mark_started.assert_awaited_once_with(user_id, mock_account.id)
        mock_mark_finished.assert_awaited_once_with(user_id, mock_account.id)
