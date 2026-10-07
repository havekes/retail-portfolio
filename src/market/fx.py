"""Foreign-exchange rate provider backed by a daily ECB refresh.

The ``currencyconverter`` package ships an ECB snapshot that goes stale as soon
as the package is installed. A daily Huey task downloads the current ECB
history and stores it in Redis, which both the backend and the worker share.
:class:`FxRateProvider` then builds a :class:`CurrencyConverter` from that
snapshot, caches it in-process until the stored fetch date changes, and falls
back to the bundled snapshot when Redis has nothing (or is unreachable).

The parsed converter is cached at module level (keyed by the fetch date), not
per provider instance: providers are request-scoped in svcs, so an instance
cache would re-parse the whole ECB CSV on every request.
"""

import asyncio
import base64
import io
import logging
import tempfile
import zipfile
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

# Process-level caches: {fetch date -> parsed converter}. Providers are
# request-scoped, so this must outlive any single instance for the zip to be
# parsed once per refresh.
_converter_by_fetched_at: dict[str, CurrencyConverter] = {}
# {bundled currency file -> parsed fallback converter}.
_fallback_converters: dict[str | None, CurrencyConverter] = {}
# Per-event-loop build locks (one loop per asyncio.run() in the worker/tests).
_build_locks: dict[asyncio.AbstractEventLoop, asyncio.Lock] = {}

_MAX_CACHED_CONVERTERS = 4

# ``date.weekday()`` for Saturday; Monday is 0, so anything below this is a
# business day (Monday through Friday).
_SATURDAY_WEEKDAY = 5


def _get_build_lock() -> asyncio.Lock:
    """Return the build lock for the running event loop, creating it if needed."""
    for closed_loop in [loop for loop in _build_locks if loop.is_closed()]:
        _build_locks.pop(closed_loop, None)

    loop = asyncio.get_running_loop()
    lock = _build_locks.get(loop)
    if lock is None:
        lock = asyncio.Lock()
        _build_locks[loop] = lock
    return lock


def _prune_converter_cache() -> None:
    """Keep the process-level converter cache bounded (oldest first)."""
    while len(_converter_by_fetched_at) > _MAX_CACHED_CONVERTERS:
        oldest = next(iter(_converter_by_fetched_at))
        del _converter_by_fetched_at[oldest]


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


def _validate_zip(zip_bytes: bytes) -> None:
    """Reject a download that is not a readable zip archive."""
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            archive.namelist()
    except zipfile.BadZipFile as exc:
        msg = "ECB FX download is not a valid zip archive"
        raise ValueError(msg) from exc


async def refresh_fx_rates(redis: Redis, http_client: httpx.AsyncClient) -> None:
    """Download the ECB history and store the zip plus fetch date in Redis.

    The zip is base64-encoded because the shared ``redis_manager`` client
    decodes responses as text and cannot round-trip binary payloads. Both keys
    are written atomically with ``MSET`` so the zip and its fetch date can never
    drift apart.
    """
    response = await http_client.get(ECB_URL)
    response.raise_for_status()

    zip_bytes = response.content
    _validate_zip(zip_bytes)
    fetched_at = datetime.now(UTC).date().isoformat()

    await redis.mset(
        {
            ECB_ZIP_KEY: base64.b64encode(zip_bytes).decode("ascii"),
            ECB_FETCHED_AT_KEY: fetched_at,
        }
    )

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

    async def converter(self) -> CurrencyConverter:
        """Return the current converter, reloading it when the fetch date changes.

        Falls back to the bundled ``currencyconverter`` snapshot when Redis has
        no cached data, cannot be reached, or holds an unreadable zip. The zip
        is parsed once per fetch date for the whole process.
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
            return await self._fallback()

        if not zip_payload or not fetched_at:
            logger.warning(
                "FX rate provider: no cached ECB rates in Redis; "
                "falling back to bundled ECB rates"
            )
            return await self._fallback()

        cached = _converter_by_fetched_at.get(fetched_at)
        if cached is not None:
            return cached

        async with _get_build_lock():
            cached = _converter_by_fetched_at.get(fetched_at)
            if cached is not None:
                return cached
            try:
                converter = await asyncio.to_thread(self._build_converter, zip_payload)
            except Exception:
                logger.exception(
                    "FX rate provider: cached ECB zip is unreadable; "
                    "falling back to bundled ECB rates"
                )
            else:
                _converter_by_fetched_at[fetched_at] = converter
                _prune_converter_cache()
                _log_if_stale(converter)
                return converter

        return await self._fallback()

    async def as_of(self) -> date:
        """Return the most recent ECB rate date in the active converter."""
        return _last_rate_date(await self.converter())

    async def _fallback(self) -> CurrencyConverter:
        """Return the bundled converter, parsed once per process."""
        key = self._fallback_currency_file
        cached = _fallback_converters.get(key)
        if cached is not None:
            return cached

        async with _get_build_lock():
            cached = _fallback_converters.get(key)
            if cached is not None:
                return cached
            converter = await asyncio.to_thread(self._load_bundled)
            _fallback_converters[key] = converter
            _log_if_stale(converter)
            return converter

    def _load_bundled(self) -> CurrencyConverter:
        if self._fallback_currency_file:
            return CurrencyConverter(self._fallback_currency_file)
        return CurrencyConverter()

    def _build_converter(self, zip_payload: str) -> CurrencyConverter:
        """Write the cached zip to a temp file and parse it."""
        zip_bytes = base64.b64decode(zip_payload)
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp.write(zip_bytes)
            tmp_path = tmp.name
        try:
            converter = CurrencyConverter(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        return converter


async def fx_rate_provider_factory() -> FxRateProvider:
    """Create an :class:`FxRateProvider` backed by the shared Redis manager."""
    return FxRateProvider(redis_manager=default_redis_manager)
