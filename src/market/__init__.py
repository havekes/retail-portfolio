from svcs import Registry

from src.market.api import MarketPrices, market_prices_factory


def register_api_services(registry: Registry) -> None:
    registry.register_factory(MarketPrices, market_prices_factory)
