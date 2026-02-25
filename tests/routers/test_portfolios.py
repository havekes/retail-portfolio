"""Integration tests for portfolios router."""

from uuid import uuid4

import pytest


@pytest.mark.anyio
async def test_portfolios_list_empty(auth_client):
    """Test portfolios_list returns empty list when user has no portfolios."""
    response = await auth_client.get("/api/portfolios/")

    assert response.status_code == 200
    result = response.json()

    assert result == []


@pytest.mark.anyio
async def test_portfolios_list_success(auth_client, test_portfolios):
    """Test portfolios_list returns user's portfolios."""
    response = await auth_client.get("/api/portfolios/")

    assert response.status_code == 200
    result = response.json()

    assert len(result) == 2
    assert result[0]["name"] == "Test Portfolio 0"
    assert result[1]["name"] == "Test Portfolio 1"


@pytest.mark.anyio
async def test_portfolio_create_success(auth_client, test_accounts):
    """Test portfolio_create successfully creates a portfolio."""
    portfolio_request = {
        "name": "New Portfolio",
        "accounts": [str(test_accounts[0].id)],
    }
    response = await auth_client.post("/api/portfolios/", json=portfolio_request)

    assert response.status_code == 200
    result = response.json()

    assert result["name"] == "New Portfolio"
    assert result["id"] is not None
    assert len(result["accounts"]) == 1
    assert result["accounts"][0]["id"] == str(test_accounts[0].id)


@pytest.mark.anyio
async def test_portfolio_create_with_multiple_accounts(auth_client, test_accounts):
    """Test portfolio_create successfully creates a portfolio with multiple accounts."""
    account_ids = [str(acc.id) for acc in test_accounts[:2]]
    portfolio_request = {
        "name": "Portfolio with Multiple Accounts",
        "accounts": account_ids,
    }
    response = await auth_client.post("/api/portfolios/", json=portfolio_request)

    assert response.status_code == 200
    result = response.json()

    assert result["name"] == "Portfolio with Multiple Accounts"
    assert len(result["accounts"]) == 2
    assert result["accounts"][0]["id"] in account_ids
    assert result["accounts"][1]["id"] in account_ids


@pytest.mark.anyio
async def test_portfolio_create_missing_name(auth_client):
    """Test portfolio_create raises 422 for missing name field."""
    portfolio_request = {"accounts": []}
    response = await auth_client.post("/api/portfolios/", json=portfolio_request)

    assert response.status_code == 422


@pytest.mark.anyio
async def test_portfolio_create_missing_accounts(auth_client):
    """Test portfolio_create raises 422 for missing accounts field."""
    portfolio_request = {"name": "Test Portfolio"}
    response = await auth_client.post("/api/portfolios/", json=portfolio_request)

    assert response.status_code == 422


@pytest.mark.anyio
async def test_portfolio_accounts_update_success(
    auth_client, test_portfolio_with_accounts, test_accounts
):
    """Test portfolio_accounts_update successfully updates portfolio accounts."""
    portfolio_id = test_portfolio_with_accounts.id
    # Add one more account, remove none (keep existing)
    account_ids = [str(acc.id) for acc in test_accounts[:2]]

    update_request = {"accounts": account_ids}
    response = await auth_client.put(
        f"/api/portfolios/{portfolio_id}/accounts", json=update_request
    )

    assert response.status_code == 200
    result = response.json()

    assert result["id"] == str(portfolio_id)
    assert result["name"] == "Portfolio with Accounts"
    # Should have 2 accounts now (the 2 test accounts)
    assert len(result["accounts"]) == 2


@pytest.mark.anyio
async def test_portfolio_accounts_update_add_accounts(
    auth_client, test_portfolio_with_accounts, test_accounts
):
    """Test portfolio_accounts_update successfully adds accounts to portfolio."""
    portfolio_id = test_portfolio_with_accounts.id
    # Add the third account to the portfolio
    new_account_id = str(test_accounts[2].id)
    account_ids = [str(test_accounts[0].id), str(test_accounts[1].id), new_account_id]

    update_request = {"accounts": account_ids}
    response = await auth_client.put(
        f"/api/portfolios/{portfolio_id}/accounts", json=update_request
    )

    assert response.status_code == 200
    result = response.json()

    assert result["id"] == str(portfolio_id)
    # Should now have 3 accounts
    assert len(result["accounts"]) == 3
    # Verify all accounts are present
    result_account_ids = {acc["id"] for acc in result["accounts"]}
    assert result_account_ids == set(account_ids)


@pytest.mark.anyio
async def test_portfolio_accounts_update_remove_accounts(
    auth_client, test_portfolio_with_accounts, test_accounts
):
    """Test portfolio_accounts_update successfully removes accounts from portfolio."""
    portfolio_id = test_portfolio_with_accounts.id
    # Remove one account, keep one
    account_ids = [str(test_accounts[0].id)]

    update_request = {"accounts": account_ids}
    response = await auth_client.put(
        f"/api/portfolios/{portfolio_id}/accounts", json=update_request
    )

    assert response.status_code == 200
    result = response.json()

    assert result["id"] == str(portfolio_id)
    # Should now have only 1 account
    assert len(result["accounts"]) == 1
    assert result["accounts"][0]["id"] == str(test_accounts[0].id)


@pytest.mark.anyio
async def test_portfolio_accounts_update_not_found(auth_client):
    """Test portfolio_accounts_update raises 404 for non-existent portfolio."""
    fake_id = uuid4()
    update_request = {"accounts": []}

    response = await auth_client.put(
        f"/api/portfolios/{fake_id}/accounts", json=update_request
    )

    assert response.status_code == 404


@pytest.mark.anyio
async def test_portfolio_accounts_update_not_owned(
    auth_client, other_user_portfolio, test_accounts
):
    """Test portfolio_accounts_update raises 404 for portfolio not owned by user."""
    portfolio_id = other_user_portfolio.id
    update_request = {"accounts": [str(test_accounts[0].id)]}

    response = await auth_client.put(
        f"/api/portfolios/{portfolio_id}/accounts", json=update_request
    )

    assert response.status_code == 404


@pytest.mark.anyio
async def test_portfolio_delete_success(auth_client, test_portfolios):
    """Test portfolio_delete successfully deletes a portfolio."""
    portfolio_id = test_portfolios[0].id

    response = await auth_client.delete(f"/api/portfolios/{portfolio_id}")

    assert response.status_code == 204

    # Verify portfolio is deleted
    response = await auth_client.get("/api/portfolios/")
    assert response.status_code == 200
    result = response.json()
    assert len(result) == 1
    assert result[0]["id"] != str(portfolio_id)


@pytest.mark.anyio
async def test_portfolio_delete_not_found(auth_client):
    """Test portfolio_delete raises 404 for non-existent portfolio."""
    fake_id = uuid4()

    response = await auth_client.delete(f"/api/portfolios/{fake_id}")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_portfolio_delete_not_owned(auth_client, other_user_portfolio):
    """Test portfolio_delete raises 404 for portfolio not owned by user."""
    portfolio_id = other_user_portfolio.id

    response = await auth_client.delete(f"/api/portfolios/{portfolio_id}")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_portfolio_accounts_update_empty(auth_client, test_portfolios):
    """Test portfolio_accounts_update successfully empties portfolio accounts."""
    portfolio_id = test_portfolios[0].id

    update_request = {"accounts": []}
    response = await auth_client.put(
        f"/api/portfolios/{portfolio_id}/accounts", json=update_request
    )

    assert response.status_code == 200
    result = response.json()

    assert result["id"] == str(portfolio_id)
    # Portfolio should now have no accounts
    assert len(result["accounts"]) == 0
