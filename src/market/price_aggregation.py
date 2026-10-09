from __future__ import annotations

import itertools
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import HTTPException

from src.market.schema import PriceBar

PriceInterval = Literal["day", "week", "month"]
MAX_PRICE_BARS = 2000
_WEEKEND_START = 5
_DAYS_PER_WEEK = 7
_WEEKDAYS_PER_WEEK = 5
_MONTHS_PER_YEAR = 12


def count_weekdays(start: date, end: date) -> int:
    """Count weekdays (Monday through Friday) in [start, end] inclusive."""
    days = (end - start).days + 1
    full_weeks, extra = divmod(days, _DAYS_PER_WEEK)
    count = full_weeks * _WEEKDAYS_PER_WEEK
    for i in range(extra):
        cur = start + timedelta(days=full_weeks * _DAYS_PER_WEEK + i)
        if cur.weekday() < _WEEKEND_START:
            count += 1
    return count


def count_iso_weeks(start: date, end: date) -> int:
    """Count distinct ISO calendar weeks spanned by [start, end] inclusive."""
    start_monday = start - timedelta(days=start.weekday())
    end_sunday = end + timedelta(days=_DAYS_PER_WEEK - 1 - end.weekday())
    return (end_sunday - start_monday).days // _DAYS_PER_WEEK + 1


def count_calendar_months(start: date, end: date) -> int:
    """Count distinct calendar months spanned by [start, end] inclusive."""
    return (end.year - start.year) * _MONTHS_PER_YEAR + end.month - start.month + 1


def resolve_price_range(
    from_: date | None,
    to: date | None,
    interval: PriceInterval = "day",
    today: date | None = None,
) -> tuple[date, date]:
    """Resolve default dates and validate bar count cap for the given interval.

    If ``to`` is omitted, it defaults to today (UTC).
    If ``from_`` is omitted, it defaults to ``to`` minus 365 days.

    Raises:
        HTTPException(422): If ``from_ > to`` or if estimated bar count exceeds
            MAX_PRICE_BARS.
    """
    if to is None:
        to = today if today is not None else datetime.now(UTC).date()
    if from_ is None:
        from_ = to - timedelta(days=365)

    if from_ > to:
        raise HTTPException(
            status_code=422,
            detail="from must be less than or equal to to",
        )

    if interval == "day":
        estimated_bars = count_weekdays(from_, to)
        coarser_msg = " or use a coarser interval ('week' or 'month')"
    elif interval == "week":
        estimated_bars = count_iso_weeks(from_, to)
        coarser_msg = " or use a coarser interval ('month')"
    elif interval == "month":
        estimated_bars = count_calendar_months(from_, to)
        coarser_msg = ""
    else:
        detail = f"Unsupported interval '{interval}'. Use 'day', 'week', or 'month'."
        raise HTTPException(
            status_code=422,
            detail=detail,
        )

    if estimated_bars > MAX_PRICE_BARS:
        detail = (
            f"Requested range spans ~{estimated_bars} bars, exceeding the limit of "
            f"{MAX_PRICE_BARS}. Narrow the date range{coarser_msg}."
        )
        raise HTTPException(
            status_code=422,
            detail=detail,
        )

    return from_, to


def aggregate_bars(
    bars: list[PriceBar],
    interval: PriceInterval,
) -> list[PriceBar]:
    """Aggregate daily OHLCV bars into weekly or monthly bars.

    Aggregation rules for weekly/monthly buckets:
    - open: first open in bucket
    - high: maximum high in bucket
    - low: minimum low in bucket
    - close: last close in bucket
    - volume: sum of volume in bucket
    - adjusted_close: last adjusted_close in bucket
    - date: last trading date in bucket

    Weeks are ISO calendar weeks; months are calendar months.
    """
    if not bars:
        return []

    sorted_bars = sorted(bars, key=lambda b: b.date)

    if interval == "day":
        return sorted_bars

    key_func: Callable[[PriceBar], tuple[int, int]]
    if interval == "week":

        def _week_key(b: PriceBar) -> tuple[int, int]:
            return b.date.isocalendar()[:2]

        key_func = _week_key
    elif interval == "month":

        def _month_key(b: PriceBar) -> tuple[int, int]:
            return (b.date.year, b.date.month)

        key_func = _month_key
    else:
        msg = f"Unsupported interval: '{interval}'"
        raise ValueError(msg)

    aggregated: list[PriceBar] = []
    for _, group in itertools.groupby(sorted_bars, key=key_func):
        bucket_bars = list(group)
        aggregated.append(
            PriceBar(
                date=bucket_bars[-1].date,
                open=bucket_bars[0].open,
                high=max(b.high for b in bucket_bars),
                low=min(b.low for b in bucket_bars),
                close=bucket_bars[-1].close,
                volume=sum(b.volume for b in bucket_bars),
                adjusted_close=bucket_bars[-1].adjusted_close,
            )
        )

    return aggregated
