import pytest
from sqlalchemy import text
from src.account.enum import InstitutionEnum

@pytest.mark.anyio
async def test_get_institutions_empty(auth_client):
    """Test get institutions returns empty list when no integrations enabled."""
    response = await auth_client.get("/api/integration/institutions")
    assert response.status_code == 200
    data = response.json()
    assert data == []

@pytest.mark.anyio
async def test_get_institutions_success(auth_client, db_session):
    """Test get institutions returns enabled integrations."""

    # Enable Wealthsimple
    await db_session.execute(
        text("UPDATE account_institutions SET integration_enabled = true WHERE id = :id"),
        {"id": InstitutionEnum.WEALTHSIMPLE.value}
    )
    await db_session.commit()

    response = await auth_client.get("/api/integration/institutions")
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    assert data[0]["id"] == InstitutionEnum.WEALTHSIMPLE.value
    assert data[0]["integration_enabled"] is True
