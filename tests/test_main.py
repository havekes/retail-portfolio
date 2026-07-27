import pytest


@pytest.mark.anyio
async def test_health_live(auth_client):
    response = await auth_client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}

@pytest.mark.anyio
async def test_health_ready(auth_client):
    response = await auth_client.get("/health/ready")
    print(response.json())
    assert response.status_code == 200
    assert response.json()["status"] == "ready"

@pytest.mark.anyio
async def test_ping(auth_client):
    response = await auth_client.get("/api/ping")

    assert response.status_code == 200
    # result = response.json()

    # assert result == {
    #     "ping": "pong",
    #     "database": "ok"
    # }
