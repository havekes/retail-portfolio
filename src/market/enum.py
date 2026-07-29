from enum import StrEnum


class PriceInterval(StrEnum):
    """Supported candle length intervals for market prices."""

    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1m"
