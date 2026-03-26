"""EODHD API stubs for testing and local development."""

import random
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pandas as pd

from src.market.api_types import EodhdSearchResult, HistoricalPrice
from src.market.schema import SecuritySchema


class StubEodhdAPIClient:
    """Stub implementation of eodhd.APIClient."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def get_historical_data(
        self,
        symbol: str,
        interval: str = "d",
        iso8601_start: str = "",
        iso8601_end: str = "",
        results: int = 300,
    ) -> pd.DataFrame:
        """Get historical price data for a symbol."""
        _ = interval, results  # Unused in stub mode
        start_date = date.fromisoformat(iso8601_start)
        end_date = date.fromisoformat(iso8601_end)

        price_data = self._generate_price_data(symbol, start_date, end_date)

        return pd.DataFrame(price_data)

    def _generate_price_data(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """Generate realistic price data for a symbol."""
        random.seed(hash(symbol) % 2**32)

        base_prices = {
            "US:AAPL": 175.0,
            "US:MSFT": 380.0,
            "US:NFLX": 450.0,
            "TO:RY": 120.0,
            "TO:XYR": 120.50,
            "TO:RYT": 95.0,
            "US:GOOGL": 140.0,
            "US:TSLA": 200.0,
            "US:AMZN": 180.0,
            "TO:TD": 85.0,
        }

        base_price = base_prices.get(symbol, 100.0)

        data = []
        current_date = start_date
        current_price = base_price

        while current_date <= end_date:
            volatility = 0.02
            change = random.uniform(-volatility, volatility)  # noqa: S311
            current_price *= 1 + change

            high = current_price * (1 + random.uniform(0, 0.01))  # noqa: S311
            low = current_price * (1 - random.uniform(0, 0.01))  # noqa: S311
            open_price = current_price * (1 + random.uniform(-0.005, 0.005))  # noqa: S311

            data.append(
                {
                    "date": current_date.isoformat(),
                    "open": round(open_price, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(current_price, 2),
                    "adjusted_close": round(current_price, 2),
                    "volume": random.randint(500000, 5000000),  # noqa: S311
                }
            )

            current_date = current_date + timedelta(days=1)

        return data


class StubEodhdGateway:
    """Stub EODHD gateway for testing."""

    _client: StubEodhdAPIClient
    _api_key: str

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = StubEodhdAPIClient(api_key)

    def search(self, _query: str) -> list[EodhdSearchResult]:
        """Search for securities."""
        return [
            {
                "Code": "AAPL",
                "Currency": "USD",
                "Exchange": "NASDAQ",
                "Name": "Apple Inc.",
                "Type": "Common Stock",
                "Country": "US",
                "ISIN": "US0378331005",
                "isPrimary": True,
                "previousClose": 175.0,
                "previousCloseDate": "2024-01-15",
            },
            {
                "Code": "MSFT",
                "Currency": "USD",
                "Exchange": "NASDAQ",
                "Name": "Microsoft Corporation",
                "Type": "Common Stock",
                "Country": "US",
                "ISIN": "US5949181045",
                "isPrimary": True,
                "previousClose": 380.0,
                "previousCloseDate": "2024-01-15",
            },
            {
                "Code": "RY",
                "Currency": "CAD",
                "Exchange": "TSX",
                "Name": "Royal Bank of Canada",
                "Type": "Common Stock",
                "Country": "CA",
                "ISIN": "CA7800625089",
                "isPrimary": True,
                "previousClose": 120.0,
                "previousCloseDate": "2024-01-15",
            },
        ]

    def get_price_on_date(
        self, security: SecuritySchema, date: date
    ) -> HistoricalPrice | None:
        """Get price for a security on a specific date."""
        data = self._client.get_historical_data(
            symbol=security.get_eodhd_symbol(),
            interval="d",
            iso8601_start=date.isoformat(),
            iso8601_end=date.isoformat(),
        )

        try:
            price = data.iloc[0]
            return HistoricalPrice(
                security_id=security.id,
                date=date,
                open=Decimal(str(price["open"])),
                high=Decimal(str(price["high"])),
                low=Decimal(str(price["low"])),
                close=Decimal(str(price["close"])),
                adjusted_close=Decimal(str(price["adjusted_close"])),
                volume=int(price["volume"]),
            )
        except (IndexError, KeyError):
            return None

    def get_prices(
        self, security: SecuritySchema, from_date: date, to_date: date
    ) -> list[HistoricalPrice]:
        """Get historical prices for a security."""
        data = self._client.get_historical_data(
            symbol=security.get_eodhd_symbol(),
            interval="d",
            iso8601_start=from_date.isoformat(),
            iso8601_end=to_date.isoformat(),
        )

        prices: list[HistoricalPrice] = []
        for index, row in data.iterrows():
            price_date = (
                pd.Timestamp(index).date()
                if isinstance(index, pd.Timestamp)
                else date.fromisoformat(str(index))
            )
            prices.append(
                HistoricalPrice(
                    security_id=security.id,
                    date=price_date,
                    open=Decimal(str(row["open"])),
                    high=Decimal(str(row["high"])),
                    low=Decimal(str(row["low"])),
                    close=Decimal(str(row["close"])),
                    adjusted_close=Decimal(str(row["adjusted_close"])),
                    volume=int(float(row["volume"])),
                )
            )

        return prices
