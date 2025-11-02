from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_ping():
    """Test the /api/ping endpoint."""
    response = client.get("/api/ping")
    assert response.status_code == 200
    assert response.json() == {"ping": "pong"}
