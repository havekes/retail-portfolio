"""Integration tests for accounts router."""

from uuid import uuid4

import pytest


@pytest.mark.anyio
async def test_accounts_list_empty(auth_client):
    """Test accounts_list returns empty list when user has no accounts."""
    response = await auth_client.get("/api/accounts/")

    assert response.status_code == 200
    result = response.json()

    assert result == []


@pytest.mark.anyio
async def test_accounts_list_success(auth_client, test_accounts):
    """Test accounts_list returns user's accounts."""
    response = await auth_client.get("/api/accounts/")

    assert response.status_code == 200
    result = response.json()

    assert len(result) == 2
    assert result[0]["name"] == "Test Account 0"
    assert result[1]["name"] == "Test Account 1"


@pytest.mark.anyio
async def test_account_rename_success(auth_client, test_accounts):
    """Test account_rename successfully renames an account."""
    account_id = test_accounts[0].id
    new_name = "Renamed Account"
    rename_request = {"name": new_name}

    response = await auth_client.patch(
        f"/api/accounts/{account_id}/rename", json=rename_request
    )

    assert response.status_code == 200
    result = response.json()

    assert result["name"] == new_name
    assert result["id"] == str(account_id)


@pytest.mark.anyio
async def test_account_rename_not_found(auth_client):
    """Test account_rename raises 404 for non-existent account."""
    fake_id = uuid4()
    new_name = "Should Not Rename"
    rename_request = {"name": new_name}

    response = await auth_client.patch(
        f"/api/accounts/{fake_id}/rename", json=rename_request
    )

    assert response.status_code == 404


@pytest.mark.anyio
async def test_account_rename_not_owned(auth_client, other_user_account):
    """Test account_rename raises 404 for account not owned by user."""
    account_id = other_user_account.id
    new_name = "Should Not Rename"
    rename_request = {"name": new_name}

    response = await auth_client.patch(
        f"/api/accounts/{account_id}/rename", json=rename_request
    )

    assert response.status_code == 404


@pytest.mark.anyio
@pytest.mark.skip(reason="Requires EODHD API mock")
async def test_account_totals_success(auth_client, test_accounts, test_positions):
    """Test account_totals returns totals for an account."""
    account_id = test_accounts[0].id

    response = await auth_client.get(f"/api/accounts/{account_id}/totals")

    assert response.status_code == 200
    result = response.json()

    # Verify the response contains cost totals
    assert "cost" in result
    # Note: The actual value depends on market data service which may query external APIs
    assert "value" in result["cost"]
    assert result["cost"]["value"].endswith(" CAD")


@pytest.mark.anyio
@pytest.mark.skip(reason="Requires EODHD API mock")
async def test_account_totals_not_found(auth_client):
    """Test account_totals raises 404 for non-existent account."""
    fake_id = uuid4()

    response = await auth_client.get(f"/api/accounts/{fake_id}/totals")

    assert response.status_code == 404


@pytest.mark.anyio
@pytest.mark.skip(reason="Requires EODHD API mock")
async def test_account_totals_not_owned(auth_client, other_user_account):
    """Test account_totals raises 404 for account not owned by user."""
    account_id = other_user_account.id

    response = await auth_client.get(f"/api/accounts/{account_id}/totals")

    assert response.status_code == 404


@pytest.mark.anyio
@pytest.mark.skip(reason="Requires EODHD API mock")
async def test_positions_by_account_success(
    auth_client, test_accounts, test_position_for_first_account
):
    """Test positions_by_account returns positions for an account."""
    account_id = test_accounts[0].id

    response = await auth_client.get(f"/api/accounts/{account_id}/positions")
    assert response.status_code == 200
    result = response.json()

    assert len(result) == 1
    assert result[0]["account_id"] == str(account_id)
    assert result[0]["security_id"] == str(test_position_for_first_account.security_id)


@pytest.mark.anyio
@pytest.mark.skip(reason="Requires EODHD API mock")
async def test_positions_by_account_not_found(auth_client):
    """Test positions_by_account raises 404 for non-existent account."""
    fake_id = uuid4()

    response = await auth_client.get(f"/api/accounts/{fake_id}/positions")

    assert response.status_code == 404


@pytest.mark.anyio
@pytest.mark.skip(reason="Requires EODHD API mock")
async def test_positions_by_account_not_owned(auth_client, other_user_account):
    """Test positions_by_account raises 404 for account not owned by user."""
    account_id = other_user_account.id

    response = await auth_client.get(f"/api/accounts/{account_id}/positions")

    assert response.status_code == 404


@pytest.mark.anyio
@pytest.mark.skip(reason="Requires EODHD API mock")
async def test_positions_by_account_empty(auth_client, test_accounts):
    """Test positions_by_account returns empty list when account has no positions."""
    account_id = test_accounts[1].id

    response = await auth_client.get(f"/api/accounts/{account_id}/positions")

    assert response.status_code == 200
    result = response.json()
    assert result == []


@pytest.mark.anyio
async def test_account_rename_invalid_body(auth_client, test_accounts):
    """Test account_rename raises 422 for invalid request body."""
    account_id = test_accounts[0].id
    rename_request = {}  # Missing "name" field

    response = await auth_client.patch(
        f"/api/accounts/{account_id}/rename", json=rename_request
    )

    assert response.status_code == 422
