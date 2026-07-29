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
async def test_get_intraday_prices_1h_default(auth_client, db_session):
    """Test GET /prices/{security_id}/intraday returns 1h candles by default."""
    from uuid import uuid4
    from datetime import datetime, timezone
    from decimal import Decimal
    from src.market.repository_sqlalchemy import (
        SqlAlchemySecurityRepository,
        SqlAlchemyIntradayPriceRepository,
    )
    from src.market.schema import SecuritySchema, IntradayPriceSchema

    security_repo = SqlAlchemySecurityRepository(db_session)
    intraday_repo = SqlAlchemyIntradayPriceRepository(db_session)

    security = await security_repo.get_or_create(
        SecuritySchema(
            id=uuid4(),
            symbol="AAPL",
            exchange="US",
            currency="USD",
            name="Apple Inc",
            isin=None,
            is_active=True,
            updated_at=datetime.now(timezone.utc),
        )
    )

    base_time = datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc)
    candles = [
        IntradayPriceSchema(
            security_id=security.id,
            timestamp=base_time,
            open=Decimal("100.0"),
            high=Decimal("105.0"),
            low=Decimal("98.0"),
            close=Decimal("102.0"),
            volume=1000,
        ),
        IntradayPriceSchema(
            security_id=security.id,
            timestamp=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
            open=Decimal("102.0"),
            high=Decimal("108.0"),
            low=Decimal("101.0"),
            close=Decimal("107.0"),
            volume=1500,
        ),
    ]
    await intraday_repo.save_intraday_prices(candles)

    response = await auth_client.get(f"/api/v1/market/prices/{security.id}/intraday")
    assert response.status_code == 200
    data = response.json()
    assert data["interval"] == "1h"
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert Decimal(str(data["items"][0]["open"])) == Decimal("100.0")


@pytest.mark.anyio
async def test_get_intraday_prices_4h_aggregation(auth_client, db_session):
    """Test GET /prices/{security_id}/intraday?interval=4h aggregates 1h candles into 4h candles."""
    from uuid import uuid4
    from datetime import datetime, timezone
    from decimal import Decimal
    from src.market.repository_sqlalchemy import (
        SqlAlchemySecurityRepository,
        SqlAlchemyIntradayPriceRepository,
    )
    from src.market.schema import SecuritySchema, IntradayPriceSchema

    security_repo = SqlAlchemySecurityRepository(db_session)
    intraday_repo = SqlAlchemyIntradayPriceRepository(db_session)

    security = await security_repo.get_or_create(
        SecuritySchema(
            id=uuid4(),
            symbol="MSFT",
            exchange="US",
            currency="USD",
            name="Microsoft Corp",
            isin=None,
            is_active=True,
            updated_at=datetime.now(timezone.utc),
        )
    )

    candles = [
        IntradayPriceSchema(
            security_id=security.id,
            timestamp=datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc),
            open=Decimal("100.0"),
            high=Decimal("105.0"),
            low=Decimal("98.0"),
            close=Decimal("102.0"),
            volume=1000,
        ),
        IntradayPriceSchema(
            security_id=security.id,
            timestamp=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
            open=Decimal("102.0"),
            high=Decimal("108.0"),
            low=Decimal("101.0"),
            close=Decimal("107.0"),
            volume=1500,
        ),
        IntradayPriceSchema(
            security_id=security.id,
            timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
            open=Decimal("107.0"),
            high=Decimal("109.0"),
            low=Decimal("104.0"),
            close=Decimal("105.0"),
            volume=1200,
        ),
        IntradayPriceSchema(
            security_id=security.id,
            timestamp=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
            open=Decimal("105.0"),
            high=Decimal("110.0"),
            low=Decimal("103.0"),
            close=Decimal("108.0"),
            volume=800,
        ),
    ]
    await intraday_repo.save_intraday_prices(candles)

    response = await auth_client.get(
        f"/api/v1/market/prices/{security.id}/intraday?interval=4h"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["interval"] == "4h"
    assert data["total"] == 2
    assert len(data["items"]) == 2

    bucket1 = data["items"][0]
    assert Decimal(str(bucket1["open"])) == Decimal("100.0")
    assert Decimal(str(bucket1["high"])) == Decimal("109.0")
    assert Decimal(str(bucket1["low"])) == Decimal("98.0")
    assert Decimal(str(bucket1["close"])) == Decimal("105.0")
    assert bucket1["volume"] == 3700

    bucket2 = data["items"][1]
    assert Decimal(str(bucket2["open"])) == Decimal("105.0")
    assert Decimal(str(bucket2["high"])) == Decimal("110.0")
    assert Decimal(str(bucket2["low"])) == Decimal("103.0")
    assert Decimal(str(bucket2["close"])) == Decimal("108.0")
    assert bucket2["volume"] == 800


@pytest.mark.anyio
async def test_get_intraday_prices_validation_and_not_found(auth_client, test_security):
    """Test validation errors (422) and missing security (404)."""
    from uuid import uuid4

    resp = await auth_client.get(
        f"/api/v1/market/prices/{test_security.id}/intraday?interval=2h"
    )
    assert resp.status_code == 422

    resp = await auth_client.get(
        f"/api/v1/market/prices/{test_security.id}/intraday?from_datetime=2026-01-16T00:00:00Z&to_datetime=2026-01-15T00:00:00Z"
    )
    assert resp.status_code == 422

    missing_id = uuid4()
    resp = await auth_client.get(f"/api/v1/market/prices/{missing_id}/intraday")
    assert resp.status_code == 404
