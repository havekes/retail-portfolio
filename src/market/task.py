import asyncio
import logging

from huey import crontab
from svcs import Container

from src.core.context import get_request_id, request_id_ctx_var, set_request_id
from src.market.ai_service import AIService
from src.market.repository import SecurityNoteRepository
from src.market.service import MarketService
from src.worker import huey

logger = logging.getLogger(__name__)


@huey.task()
def generate_note_title_task(note_id: int, request_id: str | None = None) -> None:
    """Huey task to generate note title using AI."""
    if request_id is None:
        request_id = get_request_id()

    asyncio.run(_generate_note_title(note_id, request_id=request_id))


async def _generate_note_title(note_id: int, request_id: str | None = None) -> None:
    if huey.svcs_registry is None:
        return

    req_token = set_request_id(request_id) if request_id else None

    try:
        async with Container(huey.svcs_registry) as svcs_container:
            note_repository: SecurityNoteRepository = await svcs_container.aget(
                SecurityNoteRepository
            )
            ai_service: AIService = await svcs_container.aget(AIService)

            note = await note_repository.get_by_id(note_id)
            if not note:
                logger.warning("Note %d not found for title generation", note_id)
                return

            title = await ai_service.generate_note_title(note.content)
            await note_repository.update_title(note_id, title)
            logger.info("Generated title for note %d: %s", note_id, title)
    finally:
        if req_token is not None:
            request_id_ctx_var.reset(req_token)


@huey.periodic_task(crontab(hour="0", minute="0"))
def daily_price_update() -> None:
    """Huey periodic task to run daily price updates at midnight.

    Runs in the huey-worker process via thread workers.
    Uses asyncio.run() to execute the async business logic.
    """
    asyncio.run(_daily_price_update())


async def _daily_price_update() -> None:
    if huey.svcs_registry is None:
        msg = "Worker registry not initialized"
        raise RuntimeError(msg)

    async with Container(huey.svcs_registry) as svcs_container:
        market_service: MarketService = await svcs_container.aget(MarketService)

        logger.info("Starting daily price update for all active securities...")
        result = await market_service.update_daily_prices_for_all_securities()

        success = result.get("success", 0)
        failure = result.get("failure", 0)

        logger.info(
            "Daily price update completed. Successfully updated: %s | Failed: %s",
            success,
            failure,
        )


@huey.periodic_task(crontab(minute="0"))
def hourly_intraday_price_update() -> None:
    """Huey periodic task to run hourly intraday price updates.

    Runs in the huey-worker process via thread workers.
    Uses asyncio.run() to execute the async business logic.
    """
    asyncio.run(_hourly_intraday_price_update())


async def _hourly_intraday_price_update() -> None:
    if huey.svcs_registry is None:
        msg = "Worker registry not initialized"
        raise RuntimeError(msg)

    async with Container(huey.svcs_registry) as svcs_container:
        market_service: MarketService = await svcs_container.aget(MarketService)

        logger.info(
            "Starting hourly intraday price update for all active securities..."
        )
        result = await market_service.update_intraday_prices_for_all_securities()

        success = result.get("success", 0)
        failure = result.get("failure", 0)

        logger.info(
            "Hourly intraday price update completed. Successfully updated: %s | "
            "Failed: %s",
            success,
            failure,
        )
