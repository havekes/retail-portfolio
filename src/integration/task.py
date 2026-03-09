import asyncio
import logging

from src.account.api_types import Account
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

    security_api = await huey.svcs_container.aget(SecurityApi)
    integration_user_repository = await huey.svcs_container.aget(
        IntegrationUserRepository
    )

    if account.integration_user_id is None:
        msg = "Account does not have an integration user"
        raise AccountPositionsSyncError(msg)

    integration_user = await integration_user_repository.get(
        account.integration_user_id,
    )

    if integration_user is None:
        raise IntegrationUserNotFoundError(account.integration_user_id)

    # TODO type websocket messages
    await ws_manager.send_personal_message(
        {"type": "sync_started", "account_id": str(account.id)},
        user_id,
    )

    broker = await huey.svcs_container.aget(broker_class)
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

    await ws_manager.send_personal_message(
        {"type": "sync_finished", "account_id": str(account.id)},
        user_id,
    )
