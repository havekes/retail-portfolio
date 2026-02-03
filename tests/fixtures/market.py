"""Market data and EODHD API mocking fixtures."""

from datetime import date
from decimal import Decimal

import pytest

from src.market.api_types import EodhdSearchResult, HistoricalPrice
from src.market.schema import SecuritySchema