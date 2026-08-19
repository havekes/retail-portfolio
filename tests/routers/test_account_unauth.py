import pytest
from httpx import ASGITransport, AsyncClient
from src.main import app

@pytest.mark.anyio
async def test_account_rename_unauth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.patch("/api/v1/accounts/123e4567-e89b-12d3-a456-426614174000/rename", json={"name": "test"})
        print(f"STATUS CODE: {response.status_code}")
        print(f"RESPONSE JSON: {response.json()}")
        assert response.status_code == 401


@pytest.mark.anyio
async def test_preferences_get_unauth():
    """GET /me/preferences returns 401 without auth."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/accounts/me/preferences")
        assert response.status_code == 401


@pytest.mark.anyio
async def test_preferences_put_unauth():
    """PUT /me/preferences returns 401 without auth."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.put("/api/v1/accounts/me/preferences", json={"timeframe": "1d"})
        assert response.status_code == 401


@pytest.mark.anyio
async def test_preferences_patch_unauth():
    """PATCH /me/preferences returns 401 without auth."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.patch("/api/v1/accounts/me/preferences", json={"timeframe": "1d"})
        assert response.status_code == 401


