import pytest


@pytest.mark.anyio
async def test_ping(auth_client):
    response = await auth_client.get("/api/ping")

    assert response.status_code == 200
    # result = response.json()

    # assert result == {
    #     "ping": "pong",
    #     "database": "ok"
    # }
