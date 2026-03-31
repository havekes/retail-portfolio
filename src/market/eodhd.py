import logging
from datetime import date
from decimal import Decimal

import requests
from eodhd.apiclient import APIClient
from pandas import Timestamp

from src.config.settings import settings
from src.market.api_types import (
    EodhdSearchResult,
    HistoricalPrice,
    SecurityId,
    SecuritySearchResult,
)
from src.market.gateway import MarketGateway
from src.market.schema import SecuritySchema

logger = logging.getLogger(__name__)


class EodhdGateway(MarketGateway):
    _client: APIClient
    _api_key: str

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = APIClient(api_key)

    def search(self, query: str) -> list[SecuritySearchResult]:
        url = f"https://eodhd.com/api/search/{query}?api_token={self._api_key}&fmt=json"
        data: list[EodhdSearchResult] = requests.get(url, timeout=10).json()

        return [
            SecuritySearchResult(
                code=result["Code"],
                exchange=result["Exchange"],
                name=result["Name"],
                currency=result["Currency"],
                security_type=result["Type"],
                isin=result.get("ISIN"),
                country=result["Country"],
            )
            for result in data
        ]

    def get_price_on_date(
        self,
        security_id: SecurityId,
        symbol: str,
        exchange: str,
        date: date,
    ) -> HistoricalPrice | None:
        eodhd_symbol = f"{symbol}.{exchange}"
        data = self._client.get_historical_data(
            symbol=eodhd_symbol,
            interval="d",
            iso8601_start=date.isoformat(),
            iso8601_end=date.isoformat(),
        )

        try:
            price = data.iloc[0]
            return HistoricalPrice(
                security_id=security_id,
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
        self,
        security_id: SecurityId,
        symbol: str,
        exchange: str,
        from_date: date,
        to_date: date,
    ) -> list[HistoricalPrice]:
        eodhd_symbol = f"{symbol}.{exchange}"
        logger.info("Fetching data for security: %s", eodhd_symbol)

        data = self._client.get_historical_data(
            symbol=eodhd_symbol,
            interval="d",
            iso8601_start=from_date.isoformat(),
            iso8601_end=to_date.isoformat(),
        )

        prices: list[HistoricalPrice] = []
        for index, price in data.iterrows():
            if type(index) is not Timestamp:
                logger.error(
                    "Historical data index should be pandas.Timestamp but is: %s",
                    type(index),
                )
                continue

            prices.append(
                HistoricalPrice(
                    security_id=security_id,
                    date=index.date(),
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
    if settings.stub_external_api:
        from src.stubs.eodhd import StubEodhdGateway  # noqa: PLC0415

        return StubEodhdGateway(api_key=settings.eodhd_api_key)
    return EodhdGateway(api_key=settings.eodhd_api_key)
