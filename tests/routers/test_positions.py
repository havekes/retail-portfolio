"""Integration tests for positions router."""

from uuid import uuid4


def test_positions_by_account_empty(auth_client, test_accounts):
    """Test that positions_by_account returns empty list when account has no positions."""
    account_id = test_accounts[1].id

    response = auth_client.get(f"/api/positions/{account_id}")

    assert response.status_code == 200
    result = response.json()

    assert result == []


def test_positions_by_account_success(auth_client, test_accounts, test_positions):
    """Test that positions_by_account returns user's positions for the account."""
    account_id = test_accounts[0].id

    response = auth_client.get(f"/api/positions/{account_id}")

    assert response.status_code == 200
    result = response.json()

    assert len(result) == 1
    assert result[0]["security_symbol"] == "AAPL"
    assert result[0]["quantity"] == 10.0
    assert result[0]["average_cost"] == 150.0


def test_positions_by_account_not_found(auth_client):
    """Test that positions_by_account returns 404 for non-existent account."""
    fake_account_id = uuid4()

    response = auth_client.get(f"/api/positions/{fake_account_id}")

    assert response.status_code == 404


def test_positions_by_account_not_owned(auth_client, other_user_account):
    """Test that positions_by_account returns 404 for account not owned by user."""
    account_id = other_user_account.id

    response = auth_client.get(f"/api/positions/{account_id}")

    assert response.status_code == 404
