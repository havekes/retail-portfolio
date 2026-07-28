import pytest
from unittest.mock import AsyncMock
from contextlib import asynccontextmanager

@pytest.mark.anyio
async def test_health_live(client):
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}

@pytest.mark.anyio
async def test_health_ready(monkeypatch, client):
    # Setup mock for redis client context manager
    mock_redis = AsyncMock()
    mock_redis.ping.return_value = True

    @asynccontextmanager
    async def mock_client():
        yield mock_redis

    monkeypatch.setattr("src.main.redis_manager.client", mock_client)
    
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"

@pytest.mark.anyio
async def test_ping(client):
    response = await client.get("/api/ping")
    assert response.status_code == 200
