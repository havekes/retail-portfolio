from abc import ABC, abstractmethod
from datetime import date

from src.market.api_types import HistoricalPrice, SecurityId, SecuritySearchResult


class MarketGateway(ABC):
    """Abstract base class for market data gateway implementations."""

    @abstractmethod
    def search(self, query: str) -> list[SecuritySearchResult]:
        """Search for securities by query string."""
        ...

    @abstractmethod
    def get_price_on_date(
        self,
        security_id: SecurityId,
        symbol: str,
        exchange: str,
        date: date,
    ) -> HistoricalPrice | None:
        """Get price for a security on a specific date."""
        ...

    @abstractmethod
    def get_prices(
        self,
        security_id: SecurityId,
        symbol: str,
        exchange: str,
        from_date: date,
        to_date: date,
    ) -> list[HistoricalPrice]:
        """Get historical prices for a security within a date range."""
        ...
