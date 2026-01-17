"""Integration tests for positions router."""

from uuid import uuid4

from src.schemas.account import Account
from src.schemas.position import Position


def test_positions_by_account_not_found(auth_client):
    """Test that positions_by_account returns 404 for non-existent account."""
    fake_account_id = uuid4()

    response = auth_client.get(f"/api/positions/{fake_account_id}")

    assert response.status_code == 404
