import asyncio
import contextlib
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from svcs import Container, Registry

from src.config.services import register_services
from src.market.service import MarketService

# Configure basic logging for the scheduler
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_update() -> None:
    registry = Registry()
    register_services(registry)

    async with Container(registry) as container:
        market_service: MarketService = await container.aget(MarketService)

        logger.info("Starting daily price update for all active securities...")
        result = await market_service.update_daily_prices_for_all_securities()

        success = result.get("success", 0)
        failure = result.get("failure", 0)

        logger.info(
            "Daily price update completed. Successfully updated: %s | Failed: %s",
            success,
            failure,
        )


async def main() -> None:
    logger.info("Initializing APScheduler for daily price updates...")

    scheduler = AsyncIOScheduler()

    # Schedule the run_update function to run daily at midnight
    scheduler.add_job(
        run_update,
        trigger=CronTrigger(hour=0, minute=0),
        id="retail-portfolio-daily-prices",
        name="Daily Price Updates",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started successfully. Press Ctrl+C to exit.")

    try:
        # Keep the script running
        await asyncio.Event().wait()
    except KeyboardInterrupt, SystemExit:
        logger.info("Shutting down the scheduler...")
        scheduler.shutdown()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
