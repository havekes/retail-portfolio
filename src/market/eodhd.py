from datetime import date
from decimal import Decimal

import requests
from eodhd.apiclient import APIClient

from src.config.settings import settings
from src.market.api_types import EodhdSearchResult, HistoricalPrice
from src.market.schema import SecuritySchema


class EodhdGateway:
    _client: APIClient
    _api_key: str

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = APIClient(api_key)

    def search(self, query: str) -> list[EodhdSearchResult]:
        url = f"https://eodhd.com/api/search/{query}?api_token={self._api_key}&fmt=json"
        data: list[EodhdSearchResult] = requests.get(url, timeout=10).json()

        return data

    def get_price_on_date(
        self, security: SecuritySchema, date: date
    ) -> HistoricalPrice | None:
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
        except IndexError:
            return None

    def get_prices(
        self, security: SecuritySchema, from_date: date, to_date: date
    ) -> list[HistoricalPrice]:
        data = self._client.get_historical_data(
            symbol=security.get_eodhd_symbol(),
            interval="d",
            iso8601_start=from_date.isoformat(),
            iso8601_end=to_date.isoformat(),
        )

        prices: list[HistoricalPrice] = []
        for index, price in data.iterrows():
            prices.append(
                HistoricalPrice(
                    security_id=security.id,
                    date=index.date(),  # type: ignore[attr-defined]
                    open=Decimal(str(price["open"])),
                    high=Decimal(str(price["high"])),
                    low=Decimal(str(price["low"])),
                    close=Decimal(str(price["close"])),
                    adjusted_close=Decimal(str(price["adjusted_close"])),
                    volume=int(price["volume"]),
                )
            )

        return prices


def eodhd_gateway_factory():
    return EodhdGateway(api_key=settings.eodhd_api_key)
