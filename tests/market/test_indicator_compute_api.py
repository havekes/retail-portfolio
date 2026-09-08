# ruff: noqa: PLR2004, ARG001
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.market.cache import IndicatorCache
from src.market.model import IntradayPriceModel, PriceModel
from src.market.service import IndicatorServiceClient


@pytest.mark.anyio
async def test_compute_unauthenticated(client):
    fake_id = uuid4()
    payload = {
        "interval": "1d",
        "chart_style": "candlestick",
        "indicators": [{"type": "SMA", "period": 20}],
    }
    response = await client.post(
        f"/api/v1/market/securities/{fake_id}/indicators/compute",
        json=payload,
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_compute_security_not_found(auth_client):
    fake_id = uuid4()
    payload = {
        "interval": "1d",
        "chart_style": "candlestick",
        "indicators": [{"type": "SMA", "period": 20}],
    }
    response = await auth_client.post(
        f"/api/v1/market/securities/{fake_id}/indicators/compute",
        json=payload,
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_compute_invalid_date_range(auth_client, test_security):
    payload = {
        "interval": "1d",
        "chart_style": "candlestick",
        "indicators": [{"type": "SMA", "period": 20}],
        "from_date": "2026-02-01",
        "to_date": "2026-01-01",
    }
    response = await auth_client.post(
        f"/api/v1/market/securities/{test_security.id}/indicators/compute",
        json=payload,
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_compute_with_custom_candles_and_heikin_ashi(auth_client, test_security):
    custom_candles = [
        {
            "time": "2026-01-01",
            "open": 10.0,
            "high": 15.0,
            "low": 8.0,
            "close": 12.0,
            "volume": 100.0,
        },
        {
            "time": "2026-01-02",
            "open": 12.0,
            "high": 16.0,
            "low": 11.0,
            "close": 14.0,
            "volume": 150.0,
        },
    ]
    payload = {
        "interval": "1d",
        "chart_style": "heikin_ashi",
        "indicators": [{"id": "SMA_20", "type": "SMA", "period": 20}],
        "candles": custom_candles,
    }

    mock_compute = AsyncMock(
        return_value={"SMA_20": [{"time": "2026-01-02", "value": 12.2}]}
    )

    with patch.object(IndicatorServiceClient, "compute", mock_compute):
        response = await auth_client.post(
            f"/api/v1/market/securities/{test_security.id}/indicators/compute",
            json=payload,
        )

        assert response.status_code == 200
        data = response.json()
        assert "indicators" in data
        assert "SMA_20" in data["indicators"]

        # Verify candles passed to sidecar were Heikin-Ashi converted
        mock_compute.assert_awaited_once()
        _, kwargs = mock_compute.call_args
        sidecar_candles = kwargs["candles"]
        assert len(sidecar_candles) == 2
        # First HA candle open = (10+12)/2 = 11.0
        assert sidecar_candles[0].open == 11.0


@pytest.mark.anyio
async def test_compute_with_daily_prices(auth_client, test_security, db_session):
    price = PriceModel(
        security_id=test_security.id,
        date=date(2026, 1, 15),
        open=Decimal("150.00"),
        high=Decimal("155.00"),
        low=Decimal("149.00"),
        close=Decimal("153.00"),
        adjusted_close=Decimal("153.00"),
        volume=1000000,
    )
    db_session.add(price)
    await db_session.commit()

    payload = {
        "interval": "1d",
        "chart_style": "candlestick",
        "indicators": [{"type": "SMA", "period": 50}],
    }

    mock_compute = AsyncMock(
        return_value={"SMA": [{"time": "2026-01-15", "value": 153.0}]}
    )

    with patch.object(IndicatorServiceClient, "compute", mock_compute):
        response = await auth_client.post(
            f"/api/v1/market/securities/{test_security.id}/indicators/compute",
            json=payload,
        )

        assert response.status_code == 200
        data = response.json()
        assert "indicators" in data
        assert "SMA" in data["indicators"]

        mock_compute.assert_awaited_once()
        _, kwargs = mock_compute.call_args
        assert kwargs["interval"] == "1d"
        assert kwargs["candles"][0].time == "2026-01-15"
        assert kwargs["candles"][0].close == 153.0


@pytest.mark.anyio
async def test_compute_with_weekly_and_monthly_prices(
    auth_client, test_security, db_session
):
    prices = [
        PriceModel(
            security_id=test_security.id,
            date=date(2026, 1, 5),
            open=Decimal("100.00"),
            high=Decimal("105.00"),
            low=Decimal("99.00"),
            close=Decimal("102.00"),
            adjusted_close=Decimal("102.00"),
            volume=500,
        ),
        PriceModel(
            security_id=test_security.id,
            date=date(2026, 1, 6),
            open=Decimal("102.00"),
            high=Decimal("108.00"),
            low=Decimal("101.00"),
            close=Decimal("107.00"),
            adjusted_close=Decimal("107.00"),
            volume=600,
        ),
    ]
    db_session.add_all(prices)
    await db_session.commit()

    mock_compute = AsyncMock(
        return_value={"SMA": [{"time": "2026-01-05", "value": 105.0}]}
    )

    with patch.object(IndicatorServiceClient, "compute", mock_compute):
        # 1w interval
        resp_w = await auth_client.post(
            f"/api/v1/market/securities/{test_security.id}/indicators/compute",
            json={
                "interval": "1w",
                "chart_style": "candlestick",
                "indicators": [{"type": "SMA", "period": 10}],
            },
        )
        assert resp_w.status_code == 200
        _, kwargs_w = mock_compute.call_args
        assert kwargs_w["interval"] == "1w"
        assert len(kwargs_w["candles"]) == 1

        # 1m interval
        resp_m = await auth_client.post(
            f"/api/v1/market/securities/{test_security.id}/indicators/compute",
            json={
                "interval": "1m",
                "chart_style": "candlestick",
                "indicators": [{"type": "SMA", "period": 10}],
            },
        )
        assert resp_m.status_code == 200
        _, kwargs_m = mock_compute.call_args
        assert kwargs_m["interval"] == "1m"
        assert len(kwargs_m["candles"]) == 1


@pytest.mark.anyio
async def test_compute_with_intraday_prices(auth_client, test_security, db_session):
    candles = [
        IntradayPriceModel(
            security_id=test_security.id,
            timestamp=datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
            open=Decimal("100.00"),
            high=Decimal("105.00"),
            low=Decimal("98.00"),
            close=Decimal("102.00"),
            volume=1000,
        ),
        IntradayPriceModel(
            security_id=test_security.id,
            timestamp=datetime(2026, 1, 15, 9, 0, tzinfo=UTC),
            open=Decimal("102.00"),
            high=Decimal("110.00"),
            low=Decimal("101.00"),
            close=Decimal("108.00"),
            volume=1500,
        ),
    ]
    db_session.add_all(candles)
    await db_session.commit()

    mock_compute = AsyncMock(
        return_value={"RSI": [{"time": 1768464000, "value": 55.0}]}
    )

    with patch.object(IndicatorServiceClient, "compute", mock_compute):
        # 1h interval
        resp_1h = await auth_client.post(
            f"/api/v1/market/securities/{test_security.id}/indicators/compute",
            json={
                "interval": "1h",
                "chart_style": "candlestick",
                "indicators": [{"type": "RSI", "period": 14}],
            },
        )
        assert resp_1h.status_code == 200
        _, kwargs_1h = mock_compute.call_args
        assert kwargs_1h["interval"] == "1h"
        assert isinstance(kwargs_1h["candles"][0].time, int)

        # 4h interval
        resp_4h = await auth_client.post(
            f"/api/v1/market/securities/{test_security.id}/indicators/compute",
            json={
                "interval": "4h",
                "chart_style": "candlestick",
                "indicators": [{"type": "RSI", "period": 14}],
            },
        )
        assert resp_4h.status_code == 200
        _, kwargs_4h = mock_compute.call_args
        assert kwargs_4h["interval"] == "4h"
        assert len(kwargs_4h["candles"]) == 1


@pytest.mark.anyio
async def test_compute_cache_hit_and_miss(auth_client, test_security, db_session):
    price = PriceModel(
        security_id=test_security.id,
        date=date(2026, 1, 15),
        open=Decimal("150.00"),
        high=Decimal("155.00"),
        low=Decimal("149.00"),
        close=Decimal("153.00"),
        adjusted_close=Decimal("153.00"),
        volume=1000000,
    )
    db_session.add(price)
    await db_session.commit()

    payload = {
        "interval": "1d",
        "chart_style": "candlestick",
        "indicators": [{"id": "SMA_20", "type": "SMA", "period": 20}],
    }

    cached_store = {}

    async def mock_get(*args, **kwargs):
        return cached_store.get("cached_key")

    async def mock_set(*args, **kwargs):
        cached_store["cached_key"] = kwargs.get("data")

    mock_compute = AsyncMock(
        return_value={"SMA_20": [{"time": "2026-01-15", "value": 153.0}]}
    )

    with (
        patch.object(IndicatorCache, "get", side_effect=mock_get),
        patch.object(IndicatorCache, "set", side_effect=mock_set),
        patch.object(IndicatorServiceClient, "compute", mock_compute),
    ):
        # 1st call: Cache miss -> calls sidecar -> caches
        resp1 = await auth_client.post(
            f"/api/v1/market/securities/{test_security.id}/indicators/compute",
            json=payload,
        )
        assert resp1.status_code == 200
        assert mock_compute.await_count == 1
        assert "cached_key" in cached_store

        # 2nd call: Cache hit -> returns cached without calling sidecar
        resp2 = await auth_client.post(
            f"/api/v1/market/securities/{test_security.id}/indicators/compute",
            json=payload,
        )
        assert resp2.status_code == 200
        assert resp2.json() == resp1.json()
        assert mock_compute.await_count == 1


@pytest.mark.anyio
async def test_compute_sidecar_failure_propagation(
    auth_client, test_security, db_session
):
    price = PriceModel(
        security_id=test_security.id,
        date=date(2026, 1, 15),
        open=Decimal("150.00"),
        high=Decimal("155.00"),
        low=Decimal("149.00"),
        close=Decimal("153.00"),
        adjusted_close=Decimal("153.00"),
        volume=1000000,
    )
    db_session.add(price)
    await db_session.commit()

    payload = {
        "interval": "1d",
        "chart_style": "candlestick",
        "indicators": [{"type": "SMA", "period": 20}],
    }

    # 503 Unavailable
    with patch.object(
        IndicatorServiceClient,
        "compute",
        AsyncMock(
            side_effect=HTTPException(
                status_code=503, detail="Indicator service unavailable"
            )
        ),
    ):
        resp_503 = await auth_client.post(
            f"/api/v1/market/securities/{test_security.id}/indicators/compute",
            json=payload,
        )
        assert resp_503.status_code == 503

    # 504 Timeout
    with patch.object(
        IndicatorServiceClient,
        "compute",
        AsyncMock(
            side_effect=HTTPException(
                status_code=504, detail="Indicator service timed out"
            )
        ),
    ):
        resp_504 = await auth_client.post(
            f"/api/v1/market/securities/{test_security.id}/indicators/compute",
            json=payload,
        )
        assert resp_504.status_code == 504
