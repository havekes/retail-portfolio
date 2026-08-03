from src.market.schema import PriceSchema
from datetime import date, datetime, timezone
from decimal import Decimal
from src.market.model import IntradayPriceModel, PriceModel
"""Integration tests for market router."""

import pytest

@pytest.mark.anyio
async def test_watchlists_list_empty(auth_client):
    """Test get_watchlists returns empty list when user has no watchlists."""
    response = await auth_client.get("/api/v1/market/watchlists")

    assert response.status_code == 200
    result = response.json()

    assert result == []

@pytest.mark.anyio
async def test_watchlists_list_success(auth_client, test_watchlists):
    """Test get_watchlists returns user's watchlists."""
    response = await auth_client.get("/api/v1/market/watchlists")

    assert response.status_code == 200
    result = response.json()

    assert len(result) == 2
    assert result[0]["name"] == "Test Watchlist 0"
    assert result[1]["name"] == "Test Watchlist 1"
    
    # Test new securities endpoint
    watchlist_id = result[0]["id"]
    response = await auth_client.get(f"/api/v1/market/watchlists/{watchlist_id}/securities")
    assert response.status_code == 200
    securities_result = response.json()
    assert "items" in securities_result
    assert "total" in securities_result
    assert len(securities_result["items"]) >= 0

@pytest.mark.anyio
async def test_watchlists_list_not_owned(auth_client, other_user, db_session):
    """Test get_watchlists does not return other user's watchlists."""
    from uuid import uuid4
    from src.market.model import WatchlistModel
    
    # Create a watchlist for another user
    watchlist_model = WatchlistModel(
        id=uuid4(),
        user_id=other_user.id,
        name="Other User Watchlist",
    )
    db_session.add(watchlist_model)
    await db_session.commit()
    
    response = await auth_client.get("/api/v1/market/watchlists")

    assert response.status_code == 200
    result = response.json()

    # Should still be empty for the authenticated user
    assert result == []


@pytest.mark.anyio
async def test_watchlist_add_security(auth_client, test_security):
    """Test POST /watchlists/securities/{security_id} adds a security to the watchlist."""
    response = await auth_client.post(f"/api/v1/market/watchlists/securities/{test_security.id}")
    
    assert response.status_code == 200
    result = response.json()
    assert result["name"] == "Default"
    
    # Check securities using the new endpoint
    watchlist_id = result["id"]
    securities_response = await auth_client.get(f"/api/v1/market/watchlists/{watchlist_id}/securities")
    securities_result = securities_response.json()
    assert len(securities_result["items"]) == 1
    assert securities_result["items"][0]["id"] == str(test_security.id)
    assert securities_result["items"][0]["symbol"] == test_security.symbol


@pytest.mark.anyio
async def test_watchlist_remove_security(auth_client, test_security):
    """Test DELETE /watchlists/securities/{security_id} removes a security from the watchlist."""
    # First add it
    await auth_client.post(f"/api/v1/market/watchlists/securities/{test_security.id}")
    
    # Now remove it
    response = await auth_client.delete(f"/api/v1/market/watchlists/securities/{test_security.id}")
    
    assert response.status_code == 200
    result = response.json()
    assert result["name"] == "Default"
    
    # Check securities using the new endpoint
    watchlist_id = result["id"]
    securities_response = await auth_client.get(f"/api/v1/market/watchlists/{watchlist_id}/securities")
    securities_result = securities_response.json()
    assert len(securities_result["items"]) == 0


@pytest.mark.anyio
async def test_watchlist_add_security_not_found(auth_client):
    """Test POST /watchlists/securities/{security_id} returns 404 if security not found."""
    from uuid import uuid4
    fake_id = uuid4()
    response = await auth_client.post(f"/api/v1/market/watchlists/securities/{fake_id}")
    
    assert response.status_code == 404
    assert "not found" in response.json()["error"].lower()



@pytest.mark.anyio
async def test_get_prices_1d_default(auth_client, test_security, db_session):
    """Test GET /market/prices/{security_id} with default interval=1d."""
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

    response = await auth_client.get(
        f"/api/v1/market/prices/{test_security.id}?from_date=2026-01-01&to_date=2026-01-31"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["security_id"] == str(test_security.id)
    assert result["total"] > 0
    assert len(result["items"]) > 0


@pytest.mark.anyio
async def test_get_prices_1h_intraday(auth_client, test_security, db_session):
    """Test GET /market/prices/{security_id} with interval=1h."""
    candle = IntradayPriceModel(
        security_id=test_security.id,
        timestamp=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
        open=Decimal("150.00"),
        high=Decimal("152.00"),
        low=Decimal("149.50"),
        close=Decimal("151.00"),
        volume=10000,
    )
    db_session.add(candle)
    await db_session.commit()

    response = await auth_client.get(
        f"/api/v1/market/prices/{test_security.id}?interval=1h&from_date=2026-01-15T00:00:00Z&to_date=2026-01-15T23:59:59Z"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["security_id"] == str(test_security.id)
    assert result["total"] == 1
    assert len(result["items"]) == 1
    assert Decimal(result["items"][0]["close"]) == Decimal("151.00")


@pytest.mark.anyio
async def test_get_prices_4h_intraday_aggregation(auth_client, test_security, db_session):
    """Test GET /market/prices/{security_id} with interval=4haggregates 1h candles."""
    candles = [
        IntradayPriceModel(
            security_id=test_security.id,
            timestamp=datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc),
            open=Decimal("100.00"),
            high=Decimal("105.00"),
            low=Decimal("98.00"),
            close=Decimal("102.00"),
            volume=1000,
        ),
        IntradayPriceModel(
            security_id=test_security.id,
            timestamp=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
            open=Decimal("102.00"),
            high=Decimal("110.00"),
            low=Decimal("101.00"),
            close=Decimal("108.00"),
            volume=1500,
        ),
        IntradayPriceModel(
            security_id=test_security.id,
            timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
            open=Decimal("108.00"),
            high=Decimal("109.00"),
            low=Decimal("104.00"),
            close=Decimal("105.00"),
            volume=1200,
        ),
        IntradayPriceModel(
            security_id=test_security.id,
            timestamp=datetime(2026, 1, 15, 11, 0, tzinfo=timezone.utc),
            open=Decimal("105.00"),
            high=Decimal("107.00"),
            low=Decimal("95.00"),
            close=Decimal("99.00"),
            volume=2000,
        ),
    ]
    for c in candles:
        db_session.add(c)
    await db_session.commit()

    response = await auth_client.get(
        f"/api/v1/market/prices/{test_security.id}?interval=4h"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["security_id"] == str(test_security.id)
    assert result["total"] == 1
    assert len(result["items"]) == 1

    agg = result["items"][0]
    assert Decimal(agg["open"]) == Decimal("100.00")
    assert Decimal(agg["high"]) == Decimal("110.00")
    assert Decimal(agg["low"]) == Decimal("95.00")
    assert Decimal(agg["close"]) == Decimal("99.00")
    assert agg["volume"] == 5700


@pytest.mark.anyio
async def test_get_prices_1h_intraday_no_date_range(auth_client, test_security, db_session):
    """Test 1h intraday endpoint with no from_date/to_date (the actual repro from #140).

    When the table is populated, a request without date bounds should return data
    instead of an empty list.
    """
    candle = IntradayPriceModel(
        security_id=test_security.id,
        timestamp=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
        open=Decimal("150.00"),
        high=Decimal("152.00"),
        low=Decimal("149.50"),
        close=Decimal("151.00"),
        volume=10000,
    )
    db_session.add(candle)
    await db_session.commit()

    response = await auth_client.get(
        f"/api/v1/market/prices/{test_security.id}?interval=1h"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["security_id"] == str(test_security.id)
    assert result["total"] >= 1
    assert len(result["items"]) >= 1
    assert Decimal(result["items"][0]["close"]) == Decimal("151.00")


@pytest.mark.anyio
async def test_get_prices_invalid_interval_returns_422(auth_client, test_security):
    """Test GET /market/prices/{security_id} with invalid interval returns 422."""
    response = await auth_client.get(
        f"/api/v1/market/prices/{test_security.id}?interval=invalid"
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_get_prices_1d_missing_dates_returns_422(auth_client, test_security):
    """Test GET /market/prices/{security_id} with interval=1d missing dates returns 422."""
    response = await auth_client.get(
        f"/api/v1/market/prices/{test_security.id}?interval=1d"
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_get_prices_from_date_after_to_date_returns_422(auth_client, test_security):
    """Test GET /market/prices/{security_id} with from_date > to_date returns 422."""
    response = await auth_client.get(
        f"/api/v1/market/prices/{test_security.id}?interval=1d&from_date=2026-02-01&to_date=2026-01-01"
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_get_prices_security_not_found_returns_404(auth_client):
    """Test GET /market/prices/{security_id} returns 404 if security not found."""
    from uuid import uuid4
    fake_id = uuid4()
    response = await auth_client.get(
        f"/api/v1/market/prices/{fake_id}?from_date=2026-01-01&to_date=2026-01-31"
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_get_prices_1w_weekly_aggregation(auth_client, test_security):
    """Test GET /market/prices/{security_id} with interval=1w aggregates daily prices into weekly candles."""
    response = await auth_client.get(
        f"/api/v1/market/prices/{test_security.id}?interval=1w&from_date=2026-01-01&to_date=2026-01-31"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["security_id"] == str(test_security.id)
    assert result["total"] == 5
    assert len(result["items"]) == 5
    assert result["items"][0]["date"] < result["items"][1]["date"]


@pytest.mark.anyio
async def test_get_prices_1m_monthly_aggregation(auth_client, test_security):
    """Test GET /market/prices/{security_id} with interval=1m aggregates daily prices into monthly candles."""
    response = await auth_client.get(
        f"/api/v1/market/prices/{test_security.id}?interval=1m&from_date=2026-01-01&to_date=2026-02-28"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["security_id"] == str(test_security.id)
    assert result["total"] == 2
    assert len(result["items"]) == 2
    assert result["items"][0]["date"] == "2026-01-01"
    assert result["items"][1]["date"].startswith("2026-02-")


