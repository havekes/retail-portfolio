"""Integration tests for accounts router."""

from uuid import uuid4

from src.schemas.account import Account


def test_accounts_list(auth_client):
    """Test accounts_list returns user's accounts."""
    response = auth_client.get("/api/accounts/")

    assert response.status_code == 200
    result = response.json()

    # User starts with no accounts
    assert result == []


def test_account_rename_not_owned(auth_client):
    """Test account_rename raises 404 for non-existent account."""
    from uuid import uuid4

    fake_id = uuid4()
    new_name = "Should Not Rename"
    rename_request = {"name": new_name}

    response = auth_client.patch(f"/api/accounts/{fake_id}/rename", json=rename_request)

    assert response.status_code == 404


def test_account_totals_not_found(auth_client):
    """Test account_totals raises 404 for non-existent account."""
    fake_id = uuid4()

    response = auth_client.get(f"/api/accounts/{fake_id}/totals")

    assert response.status_code == 404
