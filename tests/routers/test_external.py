"""Integration tests for external router."""

from uuid import uuid4

import pytest

from src.account.enum import InstitutionEnum


@pytest.mark.anyio
async def test_external_users_empty(auth_client, seed_reference_data):
    """Test external_users returns empty list when user has no external users."""
    response = await auth_client.get(
        f"/api/external/{InstitutionEnum.WEALTHSIMPLE}/users"
    )

    assert response.status_code == 200
    result = response.json()

    assert result == []


@pytest.mark.anyio
async def test_external_users_success(auth_client, test_external_user):
    """Test external_users returns user's external users."""
    response = await auth_client.get(
        f"/api/external/{InstitutionEnum.WEALTHSIMPLE}/users"
    )

    assert response.status_code == 200
    result = response.json()

    assert len(result) == 1
    assert result[0]["id"] == str(test_external_user.id)
    assert result[0]["display_name"] == test_external_user.display_name


@pytest.mark.anyio
async def test_external_login_success(auth_client, seed_reference_data):
    """Test external_login successfully logs into external institution."""
    login_request = {
        "username": "testuser",
        "password": "testpass",
        "otp": None,
    }

    response = await auth_client.post(
        f"/api/external/{InstitutionEnum.WEALTHSIMPLE}/login", json=login_request
    )

    assert response.status_code == 200
    result = response.json()

    assert result["login_succes"] is True


@pytest.mark.anyio
async def test_external_accounts_success(auth_client, test_external_user):
    """Test external_accounts returns list of external accounts."""
    response = await auth_client.get(
        f"/api/external/{InstitutionEnum.WEALTHSIMPLE}/{test_external_user.id}/accounts"
    )

    # The endpoint should successfully return (even if empty due to mock returning empty list)
    assert response.status_code == 200
    result = response.json()

    # The mock wrapper returns an empty list by default
    assert isinstance(result, list)


@pytest.mark.anyio
async def test_external_accounts_not_found(auth_client):
    """Test external_accounts raises 404 for non-existent external user."""
    fake_id = uuid4()

    response = await auth_client.get(
        f"/api/external/{InstitutionEnum.WEALTHSIMPLE}/{fake_id}/accounts"
    )

    assert response.status_code == 404


@pytest.mark.anyio
async def test_external_accounts_not_owned(auth_client, other_user_external_user):
    """Test external_accounts raises 404 for non-owned external user."""
    response = await auth_client.get(
        f"/api/external/{InstitutionEnum.WEALTHSIMPLE}/{other_user_external_user.id}/accounts"
    )

    assert response.status_code == 404


@pytest.mark.anyio
async def test_external_import_accounts_success(auth_client, test_external_user):
    """Test external_import_accounts successfully imports accounts."""
    import_request = {
        "external_user_id": str(test_external_user.id),
        "external_account_ids": ["ext_acc_1"],
    }

    response = await auth_client.post(
        f"/api/external/{InstitutionEnum.WEALTHSIMPLE}/accounts/import",
        json=import_request,
    )

    # The endpoint should successfully process the request
    assert response.status_code == 200
    result = response.json()

    # The mock wrapper returns an empty list by default, so imported_count will be 0
    assert "imported_count" in result
    assert isinstance(result["imported_count"], int)


@pytest.mark.anyio
async def test_external_import_accounts_no_selection(auth_client, test_external_user):
    """Test external_import_accounts with no specific account selection."""
    import_request = {
        "external_user_id": str(test_external_user.id),
        "external_account_ids": [],
    }

    response = await auth_client.post(
        f"/api/external/{InstitutionEnum.WEALTHSIMPLE}/accounts/import",
        json=import_request,
    )

    # The endpoint should successfully process the request
    assert response.status_code == 200
    result = response.json()

    # The mock wrapper returns an empty list by default
    assert "imported_count" in result
    assert isinstance(result["imported_count"], int)


@pytest.mark.anyio
async def test_external_import_accounts_not_found(auth_client):
    """Test external_import_accounts raises 404 for non-existent external user."""
    fake_id = uuid4()
    import_request = {
        "external_user_id": str(fake_id),
        "external_account_ids": [],
    }

    response = await auth_client.post(
        f"/api/external/{InstitutionEnum.WEALTHSIMPLE}/accounts/import",
        json=import_request,
    )

    assert response.status_code == 404


@pytest.mark.anyio
async def test_external_import_accounts_not_owned(
    auth_client, other_user_external_user
):
    """Test external_import_accounts raises 404 for non-owned external user."""
    import_request = {
        "external_user_id": str(other_user_external_user.id),
        "external_account_ids": [],
    }

    response = await auth_client.post(
        f"/api/external/{InstitutionEnum.WEALTHSIMPLE}/accounts/import",
        json=import_request,
    )

    assert response.status_code == 404


@pytest.mark.anyio
async def test_external_import_positions_success(
    auth_client, test_external_user, test_accounts
):
    """Test external_import_positions successfully imports positions."""
    import_request = {
        "external_user_id": str(test_external_user.id),
        "account_id": str(test_accounts[0].id),
    }

    response = await auth_client.post(
        f"/api/external/{InstitutionEnum.WEALTHSIMPLE}/positions/import",
        json=import_request,
    )

    # The endpoint should successfully process the request
    assert response.status_code == 200
    result = response.json()

    # The mock wrapper returns an empty list by default
    assert "imported_count" in result
    assert isinstance(result["imported_count"], int)


@pytest.mark.anyio
async def test_external_import_positions_external_user_not_found(
    auth_client, test_accounts
):
    """Test external_import_positions raises 404 for non-existent external user."""
    fake_id = uuid4()
    import_request = {
        "external_user_id": str(fake_id),
        "account_id": str(test_accounts[0].id),
    }

    response = await auth_client.post(
        f"/api/external/{InstitutionEnum.WEALTHSIMPLE}/positions/import",
        json=import_request,
    )

    assert response.status_code == 404


@pytest.mark.anyio
async def test_external_import_positions_account_not_found(
    auth_client, test_external_user
):
    """Test external_import_positions raises 404 for non-existent account."""
    fake_account_id = uuid4()
    import_request = {
        "external_user_id": str(test_external_user.id),
        "account_id": str(fake_account_id),
    }

    response = await auth_client.post(
        f"/api/external/{InstitutionEnum.WEALTHSIMPLE}/positions/import",
        json=import_request,
    )

    assert response.status_code == 404


@pytest.mark.anyio
async def test_external_import_positions_not_owned(
    auth_client, other_user_external_user, test_accounts
):
    """Test external_import_positions raises 404 for non-owned external user."""
    import_request = {
        "external_user_id": str(other_user_external_user.id),
        "account_id": str(test_accounts[0].id),
    }

    response = await auth_client.post(
        f"/api/external/{InstitutionEnum.WEALTHSIMPLE}/positions/import",
        json=import_request,
    )

    assert response.status_code == 404
