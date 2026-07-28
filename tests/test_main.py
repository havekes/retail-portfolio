import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.anyio
async def test_health_live(client):
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}

@pytest.mark.anyio
@patch("src.main.redis_manager.client")
async def test_health_ready(mock_redis_client, client):
    # Setup mock for redis client context manager
    mock_redis = AsyncMock()
    mock_redis.ping.return_value = True
    mock_redis_client.return_value.__aenter__.return_value = mock_redis
    
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"

@pytest.mark.anyio
async def test_ping(client):
    response = await client.get("/api/ping")
    assert response.status_code == 200
