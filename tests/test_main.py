import pytest
from fastapi.testclient import TestClient
from src.main import app

@pytest.fixture(name="client")
def _client():
    with TestClient(app) as client:
        yield client

@pytest.mark.asyncio
async def test_ping(client):
    """Test the /api/ping endpoint."""
    response = client.get("/api/ping")
    assert response.status_code == 200
    assert response.json() == {"ping": "pong"}
