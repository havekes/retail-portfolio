import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from time import perf_counter_ns

from src.market.api_types import (
    HistoricalPrice,
    IntradayHistoricalPrice,
    SecurityId,
    SecuritySearchResult,
)
from src.observability import emit_event

#: Internal telemetry dimension for the provider behind the market gateway.
#: Upstream provider identity is allowed in telemetry only — never in a user- or
#: agent-facing payload.
MARKET_DATA_PROVIDER = "eodhd"

logger = logging.getLogger(__name__)

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


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

    @abstractmethod
    def get_intraday_prices(  # noqa: PLR0913, PLR0917
        self,
        security_id: SecurityId,
        symbol: str,
        exchange: str,
        from_datetime: datetime,
        to_datetime: datetime,
        interval: str = "1h",
    ) -> list[IntradayHistoricalPrice]:
        """Get intraday prices for a security within a datetime range."""
        ...


def error_slug_from_exception(exc: BaseException) -> str:
    """Return a stable, low-cardinality failure class for an exception."""
    class_name = type(exc).__name__ or "exception"
    return _CAMEL_BOUNDARY.sub("_", class_name).lower() or "exception"


def freshness_lag_ms(value: date | datetime) -> int:
    """Return the age in milliseconds of a returned data point, never negative."""
    if isinstance(value, datetime):
        reference = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    else:
        reference = datetime.combine(value, time.min, tzinfo=UTC)
    return max(0, int((datetime.now(UTC) - reference).total_seconds() * 1000))


@dataclass
class MarketFetch:
    """
    Mutable accumulator yielded by ``record_fetch``.

    Call sites set ``row_count``/``freshness_lag_ms`` once the gateway result is
    known; ``cache_state`` defaults to ``miss`` because these paths always
    re-request from the provider.
    """

    cache_state: str | None = None
    freshness_lag_ms: int | None = None
    row_count: int | None = None


def emit_market_data_fetched(  # noqa: PLR0913
    *,
    symbol: str,
    dataset: str,
    provider: str,
    exchange: str | None = None,
    cache_state: str | None = None,
    freshness_lag_ms: int | None = None,
    duration_ms: float,
    outcome: str,
    row_count: int | None = None,
    error_slug: str | None = None,
) -> None:
    """
    Emit one ``market.data.fetched`` wide event.

    Flat primitive fields only: nested structures are neither needed nor wanted
    inside an event emitted underneath a request span.
    """
    emit_event(
        "market.data.fetched",
        symbol=symbol,
        dataset=dataset,
        provider=provider,
        exchange=exchange,
        cache_state=cache_state,
        freshness_lag_ms=freshness_lag_ms,
        duration_ms=duration_ms,
        outcome=outcome,
        row_count=row_count,
        error_slug=error_slug,
    )


@contextmanager
def record_fetch(
    *,
    symbol: str,
    dataset: str,
    provider: str = MARKET_DATA_PROVIDER,
    exchange: str | None = None,
    cache_state: str | None = "miss",
) -> Iterator[MarketFetch]:
    """
    Time one provider fetch and emit exactly one ``market.data.fetched`` event.

    Synchronous and thread-safe (plain ``perf_counter_ns``) so it can wrap calls
    dispatched through ``asyncio.to_thread`` from the caller's side. An exception
    from the wrapped call is reported with ``outcome="failure"`` and a stable
    ``error_slug``, then re-raised so existing handlers keep working. Failure
    telemetry is best-effort: it can never replace the provider exception it
    reports.
    """
    record = MarketFetch(cache_state=cache_state)
    started = perf_counter_ns()
    try:
        yield record
    except Exception as error:
        try:
            emit_market_data_fetched(
                symbol=symbol,
                dataset=dataset,
                provider=provider,
                exchange=exchange,
                cache_state=record.cache_state,
                freshness_lag_ms=record.freshness_lag_ms,
                duration_ms=(perf_counter_ns() - started) / 1_000_000,
                outcome="failure",
                row_count=record.row_count,
                error_slug=error_slug_from_exception(error),
            )
        except Exception as emit_error:  # noqa: BLE001
            logger.debug("Market fetch telemetry emission failed: %s", emit_error)
        raise
    else:
        emit_market_data_fetched(
            symbol=symbol,
            dataset=dataset,
            provider=provider,
            exchange=exchange,
            cache_state=record.cache_state,
            freshness_lag_ms=record.freshness_lag_ms,
            duration_ms=(perf_counter_ns() - started) / 1_000_000,
            outcome="success",
            row_count=record.row_count,
        )
