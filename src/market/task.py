import asyncio
import logging

from huey import crontab
from svcs import Container

from src.market.ai_service import AIService
from src.market.repository import SecurityNoteRepository
from src.market.service import MarketService
from src.worker import huey

logger = logging.getLogger(__name__)


@huey.task()
def generate_note_title_task(note_id: int) -> None:
    """Huey task to generate note title using AI."""
    asyncio.run(_generate_note_title(note_id))


async def _generate_note_title(note_id: int) -> None:
    if huey.svcs_registry is None:
        return

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
