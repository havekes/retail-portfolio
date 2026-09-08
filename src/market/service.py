import asyncio
import logging
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
from fastapi import HTTPException, status
from svcs import Container

from src.config.settings import settings
from src.market.gateway import MarketGateway
from src.market.model import IntradayPriceModel, PriceModel
from src.market.repository import (
    IntradayPriceRepository,
    PriceRepository,
    SecurityRepository,
)
from src.market.schema import (
    IndicatorCandleSchema,
    IndicatorSpecSchema,
    IntradayPriceSchema,
    PriceSchema,
    SecuritySchema,
)

logger = logging.getLogger(__name__)


def aggregate_weekly_prices(
    prices: Sequence[PriceSchema | PriceModel],
) -> list[PriceSchema]:
    """
    Aggregate daily prices into weekly candles.
    Group daily prices by ISO year and week, setting open to first candle open,
    high to max high, low to min low, close to last candle close, adjusted_close
    to last candle adjusted_close, and summing volume.
    """
    if not prices:
        return []

    sorted_prices = sorted(prices, key=lambda p: p.date)
    grouped: dict[tuple[int, int], list[PriceSchema | PriceModel]] = {}

    for price in sorted_prices:
        iso_year, iso_week, _ = price.date.isocalendar()
        key = (iso_year, iso_week)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(price)

    return [
        PriceSchema(
            security_id=group[0].security_id,
            date=group[0].date,
            open=group[0].open,
            high=max(p.high for p in group),
            low=min(p.low for p in group),
            close=group[-1].close,
            adjusted_close=group[-1].adjusted_close,
            volume=sum(p.volume for p in group),
        )
        for group in grouped.values()
    ]


def aggregate_monthly_prices(
    prices: Sequence[PriceSchema | PriceModel],
) -> list[PriceSchema]:
    """
    Aggregate daily prices into monthly candles.
    Group daily prices by year and month, setting open to first candle open,
    high to max high, low to min low, close to last candle close, adjusted_close
    to last candle adjusted_close, and summing volume.
    """
    if not prices:
        return []

    sorted_prices = sorted(prices, key=lambda p: p.date)
    grouped: dict[tuple[int, int], list[PriceSchema | PriceModel]] = {}

    for price in sorted_prices:
        key = (price.date.year, price.date.month)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(price)

    return [
        PriceSchema(
            security_id=group[0].security_id,
            date=group[0].date,
            open=group[0].open,
            high=max(p.high for p in group),
            low=min(p.low for p in group),
            close=group[-1].close,
            adjusted_close=group[-1].adjusted_close,
            volume=sum(p.volume for p in group),
        )
        for group in grouped.values()
    ]


def aggregate_4h_candles(
    candles: Sequence[IntradayPriceSchema | IntradayPriceModel],
) -> list[IntradayPriceSchema]:
    """
    Aggregate 1-hour candles into 4-hour candles.
    Group 1h candles into 4-hour buckets, setting open to first candle open,
    high to max high, low to min low, close to last candle close, and summing volume.
    """
    if not candles:
        return []

    sorted_candles = sorted(candles, key=lambda c: c.timestamp)
    grouped: dict[datetime, list[IntradayPriceSchema | IntradayPriceModel]] = {}

    for candle in sorted_candles:
        ts = candle.timestamp
        bucket_ts = ts.replace(
            hour=(ts.hour // 4) * 4, minute=0, second=0, microsecond=0
        )
        if bucket_ts not in grouped:
            grouped[bucket_ts] = []
        grouped[bucket_ts].append(candle)

    aggregated: list[IntradayPriceSchema] = []
    for bucket_ts, group in grouped.items():
        aggregated.append(
            IntradayPriceSchema(
                security_id=group[0].security_id,
                timestamp=bucket_ts,
                open=group[0].open,
                high=max(c.high for c in group),
                low=min(c.low for c in group),
                close=group[-1].close,
                volume=sum(c.volume for c in group),
            )
        )

    return aggregated


class PriceAggregationService:
    @staticmethod
    def aggregate_weekly_prices(
        prices: Sequence[PriceSchema | PriceModel],
    ) -> list[PriceSchema]:
        return aggregate_weekly_prices(prices)

    @staticmethod
    def aggregate_monthly_prices(
        prices: Sequence[PriceSchema | PriceModel],
    ) -> list[PriceSchema]:
        return aggregate_monthly_prices(prices)

    @staticmethod
    def aggregate_4h_candles(
        candles: Sequence[IntradayPriceSchema | IntradayPriceModel],
    ) -> list[IntradayPriceSchema]:
        return aggregate_4h_candles(candles)


class MarketService:
    _gateway: MarketGateway
    _price_repository: PriceRepository
    _security_repository: SecurityRepository
    _intraday_price_repository: IntradayPriceRepository

    def __init__(
        self,
        gateway: MarketGateway,
        price_repository: PriceRepository,
        security_repository: SecurityRepository,
        intraday_price_repository: IntradayPriceRepository,
    ):
        self._gateway = gateway
        self._price_repository = price_repository
        self._security_repository = security_repository
        self._intraday_price_repository = intraday_price_repository

    async def _update_security_prices(
        self, security: SecuritySchema, from_date: date, to_date: date
    ) -> bool:
        try:
            # Gateway returns a list of HistoricalPrice
            prices = await asyncio.to_thread(
                self._gateway.get_prices,
                security.id,
                security.symbol,
                security.exchange,
                from_date=from_date,
                to_date=to_date,
            )
        except Exception:
            # Catching general Exception to prevent one failure from stopping jobs
            logger.exception("Failed to update prices for security %s", security.symbol)
            return False
        else:
            if prices:
                price_schemas = [PriceSchema.from_historical_price(p) for p in prices]
                await self._price_repository.save_prices(price_schemas)
            return True

    async def update_daily_prices_for_all_securities(self) -> dict[str, int]:
        """Fetches all securities and updates their prices for the last year.

        Returns a dict containing 'success' and 'failure' counts.
        """
        securities = await self._security_repository.get_all_active_securities()

        # We'll fetch prices for the last year as per the issue comment
        to_date = datetime.now(UTC).date()
        from_date = to_date - timedelta(days=365)

        results = await asyncio.gather(
            *(
                self._update_security_prices(security, from_date, to_date)
                for security in securities
            )
        )

        success_count = sum(1 for result in results if result)
        failure_count = sum(1 for result in results if not result)

        return {"success": success_count, "failure": failure_count}

    async def _update_security_intraday_prices(
        self, security: SecuritySchema, from_datetime: datetime, to_datetime: datetime
    ) -> bool:
        try:
            prices = await asyncio.to_thread(
                self._gateway.get_intraday_prices,
                security.id,
                security.symbol,
                security.exchange,
                from_datetime=from_datetime,
                to_datetime=to_datetime,
                interval="1h",
            )
        except Exception:
            logger.exception(
                "Failed to update intraday prices for security %s", security.symbol
            )
            return False
        else:
            if prices:
                price_schemas = [
                    IntradayPriceSchema.model_validate(p, from_attributes=True)
                    for p in prices
                ]
                await self._intraday_price_repository.save_intraday_prices(
                    price_schemas
                )
            return True

    async def update_intraday_prices_for_all_securities(self) -> dict[str, int]:
        """Fetches active securities and updates 1h intraday prices for last 7 days.

        Returns a dict containing 'success' and 'failure' counts.
        """
        securities = await self._security_repository.get_all_active_securities()

        to_datetime = datetime.now(UTC)
        from_datetime = to_datetime - timedelta(days=7)

        results = await asyncio.gather(
            *(
                self._update_security_intraday_prices(
                    security, from_datetime, to_datetime
                )
                for security in securities
            )
        )

        success_count = sum(1 for result in results if result)
        failure_count = sum(1 for result in results if not result)

        return {"success": success_count, "failure": failure_count}

    async def fetch_and_save_intraday_prices(
        self,
        security: SecuritySchema,
        days: int = 30,
        from_datetime: datetime | None = None,
        to_datetime: datetime | None = None,
    ) -> bool:
        to_dt = to_datetime or datetime.now(UTC)
        from_dt = from_datetime or (to_dt - timedelta(days=days))
        return await self._update_security_intraday_prices(security, from_dt, to_dt)

    async def fetch_and_save_price_history(self, security: SecuritySchema) -> bool:
        """Fetch price history for a security from 2000-01-03 to today and save it.

        Returns True if successful, False otherwise.
        """
        try:
            from_date = date(2000, 1, 3)
            to_date = datetime.now(UTC).date()

            prices = self._gateway.get_prices(
                security.id,
                security.symbol,
                security.exchange,
                from_date=from_date,
                to_date=to_date,
            )

            if prices:
                price_schemas = [PriceSchema.from_historical_price(p) for p in prices]
                await self._price_repository.save_prices(price_schemas)
                logger.info(
                    "Fetched and saved %d prices for security %s",
                    len(prices),
                    security.symbol,
                )
                return True
        except Exception:
            logger.exception(
                "Failed to fetch and save price history for security %s",
                security.symbol,
            )
        return False


async def market_service_factory(container: Container) -> MarketService:
    return MarketService(
        gateway=await container.aget(MarketGateway),
        price_repository=await container.aget(PriceRepository),
        security_repository=await container.aget(SecurityRepository),
        intraday_price_repository=await container.aget(IntradayPriceRepository),
    )


def convert_to_heikin_ashi(
    candles: Sequence[IndicatorCandleSchema],
) -> list[IndicatorCandleSchema]:
    """
    Convert regular OHLCV candles to Heikin-Ashi candles.

    Formulas:
    - First candle:
        ha_close = (open + high + low + close) / 4
        ha_open = (open + close) / 2
        ha_high = max(high, ha_open, ha_close)
        ha_low = min(low, ha_open, ha_close)
    - Subsequent candles:
        ha_close = (open + high + low + close) / 4
        ha_open = (prev_ha_open + prev_ha_close) / 2
        ha_high = max(high, ha_open, ha_close)
        ha_low = min(low, ha_open, ha_close)
    """
    if not candles:
        return []

    result: list[IndicatorCandleSchema] = []
    prev_open: float = 0.0
    prev_close: float = 0.0

    for i, candle in enumerate(candles):
        ha_close = (candle.open + candle.high + candle.low + candle.close) / 4.0

        if i == 0:
            ha_open = (candle.open + candle.close) / 2.0
        else:
            ha_open = (prev_open + prev_close) / 2.0

        ha_high = max(candle.high, ha_open, ha_close)
        ha_low = min(candle.low, ha_open, ha_close)

        prev_open = ha_open
        prev_close = ha_close

        result.append(
            IndicatorCandleSchema(
                time=candle.time,
                open=ha_open,
                high=ha_high,
                low=ha_low,
                close=ha_close,
                volume=candle.volume,
            )
        )

    return result


class IndicatorServiceClient:
    """Client for calling external Go indicator sidecar microservice."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = client

    async def compute(
        self,
        interval: str,
        candles: Sequence[IndicatorCandleSchema],
        indicators: Sequence[IndicatorSpecSchema],
    ) -> dict[str, Any]:
        payload = {
            "interval": interval,
            "candles": [
                c.model_dump() if hasattr(c, "model_dump") else c for c in candles
            ],
            "indicators": [
                i.model_dump(by_alias=True, exclude_none=True)
                if hasattr(i, "model_dump")
                else i
                for i in indicators
            ],
        }
        url = f"{self.base_url}/compute"

        try:
            if self._client is not None:
                response = await self._client.post(
                    url, json=payload, timeout=self.timeout
                )
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            logger.warning("Indicator service timed out: %s", exc)
            raise HTTPException(
                status_code=504, detail="Indicator service timed out"
            ) from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            logger.warning("Indicator service network error: %s", exc)
            raise HTTPException(
                status_code=503, detail="Indicator service unavailable"
            ) from exc

        if response.status_code == status.HTTP_400_BAD_REQUEST:
            try:
                err_data = response.json()
                detail = err_data.get("error", response.text)
            except Exception:  # noqa: BLE001
                detail = response.text
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

        if response.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Indicator service unavailable",
            )

        if response.status_code != status.HTTP_200_OK:
            raise HTTPException(status_code=response.status_code, detail=response.text)

        data = response.json()
        if isinstance(data, dict) and "indicators" in data:
            return data["indicators"]
        return data


async def indicator_service_client_factory(
    _container: Container | None = None,
) -> IndicatorServiceClient:
    return IndicatorServiceClient(base_url=settings.indicator_service_url)
