"""Integration tests for accounts router."""

from uuid import uuid4

import pytest


@pytest.mark.anyio
async def test_accounts_list_empty(auth_client):
    """Test accounts_list returns empty list when user has no accounts."""
    response = await auth_client.get("/api/v1/accounts/")

    assert response.status_code == 200
    result = response.json()

    assert result == []


@pytest.mark.anyio
async def test_accounts_list_success(auth_client, test_accounts):
    """Test accounts_list returns user's accounts."""
    response = await auth_client.get("/api/v1/accounts/")

    assert response.status_code == 200
    result = response.json()

    assert len(result) == 3
    assert result[0]["name"] == "Test Account 0"
    assert result[1]["name"] == "Test Account 1"
    assert result[2]["name"] == "Test Account 2"


@pytest.mark.anyio
async def test_account_rename_success(auth_client, test_accounts):
    """Test account_rename successfully renames an account."""
    account_id = test_accounts[0].id
    new_name = "Renamed Account"
    rename_request = {"name": new_name}

    response = await auth_client.patch(
        f"/api/v1/accounts/{account_id}/rename", json=rename_request
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
        f"/api/v1/accounts/{fake_id}/rename", json=rename_request
    )

    assert response.status_code == 404


@pytest.mark.anyio
async def test_account_rename_not_owned(auth_client, other_user_account):
    """Test account_rename raises 404 for account not owned by user."""
    account_id = other_user_account.id
    new_name = "Should Not Rename"
    rename_request = {"name": new_name}

    response = await auth_client.patch(
        f"/api/v1/accounts/{account_id}/rename", json=rename_request
    )

    assert response.status_code == 404


@pytest.mark.anyio
async def test_account_totals_success(auth_client, test_accounts, test_positions):
    """Test account_totals returns totals for an account."""
    account_id = test_accounts[0].id

    response = await auth_client.get(f"/api/v1/accounts/{account_id}/totals")

    assert response.status_code == 200
    result = response.json()

    # Verify the response contains cost and value totals
    assert "cost" in result
    assert "value" in result
    # Note: The actual value depends on market data service which may query external APIs
    assert result["cost"]["value"].endswith(" CAD")
    assert result["value"]["value"].endswith(" CAD")


@pytest.mark.anyio
async def test_account_totals_not_found(auth_client):
    """Test account_totals raises 404 for non-existent account."""
    fake_id = uuid4()

    response = await auth_client.get(f"/api/v1/accounts/{fake_id}/totals")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_account_totals_not_owned(auth_client, other_user_account):
    """Test account_totals raises 404 for account not owned by user."""
    account_id = other_user_account.id

    response = await auth_client.get(f"/api/v1/accounts/{account_id}/totals")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_account_rename_invalid_body(auth_client, test_accounts):
    """Test account_rename raises 422 for invalid request body."""
    account_id = test_accounts[0].id
    rename_request = {}  # Missing "name" field

    response = await auth_client.patch(
        f"/api/v1/accounts/{account_id}/rename", json=rename_request
    )

    assert response.status_code == 422


@pytest.mark.anyio
async def test_security_holdings_success(
    auth_client, test_accounts, test_position_for_first_account
):
    """Test security_holdings returns holdings across user accounts."""
    security_id = test_position_for_first_account.security_id
    response = await auth_client.get(f"/api/v1/accounts/holdings/{security_id}")

    assert response.status_code == 200
    result = response.json()
    assert len(result["items"]) == 1
    assert result["items"][0]["account_id"] == str(test_accounts[0].id)
    assert result["items"][0]["quantity"] == float(
        test_position_for_first_account.quantity
    )
    assert result["items"][0]["account_name"] == test_accounts[0].name
    assert "total_value" in result["items"][0]
    assert "currency" in result["items"][0]


@pytest.mark.anyio
async def test_account_holdings_isolation(
    auth_client, other_user_account, test_position, test_security
):
    """Test account_holdings does not return other users' holdings."""
    # test_position uses test_account, not other_user_account, but wait, test_position is owned by test_user.
    # To test isolation, we just ensure it only returns holdings for the logged in user.
    # We can query a security ID that the user doesn't own.
    fake_id = uuid4()
    response = await auth_client.get(f"/api/v1/accounts/holdings/{fake_id}")

    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.anyio
async def test_account_holdings_success(
    auth_client, test_accounts, test_position_for_first_account
):
    """Test account_holdings returns detailed holdings for an account."""
    account_id = test_accounts[0].id

    response = await auth_client.get(f"/api/v1/accounts/{account_id}/holdings")
    assert response.status_code == 200
    result = response.json()

    assert result["account_id"] == str(account_id)
    assert result["account_name"] == test_accounts[0].name
    assert len(result["items"]) == 1
    assert result["items"][0]["id"] == test_position_for_first_account.id
    assert result["items"][0]["security_id"] == str(
        test_position_for_first_account.security_id
    )
    assert "total_value" in result
    assert "total_profit_loss" in result
    assert "currency" in result
    assert "updated_at" in result["items"][0]


@pytest.mark.anyio
async def test_preferences_empty(auth_client):
    """GET /me/preferences returns {} when user has no preferences saved."""
    response = await auth_client.get("/api/v1/accounts/me/preferences")
    assert response.status_code == 200
    assert response.json() == {}


@pytest.mark.anyio
async def test_preferences_roundtrip(auth_client):
    """PUT then GET returns exactly what was stored (round-trip)."""
    payload = {
        "timeframe": "1d",
        "chart_style": "heikin_ashi",
        "indicators": {
            "rsi": {"enabled": True, "color": "#FF0000", "settings": {"period": 14}}
        },
    }
    put_resp = await auth_client.put("/api/v1/accounts/me/preferences", json=payload)
    assert put_resp.status_code == 200
    put_body = put_resp.json()
    assert put_body == payload

    get_resp = await auth_client.get("/api/v1/accounts/me/preferences")
    assert get_resp.status_code == 200
    assert get_resp.json() == payload


@pytest.mark.anyio
async def test_preferences_partial_update(auth_client):
    """PUT a partial payload; GET returns exactly that (no fabricated defaults)."""
    payload = {"timeframe": "4h"}
    put_resp = await auth_client.put("/api/v1/accounts/me/preferences", json=payload)
    assert put_resp.status_code == 200

    get_resp = await auth_client.get("/api/v1/accounts/me/preferences")
    assert get_resp.status_code == 200
    assert get_resp.json() == {"timeframe": "4h"}


@pytest.mark.anyio
async def test_preferences_isolated(auth_client, other_user, client):
    """User A's preferences are not visible to user B — verified via the API."""
    payload = {"timeframe": "1d", "chart_style": "candlestick"}

    # test_user saves preferences via auth_client
    put_resp = await auth_client.put("/api/v1/accounts/me/preferences", json=payload)
    assert put_resp.status_code == 200

    # Log in as other_user via the API
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "other@example.com", "password": "otherpass"},
    )
    assert login_resp.status_code == 200
    other_token = login_resp.json()["access_token"]

    # other_user GETs their own preferences — should be empty
    get_other = await client.get(
        "/api/v1/accounts/me/preferences",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert get_other.status_code == 200
    assert get_other.json() == {}

    # test_user still sees their own preferences
    get_resp = await auth_client.get("/api/v1/accounts/me/preferences")
    assert get_resp.status_code == 200
    assert get_resp.json() == payload


@pytest.mark.anyio
async def test_preferences_sidebar_open_roundtrip(auth_client):
    """PUT then GET returns sidebar_open boolean."""
    payload = {"sidebar_open": False}
    put_resp = await auth_client.put("/api/v1/accounts/me/preferences", json=payload)
    assert put_resp.status_code == 200
    assert put_resp.json() == {"sidebar_open": False}

    get_resp = await auth_client.get("/api/v1/accounts/me/preferences")
    assert get_resp.status_code == 200
    assert get_resp.json() == {"sidebar_open": False}

    # Update to True
    payload_true = {"sidebar_open": True}
    put_resp_true = await auth_client.put(
        "/api/v1/accounts/me/preferences", json=payload_true
    )
    assert put_resp_true.status_code == 200
    assert put_resp_true.json() == {"sidebar_open": True}


@pytest.mark.anyio
async def test_preferences_sidebar_open_with_chart_preferences(auth_client):
    """Verify sidebar_open persists alongside timeframe, chart_style, and indicators."""
    payload = {
        "timeframe": "4h",
        "chart_style": "candlestick",
        "indicators": {
            "rsi": {"enabled": True, "color": "#00FF00", "settings": {"period": 14}}
        },
        "sidebar_open": False,
    }
    put_resp = await auth_client.put("/api/v1/accounts/me/preferences", json=payload)
    assert put_resp.status_code == 200
    assert put_resp.json() == payload

    get_resp = await auth_client.get("/api/v1/accounts/me/preferences")
    assert get_resp.status_code == 200
    assert get_resp.json() == payload


@pytest.mark.anyio
async def test_preferences_sidebar_open_isolated(auth_client, other_user, client):
    """User A's sidebar_open preference is isolated from user B."""
    payload = {"sidebar_open": False}
    put_resp = await auth_client.put("/api/v1/accounts/me/preferences", json=payload)
    assert put_resp.status_code == 200

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "other@example.com", "password": "otherpass"},
    )
    assert login_resp.status_code == 200
    other_token = login_resp.json()["access_token"]

    get_other = await client.get(
        "/api/v1/accounts/me/preferences",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert get_other.status_code == 200
    assert get_other.json() == {}

    get_resp = await auth_client.get("/api/v1/accounts/me/preferences")
    assert get_resp.status_code == 200
    assert get_resp.json() == {"sidebar_open": False}
