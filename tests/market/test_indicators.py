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


def test_calculate_50_day_ma_insufficient_data():
    prices = make_price_history([100.0] * 49)
    assert calculate_50_day_ma(prices) == []


def test_calculate_50_day_ma_sufficient_data():
    prices = make_price_history([100.0] * 52)
    result = calculate_50_day_ma(prices)
    assert len(result) == 3
    assert result[0]["value"] == pytest.approx(100.0)


def test_calculate_200_day_ma_insufficient_data():
    prices = make_price_history([100.0] * 199)
    assert calculate_200_day_ma(prices) == []


def test_calculate_200_day_ma_sufficient_data():
    prices = make_price_history([100.0] * 202)
    result = calculate_200_day_ma(prices)
    assert len(result) == 3
    assert result[0]["value"] == pytest.approx(100.0)


def test_calculate_50_week_ma_insufficient_data():
    prices = make_price_history([100.0] * 200, step_days=1)
    assert calculate_50_week_ma(prices) == []


def test_calculate_50_week_ma_sufficient_data():
    prices = make_price_history([100.0] * 52, step_days=7)
    result = calculate_50_week_ma(prices)
    assert len(result) == 3
    assert result[0]["value"] == pytest.approx(100.0)


def test_calculate_200_week_ma_insufficient_data():
    prices = make_price_history([100.0] * 100, step_days=7)
    assert calculate_200_week_ma(prices) == []


def test_calculate_200_week_ma_sufficient_data():
    prices = make_price_history([100.0] * 202, step_days=7)
    result = calculate_200_week_ma(prices)
    assert len(result) == 3
    assert result[0]["value"] == pytest.approx(100.0)


# ============================================================================
# 4. Tests for calculate_weekly_closes
# ============================================================================


def test_calculate_weekly_closes_empty():
    assert calculate_weekly_closes([]) == []


def test_calculate_weekly_closes_grouping():
    sec_id = uuid4()
    dates = [
        date(2025, 1, 1),
        date(2025, 1, 2),
        date(2025, 1, 3),
        date(2025, 1, 6),
        date(2025, 1, 7),
    ]
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
        for d, p in zip(dates, [10.0, 11.0, 12.0, 20.0, 21.0], strict=True)
    ]

    weekly = calculate_weekly_closes(prices)
    assert len(weekly) == 2
    assert weekly[0].date == date(2025, 1, 3)
    assert float(weekly[0].close) == pytest.approx(12.0)
    assert weekly[1].date == date(2025, 1, 7)
    assert float(weekly[1].close) == pytest.approx(21.0)


def test_calculate_weekly_closes_year_boundary():
    d1 = date(2024, 12, 29)
    d2 = date(2024, 12, 30)
    sec_id = uuid4()
    p1 = PriceSchema(
        security_id=sec_id, date=d1, open=Decimal("10"), high=Decimal("10"),
        low=Decimal("10"), close=Decimal("10"), adjusted_close=Decimal("10"), volume=100
    )
    p2 = PriceSchema(
        security_id=sec_id, date=d2, open=Decimal("20"), high=Decimal("20"),
        low=Decimal("20"), close=Decimal("20"), adjusted_close=Decimal("20"), volume=100
    )
    weekly = calculate_weekly_closes([p1, p2])
    assert len(weekly) == 2
    assert weekly[0].date == d1
    assert weekly[1].date == d2


# ============================================================================
# 5. Tests for calculate_macd
# ============================================================================


def test_calculate_macd_prices_less_than_max_period():
    prices = make_price_history([10.0] * 5)
    # 5 prices < max(12, 26) -> []
    assert calculate_macd(prices) == []


def test_calculate_macd_insufficient_data_for_signal():
    prices = make_price_history([10.0] * 33)
    # Default slow=26, signal=9 -> 33 prices gives 8 MACD points < 9 signal_period -> []
    assert calculate_macd(prices) == []


def test_calculate_macd_sufficient_data():
    prices = make_price_history([100.0] * 40)
    result = calculate_macd(prices)
    assert len(result) == 7
    for point in result:
        assert point["macd"] == pytest.approx(0.0)
        assert point["signal"] == pytest.approx(0.0)
        assert point["histogram"] == pytest.approx(0.0)
        assert point["histogram"] == pytest.approx(point["macd"] - point["signal"])


def test_calculate_macd_varying_prices():
    prices_val = [float(i) for i in range(1, 45)]
    prices = make_price_history(prices_val)
    result = calculate_macd(prices)
    assert len(result) > 0
    for point in result:
        assert point["histogram"] == pytest.approx(point["macd"] - point["signal"])


def test_calculate_macd_equal_fast_and_slow_periods():
    # Covers equal period fast_ema and slow_ema alignment (neither > nor <)
    prices = make_price_history([10.0] * 20)
    result = calculate_macd(prices, fast_period=5, slow_period=5, signal_period=5)
    assert len(result) == 12
    for point in result:
        assert point["macd"] == pytest.approx(0.0)


def test_calculate_macd_slow_period_larger_than_fast_slicing():
    # fast=20, slow=10, signal=5, len(prices)=20 -> slow_ema length 11 > fast_ema length 1 -> slow_ema sliced
    prices = make_price_history([10.0] * 20)
    result = calculate_macd(prices, fast_period=20, slow_period=10, signal_period=5)
    assert result == []


def test_calculate_macd_line_shorter_than_signal_period():
    prices = make_price_history([10.0] * 15)
    result = calculate_macd(prices, fast_period=5, slow_period=10, signal_period=10)
    assert result == []


# ============================================================================
# 6. Tests for calculate_rsi
# ============================================================================


def test_calculate_rsi_fewer_than_two_prices():
    prices = make_price_history([10.0])
    assert calculate_rsi(prices, period=14) == []


def test_calculate_rsi_insufficient_data():
    prices = make_price_history([10.0] * 14)
    assert calculate_rsi(prices, period=14) == []


def test_calculate_rsi_strictly_increasing():
    prices_val = [float(10 + i) for i in range(20)]
    prices = make_price_history(prices_val)
    result = calculate_rsi(prices, period=14)
    assert len(result) == 5
    for point in result:
        assert point["rsi"] == pytest.approx(100.0)


def test_calculate_rsi_varying_prices():
    prices_val = [10.0, 12.0, 11.0, 13.0, 12.0, 14.0, 13.0, 15.0, 14.0, 16.0,
                  15.0, 17.0, 16.0, 18.0, 17.0, 19.0, 18.0, 20.0, 19.0, 21.0]
    prices = make_price_history(prices_val)
    result = calculate_rsi(prices, period=14)
    assert len(result) == 5
    for point in result:
        assert 0.0 <= point["rsi"] <= 100.0
