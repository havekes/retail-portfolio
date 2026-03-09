import asyncio
import logging

from huey import crontab

from src.market.service import MarketService
from src.worker import huey

logger = logging.getLogger(__name__)


@huey.periodic_task(crontab(hour="0", minute="0"))
def daily_price_update() -> None:
    """Huey periodic task to run daily price updates at midnight.

    Runs in the huey-worker process via thread workers.
    Uses asyncio.run() to execute the async business logic.
    """
    asyncio.run(_daily_price_update())


async def _daily_price_update() -> None:
    if huey.svcs_container is None:
        msg = "Worker registry not initialized"
        raise RuntimeError(msg)

    market_service: MarketService = await huey.svcs_container.aget(MarketService)

    logger.info("Starting daily price update for all active securities...")
    result = await market_service.update_daily_prices_for_all_securities()

    success = result.get("success", 0)
    failure = result.get("failure", 0)

    logger.info(
        "Daily price update completed. Successfully updated: %s | Failed: %s",
        success,
        failure,
    )
