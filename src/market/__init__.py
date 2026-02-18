from svcs import Registry

from src.market.api import (
    MarketPricesApi,
    SecurityApi,
    market_prices_factory,
    security_api_factory,
)


def register_market_services(registry: Registry) -> None:
    registry.register_factory(MarketPricesApi, market_prices_factory)
    registry.register_factory(SecurityApi, security_api_factory)
