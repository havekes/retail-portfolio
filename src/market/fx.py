"""Foreign-exchange rate provider backed by a daily ECB refresh.

The ``currencyconverter`` package ships an ECB snapshot that goes stale as soon
as the package is installed. A daily Huey task downloads the current ECB
history and stores it in Redis, which both the backend and the worker share.
:class:`FxRateProvider` then builds a :class:`CurrencyConverter` from that
snapshot, caches it in-process until the stored fetch date changes, and falls
back to the bundled snapshot when Redis has nothing (or is unreachable).
"""

import base64
import logging
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import httpx
from currency_converter import ECB_URL, CurrencyConverter
from redis.asyncio.client import Redis
from redis.exceptions import RedisError

from src.core.redis import RedisManager
from src.core.redis import redis_manager as default_redis_manager

logger = logging.getLogger(__name__)

ECB_ZIP_KEY = "fx:ecb:zip"
ECB_FETCHED_AT_KEY = "fx:ecb:fetched_at"

# Warn once the freshest ECB rate is older than this many business days.
STALE_AFTER_BUSINESS_DAYS = 3

# ``date.weekday()`` for Saturday; Monday is 0, so anything below this is a
# business day (Monday through Friday).
_SATURDAY_WEEKDAY = 5


def _business_days_old(last_date: date, today: date) -> int:
    """Count business days between ``last_date`` (exclusive) and ``today``."""
    days = 0
    cursor = last_date
    while cursor < today:
        cursor += timedelta(days=1)
        if cursor.weekday() < _SATURDAY_WEEKDAY:
            days += 1
    return days


def _last_rate_date(converter: CurrencyConverter) -> date:
    """Return the most recent rate date across every currency in ``converter``."""
    bounds = cast("dict[str, Any]", converter.bounds)
    return max(bound.last_date for bound in bounds.values())


async def refresh_fx_rates(redis: Redis, http_client: httpx.AsyncClient) -> None:
    """Download the ECB history and store the zip plus fetch date in Redis.

    The zip is base64-encoded because the shared ``redis_manager`` client
    decodes responses as text and cannot round-trip binary payloads.
    """
    response = await http_client.get(ECB_URL)
    response.raise_for_status()

    zip_bytes = response.content
    fetched_at = datetime.now(UTC).date().isoformat()

    await redis.set(ECB_ZIP_KEY, base64.b64encode(zip_bytes).decode("ascii"))
    await redis.set(ECB_FETCHED_AT_KEY, fetched_at)

    logger.info(
        "Refreshed ECB FX rates: fetched_at=%s, %d bytes", fetched_at, len(zip_bytes)
    )


class FxRateProvider:
    """Provides a :class:`CurrencyConverter` built from Redis-cached ECB data."""

    def __init__(
        self,
        redis_manager: RedisManager | None = None,
        fallback_currency_file: str | None = None,
    ) -> None:
        self._redis_manager = redis_manager or default_redis_manager
        self._fallback_currency_file = fallback_currency_file
        self._converter: CurrencyConverter | None = None
        self._cached_fetched_at: str | None = None
        self._has_cache = False

    async def converter(self) -> CurrencyConverter:
        """Return the current converter, reloading it when the fetch date changes.

        Falls back to the bundled ``currencyconverter`` snapshot when Redis has
        no cached data or cannot be reached. The zip is parsed once per refresh.
        """
        try:
            async with self._redis_manager.client() as redis:
                zip_payload: str | None = cast(
                    "str | None", await redis.get(ECB_ZIP_KEY)
                )
                fetched_at: str | None = cast(
                    "str | None", await redis.get(ECB_FETCHED_AT_KEY)
                )
        except RedisError as exc:
            logger.warning(
                "FX rate provider: Redis unavailable (%s); "
                "falling back to bundled ECB rates",
                exc,
            )
            return self._fallback(cache=False)

        if not zip_payload or not fetched_at:
            logger.warning(
                "FX rate provider: no cached ECB rates in Redis; "
                "falling back to bundled ECB rates"
            )
            return self._fallback(cache=True)

        if (
            self._has_cache
            and fetched_at == self._cached_fetched_at
            and self._converter is not None
        ):
            return self._converter

        converter = self._build_converter(zip_payload)
        self._converter = converter
        self._cached_fetched_at = fetched_at
        self._has_cache = True
        self._log_if_stale(converter)
        return converter

    async def as_of(self) -> date:
        """Return the most recent ECB rate date in the active converter."""
        return _last_rate_date(await self.converter())

    def _build_converter(self, zip_payload: str) -> CurrencyConverter:
        """Write the cached zip to a temp file and parse it once."""
        zip_bytes = base64.b64decode(zip_payload)
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp.write(zip_bytes)
            tmp_path = tmp.name
        try:
            converter = CurrencyConverter(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        return converter

    def _fallback(self, *, cache: bool) -> CurrencyConverter:
        """Return the bundled converter, optionally caching it for later calls."""
        if (
            cache
            and self._has_cache
            and self._cached_fetched_at is None
            and self._converter is not None
        ):
            return self._converter

        converter = (
            CurrencyConverter(self._fallback_currency_file)
            if self._fallback_currency_file
            else CurrencyConverter()
        )
        if cache:
            self._converter = converter
            self._cached_fetched_at = None
            self._has_cache = True
        self._log_if_stale(converter)
        return converter

    @staticmethod
    def _log_if_stale(converter: CurrencyConverter) -> None:
        """Warn when the converter's freshest rate is too old."""
        last_date = _last_rate_date(converter)
        age = _business_days_old(last_date, datetime.now(UTC).date())
        if age > STALE_AFTER_BUSINESS_DAYS:
            logger.warning(
                "FX rate provider: ECB rates are stale — last date %s "
                "(%d business days old)",
                last_date,
                age,
            )


async def fx_rate_provider_factory() -> FxRateProvider:
    """Create an :class:`FxRateProvider` backed by the shared Redis manager."""
    return FxRateProvider(redis_manager=default_redis_manager)
