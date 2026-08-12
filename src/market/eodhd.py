import logging
from datetime import UTC, date, datetime
from decimal import Decimal

import requests
from eodhd.apiclient import APIClient
from pandas import Timestamp

from src.config.settings import settings
from src.market.api_types import (
    EodhdSearchResult,
    HistoricalPrice,
    IntradayHistoricalPrice,
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
        results = requests.get(url, timeout=10).json()

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
            for result in results
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

    def get_intraday_prices(  # noqa: PLR0913, PLR0917, PLR0912, C901
        self,
        security_id: SecurityId,
        symbol: str,
        exchange: str,
        from_datetime: datetime,
        to_datetime: datetime,
        interval: str = "1h",
    ) -> list[IntradayHistoricalPrice]:
        if interval != "1h":
            msg = f"Unsupported interval '{interval}'. Only '1h' interval is supported."
            raise ValueError(msg)

        eodhd_symbol = f"{symbol}.{exchange}"
        logger.info("Fetching intraday data for security: %s", eodhd_symbol)

        if from_datetime.tzinfo is None:
            from_datetime = from_datetime.replace(tzinfo=UTC)
        if to_datetime.tzinfo is None:
            to_datetime = to_datetime.replace(tzinfo=UTC)

        from_unix = int(from_datetime.timestamp())
        to_unix = int(to_datetime.timestamp())

        data = self._client.get_intraday_historical_data(
            symbol=eodhd_symbol,
            interval=interval,
            from_unix_time=from_unix,
            to_unix_time=to_unix,
        )

        prices: list[IntradayHistoricalPrice] = []
        if isinstance(data, list):
            for row in data:
                if "timestamp" in row and row["timestamp"] is not None:
                    dt = datetime.fromtimestamp(int(row["timestamp"]), tz=UTC)
                else:
                    dt = datetime.fromisoformat(str(row["datetime"]))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=UTC)

                open_val = Decimal(str(row["open"]))
                high_val = Decimal(str(row["high"]))
                low_val = Decimal(str(row["low"]))
                close_val = Decimal(str(row["close"]))
                volume_val = int(row["volume"]) if row.get("volume") is not None else 0

                if open_val == high_val == low_val == close_val and volume_val == 0:
                    continue

                prices.append(
                    IntradayHistoricalPrice(
                        security_id=security_id,
                        timestamp=dt,
                        open=open_val,
                        high=high_val,
                        low=low_val,
                        close=close_val,
                        volume=volume_val,
                    )
                )
        elif hasattr(data, "iterrows"):
            for index, row in data.iterrows():
                if "timestamp" in row and row["timestamp"] is not None:
                    dt = datetime.fromtimestamp(int(row["timestamp"]), tz=UTC)
                elif isinstance(index, Timestamp):
                    dt = index.to_pydatetime()
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=UTC)
                else:
                    dt = datetime.fromisoformat(str(row["datetime"]))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=UTC)

                open_val = Decimal(str(row["open"]))
                high_val = Decimal(str(row["high"]))
                low_val = Decimal(str(row["low"]))
                close_val = Decimal(str(row["close"]))
                volume_val = int(row["volume"]) if row.get("volume") is not None else 0

                if open_val == high_val == low_val == close_val and volume_val == 0:
                    continue

                prices.append(
                    IntradayHistoricalPrice(
                        security_id=security_id,
                        timestamp=dt,
                        open=open_val,
                        high=high_val,
                        low=low_val,
                        close=close_val,
                        volume=volume_val,
                    )
                )

        return prices


def eodhd_gateway_factory():
    if settings.stub_external_api:
        from src.stubs.eodhd import StubEodhdGateway  # noqa: PLC0415

        return StubEodhdGateway(api_key=settings.eodhd_api_key)
    return EodhdGateway(api_key=settings.eodhd_api_key)
