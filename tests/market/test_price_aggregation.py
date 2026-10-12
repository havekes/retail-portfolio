from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import cast

from fastapi import HTTPException
import pytest

from src.market.price_aggregation import (
    MAX_PRICE_BARS,
    PriceInterval,
    aggregate_bars,
    count_calendar_months,
    count_iso_weeks,
    count_weekdays,
    resolve_price_range,
)
from src.market.schema import PriceBar


def _bar(
    d: date,
    open_: str = "100.0",
    high: str = "110.0",
    low: str = "95.0",
    close: str = "105.0",
    volume: int = 1000,
    adjusted_close: str = "104.0",
) -> PriceBar:
    return PriceBar(
        date=d,
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=volume,
        adjusted_close=Decimal(adjusted_close),
    )


def test_aggregate_bars_empty() -> None:
    assert aggregate_bars([], "day") == []
    assert aggregate_bars([], "week") == []
    assert aggregate_bars([], "month") == []


def test_aggregate_bars_day() -> None:
    b1 = _bar(date(2024, 1, 2))
    b2 = _bar(date(2024, 1, 3))
    assert aggregate_bars([b2, b1], "day") == [b1, b2]


def test_aggregate_bars_invalid_interval() -> None:
    b1 = _bar(date(2024, 1, 2))
    with pytest.raises(ValueError, match="Unsupported interval"):
        aggregate_bars([b1], cast(PriceInterval, "year"))


def test_aggregate_bars_partial_week_and_month_boundary() -> None:
    # Series spanning month boundary across ISO weeks:
    # ISO week 2024-W05:
    #   2024-01-29 (Mon): open 100, high 105, low 98,  close 102, vol 100, adj 101
    #   2024-01-30 (Tue): open 102, high 108, low 101, close 107, vol 150, adj 106
    #   2024-01-31 (Wed): open 107, high 112, low 106, close 110, vol 200, adj 109
    #   2024-02-01 (Thu): open 110, high 115, low 108, close 112, vol 250, adj 111
    #   2024-02-02 (Fri): open 112, high 114, low 105, close 108, vol 300, adj 107
    # ISO week 2024-W06 (partial week - only 2 trading days):
    #   2024-02-05 (Mon): open 108, high 110, low 104, close 106, vol 120, adj 105
    #   2024-02-06 (Tue): open 106, high 109, low 103, close 104, vol 180, adj 103
    bars = [
        _bar(date(2024, 1, 29), "100", "105", "98", "102", 100, "101"),
        _bar(date(2024, 1, 30), "102", "108", "101", "107", 150, "106"),
        _bar(date(2024, 1, 31), "107", "112", "106", "110", 200, "109"),
        _bar(date(2024, 2, 1), "110", "115", "108", "112", 250, "111"),
        _bar(date(2024, 2, 2), "112", "114", "105", "108", 300, "107"),
        _bar(date(2024, 2, 5), "108", "110", "104", "106", 120, "105"),
        _bar(date(2024, 2, 6), "106", "109", "103", "104", 180, "103"),
    ]

    # Weekly aggregation
    weekly = aggregate_bars(bars, "week")
    assert len(weekly) == 2

    # Week 1: Mon Jan 29 to Fri Feb 2
    assert weekly[0].date == date(2024, 2, 2)
    assert weekly[0].open == Decimal("100")
    assert weekly[0].high == Decimal("115")
    assert weekly[0].low == Decimal("98")
    assert weekly[0].close == Decimal("108")
    assert weekly[0].volume == 100 + 150 + 200 + 250 + 300  # 1000
    assert weekly[0].adjusted_close == Decimal("107")

    # Week 2: Mon Feb 5 to Tue Feb 6 (partial week)
    assert weekly[1].date == date(2024, 2, 6)
    assert weekly[1].open == Decimal("108")
    assert weekly[1].high == Decimal("110")
    assert weekly[1].low == Decimal("103")
    assert weekly[1].close == Decimal("104")
    assert weekly[1].volume == 120 + 180  # 300
    assert weekly[1].adjusted_close == Decimal("103")

    # Monthly aggregation
    monthly = aggregate_bars(bars, "month")
    assert len(monthly) == 2

    # Month 1: Jan 2024 (Jan 29, 30, 31)
    assert monthly[0].date == date(2024, 1, 31)
    assert monthly[0].open == Decimal("100")
    assert monthly[0].high == Decimal("112")
    assert monthly[0].low == Decimal("98")
    assert monthly[0].close == Decimal("110")
    assert monthly[0].volume == 100 + 150 + 200  # 450
    assert monthly[0].adjusted_close == Decimal("109")

    # Month 2: Feb 2024 (Feb 1, 2, 5, 6)
    assert monthly[1].date == date(2024, 2, 6)
    assert monthly[1].open == Decimal("110")
    assert monthly[1].high == Decimal("115")
    assert monthly[1].low == Decimal("103")
    assert monthly[1].close == Decimal("104")
    assert monthly[1].volume == 250 + 300 + 120 + 180  # 850
    assert monthly[1].adjusted_close == Decimal("103")


def test_aggregate_bars_120_months_2015_to_2024() -> None:
    # 2015-01-01 to 2024-12-31 spans 120 months.
    # Provide 2 daily bars per month (day 1 and day 15).
    bars: list[PriceBar] = []
    for year in range(2015, 2025):
        for month in range(1, 13):
            d1 = date(year, month, 1)
            d2 = date(year, month, 15)
            bars.append(_bar(d1, open_="50", high="60", low="45", close="55", volume=100))
            bars.append(_bar(d2, open_="55", high="70", low="50", close="65", volume=200))

    monthly = aggregate_bars(bars, "month")
    assert len(monthly) == 120
    assert monthly[0].date == date(2015, 1, 15)
    assert monthly[0].open == Decimal("50")
    assert monthly[0].high == Decimal("70")
    assert monthly[0].low == Decimal("45")
    assert monthly[0].close == Decimal("65")
    assert monthly[0].volume == 300
    assert monthly[-1].date == date(2024, 12, 15)


def test_resolve_price_range_defaults() -> None:
    today = date(2024, 6, 1)
    resolved_from, resolved_to = resolve_price_range(None, None, today=today)
    assert resolved_to == today
    assert resolved_from == today - timedelta(days=365)

    # Only to provided
    resolved_from, resolved_to = resolve_price_range(None, date(2023, 12, 31), today=today)
    assert resolved_to == date(2023, 12, 31)
    assert resolved_from == date(2023, 12, 31) - timedelta(days=365)

    # Only from provided
    resolved_from, resolved_to = resolve_price_range(date(2024, 1, 1), None, today=today)
    assert resolved_to == today
    assert resolved_from == date(2024, 1, 1)


def test_resolve_price_range_from_after_to() -> None:
    with pytest.raises(HTTPException) as exc_info:
        resolve_price_range(date(2024, 2, 1), date(2024, 1, 1))
    assert exc_info.value.status_code == 422
    assert "from must be less than or equal to to" in exc_info.value.detail


def test_resolve_price_range_five_year_daily_ok() -> None:
    # 2019-10-01..2024-09-30 at interval=day succeeds (<=2,000 weekdays)
    weekdays = count_weekdays(date(2019, 10, 1), date(2024, 9, 30))
    assert weekdays == 1305
    assert weekdays <= MAX_PRICE_BARS

    rf, rt = resolve_price_range(date(2019, 10, 1), date(2024, 9, 30), interval="day")
    assert rf == date(2019, 10, 1)
    assert rt == date(2024, 9, 30)


def test_resolve_price_range_over_2000_weekdays_raises_422() -> None:
    # 2015-01-01 to 2024-12-31 spans 2,609 weekdays > 2000
    with pytest.raises(HTTPException) as exc_info:
        resolve_price_range(date(2015, 1, 1), date(2024, 12, 31), interval="day")
    assert exc_info.value.status_code == 422
    detail = exc_info.value.detail
    assert "2609" in detail
    assert "2000" in detail
    assert "week" in detail
    assert "month" in detail


def test_resolve_price_range_week_and_month_intervals() -> None:
    # 120 months for interval=month succeeds
    months = count_calendar_months(date(2015, 1, 1), date(2024, 12, 31))
    assert months == 120
    rf, rt = resolve_price_range(date(2015, 1, 1), date(2024, 12, 31), interval="month")
    assert rf == date(2015, 1, 1)
    assert rt == date(2024, 12, 31)

    # Week interval cap overflow
    start = date(1980, 1, 1)
    end = date(2024, 12, 31)
    weeks = count_iso_weeks(start, end)
    assert weeks > 2000
    with pytest.raises(HTTPException) as exc_info:
        resolve_price_range(start, end, interval="week")
    assert exc_info.value.status_code == 422
    assert "month" in exc_info.value.detail
    assert "week" not in exc_info.value.detail.split("exceeding the limit of 2000.")[1]
