"""Integration tests for market router."""

import pytest

@pytest.mark.anyio
async def test_watchlists_list_empty(auth_client):
    """Test get_watchlists returns empty list when user has no watchlists."""
    response = await auth_client.get("/api/market/watchlists")

    assert response.status_code == 200
    result = response.json()

    assert result == []

@pytest.mark.anyio
async def test_watchlists_list_success(auth_client, test_watchlists):
    """Test get_watchlists returns user's watchlists."""
    response = await auth_client.get("/api/market/watchlists")

    assert response.status_code == 200
    result = response.json()

    assert len(result) == 2
    assert result[0]["name"] == "Test Watchlist 0"
    assert "securities" in result[0]
    assert result[1]["name"] == "Test Watchlist 1"
    assert "securities" in result[1]

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
    
    response = await auth_client.get("/api/market/watchlists")

    assert response.status_code == 200
    result = response.json()

    # Should still be empty for the authenticated user
    assert result == []


@pytest.mark.anyio
async def test_watchlist_add_security(auth_client, test_security):
    """Test POST /watchlists/securities/{security_id} adds a security to the watchlist."""
    response = await auth_client.post(f"/api/market/watchlists/securities/{test_security.id}")
    
    assert response.status_code == 200
    result = response.json()
    assert result["name"] == "Default"
    assert len(result["securities"]) == 1
    assert result["securities"][0]["id"] == str(test_security.id)
    assert result["securities"][0]["symbol"] == test_security.symbol


@pytest.mark.anyio
async def test_watchlist_remove_security(auth_client, test_security):
    """Test DELETE /watchlists/securities/{security_id} removes a security from the watchlist."""
    # First add it
    await auth_client.post(f"/api/market/watchlists/securities/{test_security.id}")
    
    # Now remove it
    response = await auth_client.delete(f"/api/market/watchlists/securities/{test_security.id}")
    
    assert response.status_code == 200
    result = response.json()
    assert result["name"] == "Default"
    assert len(result["securities"]) == 0


@pytest.mark.anyio
async def test_watchlist_add_security_not_found(auth_client):
    """Test POST /watchlists/securities/{security_id} returns 404 if security not found."""
    from uuid import uuid4
    fake_id = uuid4()
    response = await auth_client.post(f"/api/market/watchlists/securities/{fake_id}")
    
    assert response.status_code == 404
    assert "not found" in response.json()["error"].lower()

