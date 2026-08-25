import asyncio
import logging

from svcs import Container

from src.worker import huey
from src.ws.api_types import AccountTotalsUpdatedMessage
from src.ws.manager import ws_manager

logger = logging.getLogger(__name__)


@huey.task()
def recalculate_all_account_totals_task() -> None:
    """Huey task to recalculate totals for all active accounts and broadcast
    via WebSocket.

    Runs in the huey-worker process via thread workers.
    Uses asyncio.run() to execute the async business logic.
    """
    asyncio.run(_recalculate_all_account_totals())


async def _recalculate_all_account_totals() -> None:
    if huey.svcs_registry is None:
        msg = "Worker registry not initialized"
        raise RuntimeError(msg)

    from src.account.service.account import AccountService  # noqa: PLC0415
    from src.account.service.position import PositionService  # noqa: PLC0415

    async with Container(huey.svcs_registry) as svcs_container:
        account_service: AccountService = await svcs_container.aget(AccountService)
        position_service: PositionService = await svcs_container.aget(PositionService)

        accounts = await account_service.get_all_accounts()
        for account in accounts:
            if not account.is_active:
                continue
            try:
                totals = await position_service.get_total_for_account(
                    account.id, account.currency
                )
                msg = AccountTotalsUpdatedMessage(
                    account_id=account.id,
                    totals=totals,
                )
                await ws_manager.send_personal_message(
                    msg.model_dump(mode="json"), account.user_id
                )
            except Exception:
                logger.exception(
                    "Failed to update totals and send WS message for account %s",
                    account.id,
                )
