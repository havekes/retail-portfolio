from decimal import Decimal
from typing import TypedDict

from src.market.schema import PriceSchema


class MovingAveragePoint(TypedDict):
    date: str
    value: float


class MACDPoint(TypedDict):
    date: str
    macd: float
    signal: float
    histogram: float


class RSIPoint(TypedDict):
    date: str
    rsi: float


def calculate_sma(prices: list[PriceSchema], period: int) -> list[MovingAveragePoint]:
    """
    Calculate Simple Moving Average.

    Args:
        prices: List of PriceSchema objects sorted by date (ascending)
        period: Number of periods for the moving average

    Returns:
        List of MovingAveragePoint with date and SMA value
    """
    if len(prices) < period:
        return []

    result = []
    for i in range(period - 1, len(prices)):
        window = prices[i - period + 1 : i + 1]
        total = sum(Decimal(str(p.close)) for p in window)
        avg = float(total / period)
        result.append({"date": prices[i].date.isoformat(), "value": avg})

    return result


def calculate_50_day_ma(prices: list[PriceSchema]) -> list[MovingAveragePoint]:
    """Calculate 50-day Simple Moving Average."""
    return calculate_sma(prices, 50)


def calculate_200_day_ma(prices: list[PriceSchema]) -> list[MovingAveragePoint]:
    """Calculate 200-day Simple Moving Average."""
    return calculate_sma(prices, 200)


def calculate_weekly_closes(prices: list[PriceSchema]) -> list[PriceSchema]:
    """
    Convert daily prices to weekly closes (Friday closes).

    Args:
        prices: List of PriceSchema objects sorted by date (ascending)

    Returns:
        List of PriceSchema objects with weekly close prices
    """
    if not prices:
        return []

    weekly_prices = []
    current_week = None
    current_close = None

    for price in prices:
        week = price.date.isocalendar()[1]
        year = price.date.year

        if current_week is None:
            current_week = (year, week)
            current_close = price
        elif (year, week) != current_week:
            weekly_prices.append(current_close)
            current_week = (year, week)
            current_close = price
        else:
            current_close = price

    if current_close:
        weekly_prices.append(current_close)

    return weekly_prices


def calculate_50_week_ma(prices: list[PriceSchema]) -> list[MovingAveragePoint]:
    """Calculate 50-week Simple Moving Average using weekly closes."""
    weekly_prices = calculate_weekly_closes(prices)
    return calculate_sma(weekly_prices, 50)


def calculate_200_week_ma(prices: list[PriceSchema]) -> list[MovingAveragePoint]:
    """Calculate 200-week Simple Moving Average using weekly closes."""
    weekly_prices = calculate_weekly_closes(prices)
    return calculate_sma(weekly_prices, 200)


def calculate_macd(
    prices: list[PriceSchema],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> list[MACDPoint]:
    """
    Calculate MACD (Moving Average Convergence Divergence).

    Args:
        prices: List of PriceSchema objects sorted by date (ascending)
        fast_period: Fast EMA period (default 12)
        slow_period: Slow EMA period (default 26)
        signal_period: Signal line EMA period (default 9)

    Returns:
        List of MACDPoint with date, macd, signal, and histogram values
    """
    if len(prices) < slow_period + signal_period:
        return []

    closes = [float(p.close) for p in prices]

    fast_ema = calculate_ema(closes, fast_period)
    slow_ema = calculate_ema(closes, slow_period)

    if len(fast_ema) < len(slow_ema):
        fast_ema = fast_ema[-len(slow_ema) :]

    macd_line = [f - s for f, s in zip(fast_ema, slow_ema, strict=True)]

    if len(macd_line) < signal_period:
        return []

    signal_line = calculate_ema(macd_line, signal_period)

    result = []
    start_idx = len(prices) - len(signal_line)
    for i, sig in enumerate(signal_line):
        macd_val = macd_line[i]
        histogram_val = macd_val - sig
        result.append(
            {
                "date": prices[start_idx + i].date.isoformat(),
                "macd": macd_val,
                "signal": sig,
                "histogram": histogram_val,
            }
        )

    return result


def calculate_ema(values: list[float], period: int) -> list[float]:
    """
    Calculate Exponential Moving Average.

    Args:
        values: List of numeric values
        period: EMA period

    Returns:
        List of EMA values (same length as input, with None for initial values)
    """
    if len(values) < period:
        return []

    multiplier = 2 / (period + 1)
    ema_values = []

    first_ema = sum(values[:period]) / period
    ema_values.append(first_ema)

    for i in range(period, len(values)):
        ema = (values[i] - ema_values[-1]) * multiplier + ema_values[-1]
        ema_values.append(ema)

    return ema_values


def calculate_rsi(prices: list[PriceSchema], period: int = 14) -> list[RSIPoint]:
    """
    Calculate Relative Strength Index (RSI).

    Args:
        prices: List of PriceSchema objects sorted by date (ascending)
        period: RSI period (default 14)

    Returns:
        List of RSIPoint with date and RSI value
    """
    if len(prices) < period + 1:
        return []

    closes = [float(p.close) for p in prices]
    gains = []
    losses = []

    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    if len(gains) < period:
        return []

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    result = []

    for i in range(period, len(gains)):
        if i > period:
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

        result.append({"date": prices[i + 1].date.isoformat(), "rsi": rsi})

    return result
