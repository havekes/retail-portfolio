from svcs import Registry

from src.market.api import MarketPricesApi, market_prices_factory


def register_api_services(registry: Registry) -> None:
    registry.register_factory(MarketPricesApi, market_prices_factory)
