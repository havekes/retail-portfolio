# ruff: noqa: PLR2004, SLF001
"""Tests for EODHD gateway and stub intraday price data fetching."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pandas as pd
import pytest

from src.market.api_types import IntradayHistoricalPrice
from src.market.eodhd import EodhdGateway
from src.stubs.eodhd import StubEodhdAPIClient, StubEodhdGateway


def test_stub_eodhd_api_client_intraday_data_generation():
    client = StubEodhdAPIClient(api_key="stub_key")
    start_dt = datetime(2026, 7, 28, 9, 0, tzinfo=UTC)
    end_dt = datetime(2026, 7, 28, 16, 0, tzinfo=UTC)

    from_unix = int(start_dt.timestamp())
    to_unix = int(end_dt.timestamp())

    data = client.get_intraday_historical_data(
        symbol="AAPL.US",
        interval="1h",
        from_unix_time=from_unix,
        to_unix_time=to_unix,
    )

    assert isinstance(data, list)
    assert len(data) == 8  # 9:00 to 16:00 inclusive (8 hours)

    first_candle = data[0]
    assert "timestamp" in first_candle
    assert "datetime" in first_candle
    assert "open" in first_candle
    assert "high" in first_candle
    assert "low" in first_candle
    assert "close" in first_candle
    assert "volume" in first_candle
    assert first_candle["timestamp"] == from_unix


def test_stub_eodhd_gateway_get_intraday_prices():
    gateway = StubEodhdGateway(api_key="stub_key")
    sec_id = uuid4()
    start_dt = datetime(2026, 7, 28, 10, 0, tzinfo=UTC)
    end_dt = datetime(2026, 7, 28, 14, 0, tzinfo=UTC)

    prices = gateway.get_intraday_prices(
        security_id=sec_id,
        symbol="AAPL",
        exchange="US",
        from_datetime=start_dt,
        to_datetime=end_dt,
        interval="1h",
    )

    assert len(prices) == 5
    for price in prices:
        assert isinstance(price, IntradayHistoricalPrice)
        assert price.security_id == sec_id
        assert price.timestamp.tzinfo is not None
        assert isinstance(price.open, Decimal)
        assert isinstance(price.high, Decimal)
        assert isinstance(price.low, Decimal)
        assert isinstance(price.close, Decimal)
        assert isinstance(price.volume, int)


@patch("src.market.eodhd.APIClient")
def test_get_intraday_prices_filters_flat_candles(mock_api_client_cls):
    gateway = EodhdGateway(api_key="test_key")
    gateway._client = mock_api_client_cls.return_value

    ts1 = int(datetime(2026, 7, 28, 14, 0, tzinfo=UTC).timestamp())
    ts2 = int(datetime(2026, 7, 28, 15, 0, tzinfo=UTC).timestamp())
    ts3 = int(datetime(2026, 7, 28, 16, 0, tzinfo=UTC).timestamp())

    mock_data_list = [
        {
            "timestamp": ts1,
            "datetime": "2026-07-28 14:00:00",
            "open": 100.0,
            "high": 105.0,
            "low": 99.0,
            "close": 102.0,
            "volume": 1000,
        },
        {
            "timestamp": ts2,
            "datetime": "2026-07-28 15:00:00",
            "open": 102.0,
            "high": 102.0,
            "low": 102.0,
            "close": 102.0,
            "volume": 50,
        },
        {
            "timestamp": ts3,
            "datetime": "2026-07-28 16:00:00",
            "open": 102.0,
            "high": 102.0,
            "low": 102.0,
            "close": 102.0,
            "volume": 0,
        },
    ]
    gateway._client.get_intraday_historical_data.return_value = mock_data_list

    sec_id = uuid4()
    prices = gateway.get_intraday_prices(
        security_id=sec_id,
        symbol="AAPL",
        exchange="US",
        from_datetime=datetime(2026, 7, 28, 14, 0, tzinfo=UTC),
        to_datetime=datetime(2026, 7, 28, 16, 0, tzinfo=UTC),
    )

    assert len(prices) == 2
    assert prices[0].open == Decimal("100.0")
    assert prices[0].volume == 1000
    assert prices[1].open == Decimal("102.0")
    assert prices[1].volume == 50

    # Also test pandas DataFrame response branch
    df_data = pd.DataFrame(mock_data_list)
    gateway._client.get_intraday_historical_data.return_value = df_data

    prices_df = gateway.get_intraday_prices(
        security_id=sec_id,
        symbol="AAPL",
        exchange="US",
        from_datetime=datetime(2026, 7, 28, 14, 0, tzinfo=UTC),
        to_datetime=datetime(2026, 7, 28, 16, 0, tzinfo=UTC),
    )

    assert len(prices_df) == 2
    assert prices_df[0].open == Decimal("100.0")
    assert prices_df[1].open == Decimal("102.0")


def test_stub_eodhd_gateway_filters_end_of_day_flat_candle():
    gateway = StubEodhdGateway(api_key="stub_key")
    sec_id = uuid4()
    start_dt = datetime(2026, 7, 28, 9, 0, tzinfo=UTC)
    end_dt = datetime(2026, 7, 28, 16, 0, tzinfo=UTC)

    prices = gateway.get_intraday_prices(
        security_id=sec_id,
        symbol="AAPL",
        exchange="US",
        from_datetime=start_dt,
        to_datetime=end_dt,
        interval="1h",
    )

    assert len(prices) == 7
    assert all(p.timestamp.hour != 16 for p in prices)



def test_stub_eodhd_gateway_invalid_interval():
    gateway = StubEodhdGateway(api_key="stub_key")
    sec_id = uuid4()
    start_dt = datetime(2026, 7, 28, 10, 0, tzinfo=UTC)
    end_dt = datetime(2026, 7, 28, 14, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="Unsupported interval"):
        gateway.get_intraday_prices(
            security_id=sec_id,
            symbol="AAPL",
            exchange="US",
            from_datetime=start_dt,
            to_datetime=end_dt,
            interval="5m",
        )


@patch("src.market.eodhd.APIClient")
def test_eodhd_gateway_get_intraday_prices_list_response(mock_api_client_cls):
    gateway = EodhdGateway(api_key="test_key")
    gateway._client = mock_api_client_cls.return_value

    mock_ts = 1775050200
    gateway._client.get_intraday_historical_data.return_value = [
        {
            "timestamp": mock_ts,
            "gmtoffset": 0,
            "datetime": "2026-04-01 13:30:00",
            "open": 150.25,
            "high": 152.0,
            "low": 149.5,
            "close": 151.10,
            "volume": 5000,
        }
    ]

    sec_id = uuid4()
    from_dt = datetime(2026, 4, 1, 13, 30, tzinfo=UTC)
    to_dt = datetime(2026, 4, 1, 14, 30, tzinfo=UTC)

    prices = gateway.get_intraday_prices(
        security_id=sec_id,
        symbol="AAPL",
        exchange="US",
        from_datetime=from_dt,
        to_datetime=to_dt,
        interval="1h",
    )

    gateway._client.get_intraday_historical_data.assert_called_once_with(
        symbol="AAPL.US",
        interval="1h",
        from_unix_time=int(from_dt.timestamp()),
        to_unix_time=int(to_dt.timestamp()),
    )

    assert len(prices) == 1
    price = prices[0]
    assert price.security_id == sec_id
    assert price.timestamp == datetime.fromtimestamp(mock_ts, tz=UTC)
    assert price.open == Decimal("150.25")
    assert price.high == Decimal("152.0")
    assert price.low == Decimal("149.5")
    assert price.close == Decimal("151.1")
    assert price.volume == 5000


@patch("src.market.eodhd.APIClient")
def test_eodhd_gateway_get_intraday_prices_dataframe_response(mock_api_client_cls):
    gateway = EodhdGateway(api_key="test_key")
    gateway._client = mock_api_client_cls.return_value

    mock_ts = 1775050200
    df = pd.DataFrame(
        [
            {
                "timestamp": mock_ts,
                "datetime": "2026-04-01 13:30:00",
                "open": 200.5,
                "high": 205.0,
                "low": 199.0,
                "close": 202.25,
                "volume": 12000,
            }
        ]
    )
    gateway._client.get_intraday_historical_data.return_value = df

    sec_id = uuid4()
    from_dt = datetime(2026, 4, 1, 13, 30, tzinfo=UTC)
    to_dt = datetime(2026, 4, 1, 14, 30, tzinfo=UTC)

    prices = gateway.get_intraday_prices(
        security_id=sec_id,
        symbol="MSFT",
        exchange="US",
        from_datetime=from_dt,
        to_datetime=to_dt,
        interval="1h",
    )

    assert len(prices) == 1
    price = prices[0]
    assert price.security_id == sec_id
    assert price.timestamp == datetime.fromtimestamp(mock_ts, tz=UTC)
    assert price.open == Decimal("200.5")
    assert price.close == Decimal("202.25")
    assert price.volume == 12000


@patch("src.market.eodhd.APIClient")
def test_eodhd_gateway_invalid_interval(mock_api_client_cls):
    gateway = EodhdGateway(api_key="test_key")
    sec_id = uuid4()
    from_dt = datetime.now(tz=UTC)
    to_dt = datetime.now(tz=UTC)

    with pytest.raises(ValueError, match="Unsupported interval"):
        gateway.get_intraday_prices(
            security_id=sec_id,
            symbol="AAPL",
            exchange="US",
            from_datetime=from_dt,
            to_datetime=to_dt,
            interval="1m",
        )
