"""Unit tests for core financial indicators in src/market/indicators.py."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.market.indicators import (
    calculate_200_day_ma,
    calculate_200_week_ma,
    calculate_50_day_ma,
    calculate_50_week_ma,
    calculate_ema,
    calculate_macd,
    calculate_rsi,
    calculate_sma,
    calculate_weekly_closes,
)
from src.market.schema import PriceSchema


def make_price_history(
    close_prices: list[float],
    start_date: date = date(2025, 1, 1),
    step_days: int = 1,
) -> list[PriceSchema]:
    sec_id = uuid4()
    prices = []
    for i, p in enumerate(close_prices):
        d = start_date + timedelta(days=i * step_days)
        prices.append(
            PriceSchema(
                security_id=sec_id,
                date=d,
                open=Decimal(str(p)),
                high=Decimal(str(p)),
                low=Decimal(str(p)),
                close=Decimal(str(p)),
                adjusted_close=Decimal(str(p)),
                volume=1000,
            )
        )
    return prices


# ============================================================================
# 1. Tests for calculate_ema
# ============================================================================


@pytest.mark.parametrize(
    "values, period, expected",
    [
        ([], 3, []),
        ([10.0, 11.0], 3, []),
        ([10.0, 12.0, 14.0], 3, [12.0]),
        ([10.0, 11.0, 12.0, 13.0, 14.0], 3, [11.0, 12.0, 13.0]),
    ],
)
def test_calculate_ema(values: list[float], period: int, expected: list[float]):
    result = calculate_ema(values, period)
    assert len(result) == len(expected)
    for res, exp in zip(result, expected, strict=True):
        assert res == pytest.approx(exp)


# ============================================================================
# 2. Tests for calculate_sma
# ============================================================================


@pytest.mark.parametrize(
    "close_prices, period, expected_values",
    [
        ([10.0, 20.0], 3, []),
        ([10.0, 20.0, 30.0], 3, [20.0]),
        ([10.0, 20.0, 30.0, 40.0, 50.0], 3, [20.0, 30.0, 40.0]),
    ],
)
def test_calculate_sma(
    close_prices: list[float], period: int, expected_values: list[float]
):
    prices = make_price_history(close_prices)
    result = calculate_sma(prices, period)

    assert len(result) == len(expected_values)
    for i, point in enumerate(result):
        expected_date = prices[period - 1 + i].date.isoformat()
        assert point["date"] == expected_date
        assert point["value"] == pytest.approx(expected_values[i])


# ============================================================================
# 3. Tests for wrapper MA functions (50-day, 200-day, 50-week, 200-week)
# ============================================================================


@pytest.mark.parametrize(
    "func, count, step_days, expected_len",
    [
        (calculate_50_day_ma, 49, 1, 0),
        (calculate_50_day_ma, 52, 1, 3),
        (calculate_200_day_ma, 199, 1, 0),
        (calculate_200_day_ma, 202, 1, 3),
        (calculate_50_week_ma, 200, 1, 0),
        (calculate_50_week_ma, 52, 7, 3),
        (calculate_200_week_ma, 100, 7, 0),
        (calculate_200_week_ma, 202, 7, 3),
    ],
)
def test_moving_average_wrappers(func, count: int, step_days: int, expected_len: int):
    prices = make_price_history([100.0] * count, step_days=step_days)
    result = func(prices)
    assert len(result) == expected_len
    if expected_len > 0:
        assert result[0]["value"] == pytest.approx(100.0)


# ============================================================================
# 4. Tests for calculate_weekly_closes
# ============================================================================


@pytest.mark.parametrize(
    "dates, closes, expected_dates, expected_closes",
    [
        # Empty input
        ([], [], [], []),
        # Weekly grouping across multiple days/weeks
        (
            [
                date(2025, 1, 1),
                date(2025, 1, 2),
                date(2025, 1, 3),
                date(2025, 1, 6),
                date(2025, 1, 7),
            ],
            [10.0, 11.0, 12.0, 20.0, 21.0],
            [date(2025, 1, 3), date(2025, 1, 7)],
            [12.0, 21.0],
        ),
        # Year boundary week transition
        (
            [date(2024, 12, 29), date(2024, 12, 30)],
            [10.0, 20.0],
            [date(2024, 12, 29), date(2024, 12, 30)],
            [10.0, 20.0],
        ),
    ],
)
def test_calculate_weekly_closes(
    dates: list[date],
    closes: list[float],
    expected_dates: list[date],
    expected_closes: list[float],
):
    sec_id = uuid4()
    prices = [
        PriceSchema(
            security_id=sec_id,
            date=d,
            open=Decimal(str(p)),
            high=Decimal(str(p)),
            low=Decimal(str(p)),
            close=Decimal(str(p)),
            adjusted_close=Decimal(str(p)),
            volume=1000,
        )
        for d, p in zip(dates, closes, strict=True)
    ]
    weekly = calculate_weekly_closes(prices)
    assert len(weekly) == len(expected_dates)
    for w, exp_d, exp_c in zip(weekly, expected_dates, expected_closes, strict=True):
        assert w.date == exp_d
        assert float(w.close) == pytest.approx(exp_c)


# ============================================================================
# 5. Tests for calculate_macd
# ============================================================================


@pytest.mark.parametrize(
    "close_prices, kwargs, expected_len, check_histogram_diff, expected_macd_zero",
    [
        # Insufficient data for max(fast, slow)
        ([10.0] * 5, {}, 0, False, False),
        # Insufficient data for signal line (slow=26, signal=9 -> 33 prices gives 8 macd points < 9 signal_period)
        ([10.0] * 33, {}, 0, False, False),
        # Sufficient data with constant prices
        ([100.0] * 40, {}, 7, True, True),
        # Varying prices
        ([float(i) for i in range(1, 45)], {}, 11, True, False),
        # Equal fast and slow periods
        (
            [10.0] * 20,
            {"fast_period": 5, "slow_period": 5, "signal_period": 5},
            12,
            True,
            True,
        ),
        # Fast period larger than slow period causing slow_ema slicing
        (
            [10.0] * 20,
            {"fast_period": 20, "slow_period": 10, "signal_period": 5},
            0,
            False,
            False,
        ),
        # MACD line shorter than signal period
        (
            [10.0] * 15,
            {"fast_period": 5, "slow_period": 10, "signal_period": 10},
            0,
            False,
            False,
        ),
    ],
)
def test_calculate_macd(
    close_prices: list[float],
    kwargs: dict,
    expected_len: int,
    check_histogram_diff: bool,
    expected_macd_zero: bool,
):
    prices = make_price_history(close_prices)
    result = calculate_macd(prices, **kwargs)
    assert len(result) == expected_len
    if check_histogram_diff:
        for point in result:
            assert point["histogram"] == pytest.approx(
                point["macd"] - point["signal"]
            )
            if expected_macd_zero:
                assert point["macd"] == pytest.approx(0.0)
                assert point["signal"] == pytest.approx(0.0)


# ============================================================================
# 6. Tests for calculate_rsi
# ============================================================================


@pytest.mark.parametrize(
    "close_prices, period, expected_len, expected_rsi_val, check_bounds",
    [
        # Fewer than two prices
        ([10.0], 14, 0, None, False),
        # Insufficient data for RSI period
        ([10.0] * 14, 14, 0, None, False),
        # Strictly increasing prices (avg_loss == 0 edge case -> RSI 100)
        ([float(10 + i) for i in range(20)], 14, 5, 100.0, False),
        # Varying prices
        (
            [
                10.0,
                12.0,
                11.0,
                13.0,
                12.0,
                14.0,
                13.0,
                15.0,
                14.0,
                16.0,
                15.0,
                17.0,
                16.0,
                18.0,
                17.0,
                19.0,
                18.0,
                20.0,
                19.0,
                21.0,
            ],
            14,
            5,
            None,
            True,
        ),
    ],
)
def test_calculate_rsi(
    close_prices: list[float],
    period: int,
    expected_len: int,
    expected_rsi_val: float | None,
    check_bounds: bool,
):
    prices = make_price_history(close_prices)
    result = calculate_rsi(prices, period=period)
    assert len(result) == expected_len
    for point in result:
        if expected_rsi_val is not None:
            assert point["rsi"] == pytest.approx(expected_rsi_val)
        if check_bounds:
            assert 0.0 <= point["rsi"] <= 100.0
