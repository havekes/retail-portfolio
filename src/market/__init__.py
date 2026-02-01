from svcs import Registry
from svcs.fastapi import DepContainer

from src.market.api import (
    MarketPricesApi,
    SecurityApi,
    market_prices_factory,
    security_api_factory,
)


def register_api_services(registry: Registry) -> None:
    # Create wrappers that svcs will properly detect as taking a container
    async def market_prices_wrapper(svcs_container: DepContainer):
        return await market_prices_factory(svcs_container)

    async def security_api_wrapper(svcs_container: DepContainer):
        return await security_api_factory(svcs_container)

    registry.register_factory(MarketPricesApi, market_prices_wrapper)
    registry.register_factory(SecurityApi, security_api_wrapper)
