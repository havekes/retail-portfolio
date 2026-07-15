"""Tests for the GET /accounts/sync-status endpoint."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import redis


@pytest.mark.anyio
async def test_sync_status_returns_empty(auth_client):
    """Test sync_status returns empty list when no active syncs."""
    with patch("src.account.router.get_active_syncs", new=AsyncMock(return_value=[])):
        response = await auth_client.get("/api/accounts/sync-status")

    assert response.status_code == 200
    result = response.json()
    assert result == {"account_ids": []}


@pytest.mark.anyio
async def test_sync_status_returns_active_accounts(auth_client):
    """Test sync_status returns active sync account IDs."""
    active_id = uuid4()
    with patch("src.account.router.get_active_syncs", new=AsyncMock(return_value=[active_id])):
        response = await auth_client.get("/api/accounts/sync-status")

    assert response.status_code == 200
    result = response.json()
    assert result == {"account_ids": [str(active_id)]}


@pytest.mark.anyio
async def test_sync_status_scoped_to_authenticated_user(auth_client, test_user):
    """Test sync_status is scoped to the authenticated user."""
    active_id = uuid4()
    mock_get = AsyncMock(return_value=[active_id])

    with patch("src.account.router.get_active_syncs", mock_get):
        response = await auth_client.get("/api/accounts/sync-status")

    assert response.status_code == 200
    mock_get.assert_awaited_once_with(test_user.id)


@pytest.mark.anyio
async def test_sync_status_unauthorized():
    """Test sync_status returns 401 without auth."""
    from asgi_lifespan import LifespanManager
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/accounts/sync-status")

    assert response.status_code in (401, 403)


@pytest.mark.anyio
async def test_sync_status_redis_unavailable(auth_client):
    """Test sync_status returns 503 when Redis is down."""
    with patch(
        "src.account.router.get_active_syncs",
        new=AsyncMock(side_effect=redis.RedisError("Connection refused")),
    ):
        response = await auth_client.get("/api/accounts/sync-status")

    assert response.status_code == 503
