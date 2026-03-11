import asyncio
import logging

from svcs import Container

from src.account.api_types import Account
from src.account.repository import PositionRepository
from src.auth.api_types import UserId
from src.integration.brokers import BrokerApiGateway
from src.integration.brokers.api_types import BrokerAccountId
from src.integration.exception import (
    AccountPositionsSyncError,
    IntegrationUserNotFoundError,
)
from src.integration.repository import IntegrationUserRepository
from src.market.api import SecurityApi
from src.worker import huey
from src.ws.api_types import AccountSyncMessage, WsEventType
from src.ws.manager import ws_manager

logger = logging.getLogger(__name__)


@huey.task()
def sync_account_positions_task(
    user_id: UserId,
    account: Account,
    broker_account_id: BrokerAccountId,
    broker_class: type[BrokerApiGateway],
) -> None:
    """
    Huey task to sync positions for newly imported accounts
    and notify the frontend via WebSockets.
    Runs in the huey-worker process, isolated from the FastAPI lifecycle.
    """
    asyncio.run(
        _sync_account_positions_task(user_id, account, broker_account_id, broker_class)
    )


async def _do_sync_positions(
    account: Account,
    broker_account_id: BrokerAccountId,
    broker_class: type[BrokerApiGateway],
    svcs_container: Container,
) -> None:
    security_api = await svcs_container.aget(SecurityApi)
    integration_user_repository = await svcs_container.aget(IntegrationUserRepository)

    if account.integration_user_id is None:
        msg = "Account does not have an integration user"
        raise AccountPositionsSyncError(msg)

    integration_user = await integration_user_repository.get(
        account.integration_user_id,
    )

    if integration_user is None:
        raise IntegrationUserNotFoundError(account.integration_user_id)

    broker = await svcs_container.aget(broker_class)
    broker_positions = await broker.get_positions_by_account(
        integration_user=integration_user,
        broker_account_id=broker_account_id,
    )

    positions = []
    for broker_position in broker_positions:
        security = await security_api.get_or_create_from_broker(
            institution_id=integration_user.institution_id,
            broker_symbol=broker_position.symbol,
            broker_exchange=broker_position.exchange,
            broker_name=broker_position.name,
        )

        positions.append(
            broker_position.to_position(account_id=account.id, security_id=security.id)
        )

    # TODO breaks domain boundary. Task should be refactored
    position_repository = await svcs_container.aget(PositionRepository)
    await position_repository.sync_by_account(account.id, positions)


async def _sync_account_positions_task(
    user_id: UserId,
    account: Account,
    broker_account_id: BrokerAccountId,
    broker_class: type[BrokerApiGateway],
) -> None:
    """
    Async implementation of sync_positions_task.
    """
    if huey.svcs_container is None:
        msg = "Worker registry not initialized"
        raise RuntimeError(msg)

    try:
        # Send sync_started websocket message
        await ws_manager.send_personal_message(
            AccountSyncMessage(
                type=WsEventType.ACCOUNT_SYNC_STARTED, account_id=account.id
            ).model_dump(mode="json"),
            user_id,
        )

        await _do_sync_positions(
            account, broker_account_id, broker_class, huey.svcs_container
        )

        # Send sync_finished websocket message
        await ws_manager.send_personal_message(
            AccountSyncMessage(
                type=WsEventType.ACCOUNT_SYNC_FINISHED, account_id=account.id
            ).model_dump(mode="json"),
            user_id,
        )
    except Exception:
        logger.exception("Failed to sync positions for account %s", account.id)
        # Send sync_failed websocket message
        await ws_manager.send_personal_message(
            AccountSyncMessage(
                type=WsEventType.ACCOUNT_SYNC_FAILED, account_id=account.id
            ).model_dump(mode="json"),
            user_id,
        )
        raise
