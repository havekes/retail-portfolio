import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from stockholm import Currency

from src.account.api.account import AccountApi
from src.account.api.position import PositionApi
from src.account.api_types import Account
from src.auth.api import UserApi
from src.config.settings import settings
from src.core.email import (
    EmailSendError,
    EmailService,
    ExternalAccountErrorEmailData,
)
from src.core.enum import AccountTypeEnum, InstitutionEnum
from src.integration.brokers import BrokerApiGateway
from src.integration.brokers.api_types import BrokerAccount, BrokerPosition
from src.integration.brokers.exception import (
    ExternalAPIError,
    LoginFailedError,
    OTPRequiredError,
    SessionDoesNotExistError,
    SessionExpiredError,
)
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
    mock_account_api = AsyncMock(spec=AccountApi)
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
        if clazz == AccountApi:
            return mock_account_api
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
        mock_account_api.update_net_deposits.assert_awaited_once_with(
            mock_account.id, 5000.0
        )
        mock_account_api.update_last_sync_at.assert_awaited_once_with(mock_account.id)

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
    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_email_for_user.return_value = "user@example.com"
    mock_email_service = AsyncMock(spec=EmailService)

    mock_container = AsyncMock()
    async def mock_aget(clazz):
        if clazz == UserApi:
            return mock_user_api
        if clazz == EmailService:
            return mock_email_service
        return AsyncMock()
    mock_container.aget.side_effect = mock_aget
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.integration.task.huey.svcs_registry", MagicMock()),
        patch("src.integration.task.Container", return_value=mock_container),
        patch("src.integration.task.mark_sync_started", AsyncMock()),
        patch("src.integration.task.mark_sync_finished", AsyncMock()),
        patch("src.integration.task.ws_manager", AsyncMock()),
    ):
        with pytest.raises(AccountPositionsSyncError, match="Account does not have an integration user"):
            await _sync_account_positions_task(
                mock_account.user_id, mock_account, "broker-id", cast("type[BrokerApiGateway]", MagicMock())
            )

@pytest.mark.asyncio
async def test_sync_account_positions_task_raises_if_integration_user_not_found(mock_account):
    mock_integration_user_repo = AsyncMock(spec=IntegrationUserRepository)
    mock_integration_user_repo.get.return_value = None
    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_email_for_user.return_value = "user@example.com"
    mock_email_service = AsyncMock(spec=EmailService)

    mock_container = AsyncMock()
    async def mock_aget(clazz):
        if clazz == IntegrationUserRepository:
            return mock_integration_user_repo
        if clazz == UserApi:
            return mock_user_api
        if clazz == EmailService:
            return mock_email_service
        return AsyncMock()
    mock_container.aget.side_effect = mock_aget
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.integration.task.huey.svcs_registry", MagicMock()),
        patch("src.integration.task.Container", return_value=mock_container),
        patch("src.integration.task.mark_sync_started", AsyncMock()),
        patch("src.integration.task.mark_sync_finished", AsyncMock()),
        patch("src.integration.task.ws_manager", AsyncMock()),
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
    mock_account_api = AsyncMock(spec=AccountApi)
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
        if clazz == AccountApi:
            return mock_account_api
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
    mock_account_api = AsyncMock(spec=AccountApi)
    mock_broker = AsyncMock()
    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_email_for_user.return_value = "user@example.com"
    mock_email_service = AsyncMock(spec=EmailService)

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
        if clazz == AccountApi:
            return mock_account_api
        if clazz == broker_class:
            return mock_broker
        if clazz == UserApi:
            return mock_user_api
        if clazz == EmailService:
            return mock_email_service
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


@pytest.mark.asyncio
async def test_sync_account_positions_task_sends_email_on_session_expired_error(
    mock_account, mock_integration_user
):
    user_id = mock_account.user_id
    broker_account_id = "broker-account-id"
    broker_class = cast(type[BrokerApiGateway], MagicMock())

    mock_integration_user_repo = AsyncMock(spec=IntegrationUserRepository)
    mock_integration_user_repo.get.return_value = mock_integration_user

    mock_broker = AsyncMock()
    mock_broker.get_positions_by_account.side_effect = SessionExpiredError("Session expired")

    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_email_for_user.return_value = "user@example.com"

    mock_email_service = AsyncMock(spec=EmailService)

    mock_container = AsyncMock()
    async def mock_aget(clazz):
        if clazz == IntegrationUserRepository:
            return mock_integration_user_repo
        if clazz == broker_class:
            return mock_broker
        if clazz == UserApi:
            return mock_user_api
        if clazz == EmailService:
            return mock_email_service
        return AsyncMock()
    mock_container.aget.side_effect = mock_aget
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.integration.task.huey.svcs_registry", MagicMock()),
        patch("src.integration.task.Container", return_value=mock_container),
        patch("src.integration.task.ws_manager", AsyncMock()),
        patch("src.integration.task.mark_sync_started", AsyncMock()),
        patch("src.integration.task.mark_sync_finished", AsyncMock()),
    ):
        with pytest.raises(SessionExpiredError):
            await _sync_account_positions_task(
                user_id, mock_account, broker_account_id, broker_class
            )

        mock_user_api.get_email_for_user.assert_awaited_once_with(user_id)
        mock_email_service.send_external_account_error_email.assert_awaited_once_with(
            recipient="user@example.com",
            data=ExternalAccountErrorEmailData(
                account_name=mock_account.name,
                institution_name="Wealthsimple",
                error_message=(
                    "Your session with the institution has expired. Please log in to your"
                    " account settings to reconnect and re-authenticate your external account."
                ),
                deeplink=f"{settings.frontend_url}/accounts",
            ),
        )


@pytest.mark.asyncio
async def test_sync_account_positions_task_sends_email_on_session_does_not_exist_error(
    mock_account, mock_integration_user
):
    user_id = mock_account.user_id
    broker_account_id = "broker-account-id"
    broker_class = cast(type[BrokerApiGateway], MagicMock())

    mock_integration_user_repo = AsyncMock(spec=IntegrationUserRepository)
    mock_integration_user_repo.get.return_value = mock_integration_user

    mock_broker = AsyncMock()
    mock_broker.get_positions_by_account.side_effect = SessionDoesNotExistError("No session")

    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_email_for_user.return_value = "user@example.com"

    mock_email_service = AsyncMock(spec=EmailService)

    mock_container = AsyncMock()
    async def mock_aget(clazz):
        if clazz == IntegrationUserRepository:
            return mock_integration_user_repo
        if clazz == broker_class:
            return mock_broker
        if clazz == UserApi:
            return mock_user_api
        if clazz == EmailService:
            return mock_email_service
        return AsyncMock()
    mock_container.aget.side_effect = mock_aget
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.integration.task.huey.svcs_registry", MagicMock()),
        patch("src.integration.task.Container", return_value=mock_container),
        patch("src.integration.task.ws_manager", AsyncMock()),
        patch("src.integration.task.mark_sync_started", AsyncMock()),
        patch("src.integration.task.mark_sync_finished", AsyncMock()),
    ):
        with pytest.raises(SessionDoesNotExistError):
            await _sync_account_positions_task(
                user_id, mock_account, broker_account_id, broker_class
            )

        mock_email_service.send_external_account_error_email.assert_awaited_once_with(
            recipient="user@example.com",
            data=ExternalAccountErrorEmailData(
                account_name=mock_account.name,
                institution_name="Wealthsimple",
                error_message=(
                    "No active session was found for your external account. Please log in to"
                    " your account settings to link and authenticate your external account."
                ),
                deeplink=f"{settings.frontend_url}/accounts",
            ),
        )


@pytest.mark.asyncio
async def test_sync_account_positions_task_sends_email_on_otp_required_error(
    mock_account, mock_integration_user
):
    user_id = mock_account.user_id
    broker_account_id = "broker-account-id"
    broker_class = cast(type[BrokerApiGateway], MagicMock())

    mock_integration_user_repo = AsyncMock(spec=IntegrationUserRepository)
    mock_integration_user_repo.get.return_value = mock_integration_user

    mock_broker = AsyncMock()
    mock_broker.get_positions_by_account.side_effect = OTPRequiredError("OTP required")

    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_email_for_user.return_value = "user@example.com"

    mock_email_service = AsyncMock(spec=EmailService)

    mock_container = AsyncMock()
    async def mock_aget(clazz):
        if clazz == IntegrationUserRepository:
            return mock_integration_user_repo
        if clazz == broker_class:
            return mock_broker
        if clazz == UserApi:
            return mock_user_api
        if clazz == EmailService:
            return mock_email_service
        return AsyncMock()
    mock_container.aget.side_effect = mock_aget
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.integration.task.huey.svcs_registry", MagicMock()),
        patch("src.integration.task.Container", return_value=mock_container),
        patch("src.integration.task.ws_manager", AsyncMock()),
        patch("src.integration.task.mark_sync_started", AsyncMock()),
        patch("src.integration.task.mark_sync_finished", AsyncMock()),
    ):
        with pytest.raises(OTPRequiredError):
            await _sync_account_positions_task(
                user_id, mock_account, broker_account_id, broker_class
            )

        mock_email_service.send_external_account_error_email.assert_awaited_once_with(
            recipient="user@example.com",
            data=ExternalAccountErrorEmailData(
                account_name=mock_account.name,
                institution_name="Wealthsimple",
                error_message=(
                    "A one-time verification code (OTP) or two-factor authentication is required."
                    " Please log in to your account settings to complete authentication."
                ),
                deeplink=f"{settings.frontend_url}/accounts",
            ),
        )


@pytest.mark.asyncio
async def test_sync_account_positions_task_sends_email_on_login_failed_error(
    mock_account, mock_integration_user
):
    user_id = mock_account.user_id
    broker_account_id = "broker-account-id"
    broker_class = cast(type[BrokerApiGateway], MagicMock())

    mock_integration_user_repo = AsyncMock(spec=IntegrationUserRepository)
    mock_integration_user_repo.get.return_value = mock_integration_user

    mock_broker = AsyncMock()
    mock_broker.get_positions_by_account.side_effect = LoginFailedError("Login failed")

    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_email_for_user.return_value = "user@example.com"

    mock_email_service = AsyncMock(spec=EmailService)

    mock_container = AsyncMock()
    async def mock_aget(clazz):
        if clazz == IntegrationUserRepository:
            return mock_integration_user_repo
        if clazz == broker_class:
            return mock_broker
        if clazz == UserApi:
            return mock_user_api
        if clazz == EmailService:
            return mock_email_service
        return AsyncMock()
    mock_container.aget.side_effect = mock_aget
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.integration.task.huey.svcs_registry", MagicMock()),
        patch("src.integration.task.Container", return_value=mock_container),
        patch("src.integration.task.ws_manager", AsyncMock()),
        patch("src.integration.task.mark_sync_started", AsyncMock()),
        patch("src.integration.task.mark_sync_finished", AsyncMock()),
    ):
        with pytest.raises(LoginFailedError):
            await _sync_account_positions_task(
                user_id, mock_account, broker_account_id, broker_class
            )

        mock_email_service.send_external_account_error_email.assert_awaited_once_with(
            recipient="user@example.com",
            data=ExternalAccountErrorEmailData(
                account_name=mock_account.name,
                institution_name="Wealthsimple",
                error_message=(
                    "Authentication with the external institution failed. Please check your"
                    " credentials and reconnect your external account."
                ),
                deeplink=f"{settings.frontend_url}/accounts",
            ),
        )


@pytest.mark.asyncio
async def test_sync_account_positions_task_sends_email_on_integration_user_not_found(
    mock_account,
):
    user_id = mock_account.user_id
    broker_account_id = "broker-account-id"
    broker_class = cast(type[BrokerApiGateway], MagicMock())

    mock_integration_user_repo = AsyncMock(spec=IntegrationUserRepository)
    mock_integration_user_repo.get.return_value = None

    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_email_for_user.return_value = "user@example.com"

    mock_email_service = AsyncMock(spec=EmailService)

    mock_container = AsyncMock()
    async def mock_aget(clazz):
        if clazz == IntegrationUserRepository:
            return mock_integration_user_repo
        if clazz == UserApi:
            return mock_user_api
        if clazz == EmailService:
            return mock_email_service
        return AsyncMock()
    mock_container.aget.side_effect = mock_aget
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.integration.task.huey.svcs_registry", MagicMock()),
        patch("src.integration.task.Container", return_value=mock_container),
        patch("src.integration.task.ws_manager", AsyncMock()),
        patch("src.integration.task.mark_sync_started", AsyncMock()),
        patch("src.integration.task.mark_sync_finished", AsyncMock()),
    ):
        with pytest.raises(IntegrationUserNotFoundError):
            await _sync_account_positions_task(
                user_id, mock_account, broker_account_id, broker_class
            )

        mock_email_service.send_external_account_error_email.assert_awaited_once_with(
            recipient="user@example.com",
            data=ExternalAccountErrorEmailData(
                account_name=mock_account.name,
                institution_name="Wealthsimple",
                error_message=(
                    "Integration details for this external account could not be found."
                    " Please reconnect your external account."
                ),
                deeplink=f"{settings.frontend_url}/accounts",
            ),
        )


@pytest.mark.asyncio
async def test_sync_account_positions_task_sends_email_on_generic_sync_error(
    mock_account, mock_integration_user
):
    user_id = mock_account.user_id
    broker_account_id = "broker-account-id"
    broker_class = cast(type[BrokerApiGateway], MagicMock())

    mock_integration_user_repo = AsyncMock(spec=IntegrationUserRepository)
    mock_integration_user_repo.get.return_value = mock_integration_user

    mock_broker = AsyncMock()
    mock_broker.get_positions_by_account.side_effect = RuntimeError("Unknown failure")

    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_email_for_user.return_value = "user@example.com"

    mock_email_service = AsyncMock(spec=EmailService)

    mock_container = AsyncMock()
    async def mock_aget(clazz):
        if clazz == IntegrationUserRepository:
            return mock_integration_user_repo
        if clazz == broker_class:
            return mock_broker
        if clazz == UserApi:
            return mock_user_api
        if clazz == EmailService:
            return mock_email_service
        return AsyncMock()
    mock_container.aget.side_effect = mock_aget
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.integration.task.huey.svcs_registry", MagicMock()),
        patch("src.integration.task.Container", return_value=mock_container),
        patch("src.integration.task.ws_manager", AsyncMock()),
        patch("src.integration.task.mark_sync_started", AsyncMock()),
        patch("src.integration.task.mark_sync_finished", AsyncMock()),
    ):
        with pytest.raises(RuntimeError, match="Unknown failure"):
            await _sync_account_positions_task(
                user_id, mock_account, broker_account_id, broker_class
            )

        mock_email_service.send_external_account_error_email.assert_awaited_once_with(
            recipient="user@example.com",
            data=ExternalAccountErrorEmailData(
                account_name=mock_account.name,
                institution_name="Wealthsimple",
                error_message=(
                    "An unexpected error occurred while syncing your account positions."
                    " Please try again later."
                ),
                deeplink=f"{settings.frontend_url}/accounts",
            ),
        )


@pytest.mark.asyncio
async def test_sync_account_positions_task_sends_email_on_external_api_error(
    mock_account, mock_integration_user
):
    user_id = mock_account.user_id
    broker_account_id = "broker-account-id"
    broker_class = cast(type[BrokerApiGateway], MagicMock())

    mock_integration_user_repo = AsyncMock(spec=IntegrationUserRepository)
    mock_integration_user_repo.get.return_value = mock_integration_user

    mock_broker = AsyncMock()
    mock_broker.get_positions_by_account.side_effect = ExternalAPIError("Gateway timeout")

    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_email_for_user.return_value = "user@example.com"

    mock_email_service = AsyncMock(spec=EmailService)

    mock_container = AsyncMock()
    async def mock_aget(clazz):
        if clazz == IntegrationUserRepository:
            return mock_integration_user_repo
        if clazz == broker_class:
            return mock_broker
        if clazz == UserApi:
            return mock_user_api
        if clazz == EmailService:
            return mock_email_service
        return AsyncMock()
    mock_container.aget.side_effect = mock_aget
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.integration.task.huey.svcs_registry", MagicMock()),
        patch("src.integration.task.Container", return_value=mock_container),
        patch("src.integration.task.ws_manager", AsyncMock()),
        patch("src.integration.task.mark_sync_started", AsyncMock()),
        patch("src.integration.task.mark_sync_finished", AsyncMock()),
    ):
        with pytest.raises(ExternalAPIError):
            await _sync_account_positions_task(
                user_id, mock_account, broker_account_id, broker_class
            )

        mock_email_service.send_external_account_error_email.assert_awaited_once_with(
            recipient="user@example.com",
            data=ExternalAccountErrorEmailData(
                account_name=mock_account.name,
                institution_name="Wealthsimple",
                error_message=(
                    "An error occurred while communicating with the external institution."
                    " Please try again later."
                ),
                deeplink=f"{settings.frontend_url}/accounts",
            ),
        )


@pytest.mark.asyncio
async def test_sync_account_positions_task_sends_email_on_account_positions_sync_error_empty_message(
    mock_account, mock_integration_user
):
    user_id = mock_account.user_id
    broker_account_id = "broker-account-id"
    broker_class = cast(type[BrokerApiGateway], MagicMock())

    mock_integration_user_repo = AsyncMock(spec=IntegrationUserRepository)
    mock_integration_user_repo.get.return_value = mock_integration_user

    mock_broker = AsyncMock()
    mock_broker.get_positions_by_account.side_effect = AccountPositionsSyncError("")

    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_email_for_user.return_value = "user@example.com"

    mock_email_service = AsyncMock(spec=EmailService)

    mock_container = AsyncMock()
    async def mock_aget(clazz):
        if clazz == IntegrationUserRepository:
            return mock_integration_user_repo
        if clazz == broker_class:
            return mock_broker
        if clazz == UserApi:
            return mock_user_api
        if clazz == EmailService:
            return mock_email_service
        return AsyncMock()
    mock_container.aget.side_effect = mock_aget
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.integration.task.huey.svcs_registry", MagicMock()),
        patch("src.integration.task.Container", return_value=mock_container),
        patch("src.integration.task.ws_manager", AsyncMock()),
        patch("src.integration.task.mark_sync_started", AsyncMock()),
        patch("src.integration.task.mark_sync_finished", AsyncMock()),
    ):
        with pytest.raises(AccountPositionsSyncError):
            await _sync_account_positions_task(
                user_id, mock_account, broker_account_id, broker_class
            )

        mock_email_service.send_external_account_error_email.assert_awaited_once_with(
            recipient="user@example.com",
            data=ExternalAccountErrorEmailData(
                account_name=mock_account.name,
                institution_name="Wealthsimple",
                error_message="Failed to sync account positions. Please try again or reconnect your external account.",
                deeplink=f"{settings.frontend_url}/accounts",
            ),
        )


@pytest.mark.asyncio
async def test_sync_account_positions_task_sends_email_unmapped_institution_fallback(
    mock_account, mock_integration_user
):
    mock_account.institution_id = 99999
    user_id = mock_account.user_id
    broker_account_id = "broker-account-id"
    broker_class = cast(type[BrokerApiGateway], MagicMock())

    mock_integration_user_repo = AsyncMock(spec=IntegrationUserRepository)
    mock_integration_user_repo.get.return_value = mock_integration_user

    mock_broker = AsyncMock()
    mock_broker.get_positions_by_account.side_effect = SessionExpiredError("Session expired")

    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_email_for_user.return_value = "user@example.com"

    mock_email_service = AsyncMock(spec=EmailService)

    mock_container = AsyncMock()
    async def mock_aget(clazz):
        if clazz == IntegrationUserRepository:
            return mock_integration_user_repo
        if clazz == broker_class:
            return mock_broker
        if clazz == UserApi:
            return mock_user_api
        if clazz == EmailService:
            return mock_email_service
        return AsyncMock()
    mock_container.aget.side_effect = mock_aget
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.integration.task.huey.svcs_registry", MagicMock()),
        patch("src.integration.task.Container", return_value=mock_container),
        patch("src.integration.task.ws_manager", AsyncMock()),
        patch("src.integration.task.mark_sync_started", AsyncMock()),
        patch("src.integration.task.mark_sync_finished", AsyncMock()),
    ):
        with pytest.raises(SessionExpiredError):
            await _sync_account_positions_task(
                user_id, mock_account, broker_account_id, broker_class
            )

        mock_email_service.send_external_account_error_email.assert_awaited_once_with(
            recipient="user@example.com",
            data=ExternalAccountErrorEmailData(
                account_name=mock_account.name,
                institution_name="99999",
                error_message=(
                    "Your session with the institution has expired. Please log in to your"
                    " account settings to reconnect and re-authenticate your external account."
                ),
                deeplink=f"{settings.frontend_url}/accounts",
            ),
        )


@pytest.mark.asyncio
async def test_sync_account_positions_task_email_failure_resilience(
    mock_account, mock_integration_user
):
    user_id = mock_account.user_id
    broker_account_id = "broker-account-id"
    broker_class = cast(type[BrokerApiGateway], MagicMock())

    mock_integration_user_repo = AsyncMock(spec=IntegrationUserRepository)
    mock_integration_user_repo.get.return_value = mock_integration_user

    mock_broker = AsyncMock()
    mock_broker.get_positions_by_account.side_effect = SessionExpiredError("Session expired")

    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_email_for_user.return_value = "user@example.com"

    mock_email_service = AsyncMock(spec=EmailService)
    mock_email_service.send_external_account_error_email.side_effect = EmailSendError("SMTP failure")

    mock_container = AsyncMock()
    async def mock_aget(clazz):
        if clazz == IntegrationUserRepository:
            return mock_integration_user_repo
        if clazz == broker_class:
            return mock_broker
        if clazz == UserApi:
            return mock_user_api
        if clazz == EmailService:
            return mock_email_service
        return AsyncMock()
    mock_container.aget.side_effect = mock_aget
    mock_container.__aenter__.return_value = mock_container

    mock_ws = AsyncMock()
    mock_mark_started = AsyncMock()
    mock_mark_finished = AsyncMock()

    with (
        patch("src.integration.task.huey.svcs_registry", MagicMock()),
        patch("src.integration.task.Container", return_value=mock_container),
        patch("src.integration.task.ws_manager", mock_ws),
        patch("src.integration.task.mark_sync_started", mock_mark_started),
        patch("src.integration.task.mark_sync_finished", mock_mark_finished),
    ):
        with pytest.raises(SessionExpiredError, match="Session expired"):
            await _sync_account_positions_task(
                user_id, mock_account, broker_account_id, broker_class
            )

        mock_email_service.send_external_account_error_email.assert_awaited_once()

        mock_ws.send_personal_message.assert_awaited()
        calls = mock_ws.send_personal_message.await_args_list
        assert calls[-1][0][0]["type"] == "sync_failed"
        assert calls[-1][0][1] == user_id

        mock_mark_started.assert_awaited_once_with(user_id, mock_account.id)
        mock_mark_finished.assert_awaited_once_with(user_id, mock_account.id)


@pytest.mark.asyncio
async def test_sync_account_positions_task_no_user_email_resilience(
    mock_account, mock_integration_user
):
    user_id = mock_account.user_id
    broker_account_id = "broker-account-id"
    broker_class = cast(type[BrokerApiGateway], MagicMock())

    mock_integration_user_repo = AsyncMock(spec=IntegrationUserRepository)
    mock_integration_user_repo.get.return_value = mock_integration_user

    mock_broker = AsyncMock()
    mock_broker.get_positions_by_account.side_effect = SessionExpiredError("Session expired")

    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_email_for_user.return_value = None

    mock_email_service = AsyncMock(spec=EmailService)

    mock_container = AsyncMock()
    async def mock_aget(clazz):
        if clazz == IntegrationUserRepository:
            return mock_integration_user_repo
        if clazz == broker_class:
            return mock_broker
        if clazz == UserApi:
            return mock_user_api
        if clazz == EmailService:
            return mock_email_service
        return AsyncMock()
    mock_container.aget.side_effect = mock_aget
    mock_container.__aenter__.return_value = mock_container

    mock_ws = AsyncMock()
    mock_mark_started = AsyncMock()
    mock_mark_finished = AsyncMock()

    with (
        patch("src.integration.task.huey.svcs_registry", MagicMock()),
        patch("src.integration.task.Container", return_value=mock_container),
        patch("src.integration.task.ws_manager", mock_ws),
        patch("src.integration.task.mark_sync_started", mock_mark_started),
        patch("src.integration.task.mark_sync_finished", mock_mark_finished),
    ):
        with pytest.raises(SessionExpiredError, match="Session expired"):
            await _sync_account_positions_task(
                user_id, mock_account, broker_account_id, broker_class
            )

        mock_email_service.send_external_account_error_email.assert_not_awaited()

        mock_ws.send_personal_message.assert_awaited()
        calls = mock_ws.send_personal_message.await_args_list
        assert calls[-1][0][0]["type"] == "sync_failed"

        mock_mark_started.assert_awaited_once_with(user_id, mock_account.id)
        mock_mark_finished.assert_awaited_once_with(user_id, mock_account.id)

