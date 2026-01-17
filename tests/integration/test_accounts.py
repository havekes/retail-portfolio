"""Integration tests for accounts router."""

from uuid import uuid4


def test_accounts_list_empty(auth_client):
    """Test accounts_list returns empty list when user has no accounts."""
    response = auth_client.get("/api/accounts/")

    assert response.status_code == 200
    result = response.json()

    assert result == []


def test_accounts_list_success(auth_client, test_accounts):
    """Test accounts_list returns user's accounts."""
    response = auth_client.get("/api/accounts/")

    assert response.status_code == 200
    result = response.json()

    assert len(result) == 2
    assert result[0]["name"] == "Test Account 0"
    assert result[1]["name"] == "Test Account 1"


def test_account_rename_success(auth_client, test_accounts):
    """Test account_rename successfully renames an account."""
    account_id = test_accounts[0].id
    new_name = "Renamed Account"
    rename_request = {"name": new_name}

    response = auth_client.patch(
        f"/api/accounts/{account_id}/rename", json=rename_request
    )

    assert response.status_code == 200
    result = response.json()

    assert result["name"] == new_name
    assert result["id"] == str(account_id)


def test_account_rename_not_found(auth_client):
    """Test account_rename raises 404 for non-existent account."""
    fake_id = uuid4()
    new_name = "Should Not Rename"
    rename_request = {"name": new_name}

    response = auth_client.patch(
        f"/api/accounts/{fake_id}/rename", json=rename_request
    )

    assert response.status_code == 404


def test_account_rename_not_owned(auth_client, other_user_account):
    """Test account_rename raises 404 for account not owned by user."""
    account_id = other_user_account.id
    new_name = "Should Not Rename"
    rename_request = {"name": new_name}

    response = auth_client.patch(
        f"/api/accounts/{account_id}/rename", json=rename_request
    )

    assert response.status_code == 404


def test_account_totals_success(auth_client, test_accounts, test_positions):
    """Test account_totals returns totals for an account."""
    account_id = test_accounts[0].id

    response = auth_client.get(f"/api/accounts/{account_id}/totals")

    assert response.status_code == 200
    result = response.json()

    # Verify the response contains cost totals
    assert "cost" in result
    assert result["cost"]["value"] == "1500.00 CAD"


def test_account_totals_not_found(auth_client):
    """Test account_totals raises 404 for non-existent account."""
    fake_id = uuid4()

    response = auth_client.get(f"/api/accounts/{fake_id}/totals")

    assert response.status_code == 404


def test_account_totals_not_owned(auth_client, other_user_account):
    """Test account_totals raises 404 for account not owned by user."""
    account_id = other_user_account.id

    response = auth_client.get(f"/api/accounts/{account_id}/totals")

    assert response.status_code == 404
