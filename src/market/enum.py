from enum import StrEnum


class PriceInterval(StrEnum):
    """Supported candle length intervals for market prices."""

    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1m"


class WatchlistSortMode(StrEnum):
    """Sort modes a watchlist's securities can be displayed in.

    ``DATE_ADDED`` is newest first, ``DATE_ADDED_ASC`` oldest first.
    """

    CUSTOM = "custom"
    NAME_ASC = "name_asc"
    PRICE_CHANGE_DESC = "price_change_desc"
    PRICE_CHANGE_ASC = "price_change_asc"
    DATE_ADDED = "date_added"
    DATE_ADDED_ASC = "date_added_asc"
