from datetime import date
from decimal import Decimal
from typing import TypedDict

import requests
from eodhd.apiclient import APIClient
from pydantic import BaseModel

from src.config.settings import settings
from src.market.api_types import SecurityId
from src.market.schema import SecuritySchema


class EodhdSearchResult(TypedDict):
    Code: str
    Currency: str
    Exchange: str
    Name: str
    Type: str
    Country: str
    ISIN: str
    isPrimary: str
    previousClose: str
    previousCloseDate: str


class HistoricalPrice(BaseModel):
    security_id: SecurityId
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


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
            price = data.iloc[0]  # pyright: ignore[reportUnknownVariableType]
            return HistoricalPrice(
                security_id=security.id,
                date=date,
                open=price["open"],  # pyright: ignore[reportUnknownArgumentType]
                high=price["high"],  # pyright: ignore[reportUnknownArgumentType]
                low=price["low"],  # pyright: ignore[reportUnknownArgumentType]
                close=price["close"],  # pyright: ignore[reportUnknownArgumentType]
                volume=price["volume"],  # pyright: ignore[reportUnknownArgumentType]
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
                    date=index,  # pyright: ignore[reportArgumentType]
                    open=price["open"],  # pyright: ignore[reportArgumentType]
                    high=price["high"],  # pyright: ignore[reportArgumentType]
                    low=price["low"],  # pyright: ignore[reportArgumentType]
                    close=price["close"],  # pyright: ignore[reportArgumentType]
                    volume=price["volume"],  # pyright: ignore[reportArgumentType]
                )
            )

        return prices


def eodhd_gateway_factory():
    return EodhdGateway(api_key=settings.eodhd_api_key)
