import asyncio
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Self

from svcs import Container

from src.market.eodhd import eodhd_gateway_factory
from src.market.gateway import MarketGateway
from src.market.repository import PriceRepository, SecurityRepository
from src.market.schema import PriceSchema, SecuritySchema

logger = logging.getLogger(__name__)


class MarketService:
    _gateway: MarketGateway
    _price_repository: PriceRepository
    _security_repository: SecurityRepository

    def __init__(
        self,
        gateway: MarketGateway,
        price_repository: PriceRepository,
        security_repository: SecurityRepository,
    ):
        self._gateway = gateway
        self._price_repository = price_repository
        self._security_repository = security_repository

    async def _update_security_prices(
        self, security: SecuritySchema, from_date: date, to_date: date
    ) -> bool:
        try:
            # Gateway returns a list of HistoricalPrice
            prices = self._gateway.get_prices(
                security.id,
                security.symbol,
                security.exchange,
                from_date=from_date,
                to_date=to_date,
            )
        except Exception:
            # Catching general Exception to prevent one failure from stopping jobs
            logger.exception("Failed to update prices for security %s", security.symbol)
            return False
        else:
            if prices:
                price_schemas = [PriceSchema.from_historical_price(p) for p in prices]
                await self._price_repository.save_prices(price_schemas)
            return True

    async def update_daily_prices_for_all_securities(self) -> dict[str, int]:
        """
        Fetches all securities and updates their prices for the last year.
        Returns a dict containing 'success' and 'failure' counts.
        """
        securities = await self._security_repository.get_all_active_securities()

        # We'll fetch prices for the last year as per the issue comment
        to_date = datetime.now(UTC).date()
        from_date = to_date - timedelta(days=365)

        results = await asyncio.gather(
            *(
                self._update_security_prices(security, from_date, to_date)
                for security in securities
            )
        )

        success_count = sum(1 for result in results if result)
        failure_count = sum(1 for result in results if not result)

        return {"success": success_count, "failure": failure_count}

    async def fetch_and_save_price_history(self, security: SecuritySchema) -> bool:
        """
        Fetch price history for a security from 2000-01-03 to today and save it.
        Returns True if successful, False otherwise.
        """
        try:
            from_date = date(2000, 1, 3)
            to_date = datetime.now(UTC).date()

            prices = self._gateway.get_prices(
                security.id,
                security.symbol,
                security.exchange,
                from_date=from_date,
                to_date=to_date,
            )

            if prices:
                price_schemas = [PriceSchema.from_historical_price(p) for p in prices]
                await self._price_repository.save_prices(price_schemas)
                logger.info(
                    "Fetched and saved %d prices for security %s",
                    len(prices),
                    security.symbol,
                )
                return True
        except Exception:
            logger.exception(
                "Failed to fetch and save price history for security %s",
                security.symbol,
            )
        return False


async def market_service_factory(container: Container) -> MarketService:
    return MarketService(
        gateway=await container.aget(MarketGateway),
        price_repository=await container.aget(PriceRepository),
        security_repository=await container.aget(SecurityRepository),
    )
