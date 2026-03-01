import asyncio
import logging

from svcs import Container, Registry

from src.config.services import register_services
from src.market.service import MarketService

logging.basicConfig(level=logging.INFO)
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


def main() -> None:
    asyncio.run(run_update())


if __name__ == "__main__":
    main()
