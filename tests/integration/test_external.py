"""Integration tests for external router."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import HTTPException
import pytest

from src.enums import AccountTypeEnum, InstitutionEnum
from src.external.schemas.accounts import ExternalAccount
from src.schemas.account import Account
from src.schemas.external import (
    ExternalImportAccountsRequest,
    ExternalImportPositionsRequest,
    ExternalLoginRequest,
)
from src.schemas.external_user import FullExternalUser
from src.schemas.position import Position


def test_external_users_success(auth_client, test_external_user: FullExternalUser):
    """Test external_users returns user's external users."""
    response = auth_client.get("/api/external/wealthsimple/users")

    assert response.status_code == 200
    result = response.json()

    assert len(result) == 1
    assert result[0]["id"] == str(test_external_user.id)
    assert result[0]["display_name"] == test_external_user.display_name


def test_external_users_empty(auth_client, seed_reference_data):
    """Test external_users returns empty list when user has no external users."""
    response = auth_client.get("/api/external/wealthsimple/users")

    assert response.status_code == 200
    result = response.json()

    assert result == []


def test_external_login_success(auth_client, seed_reference_data):
    """Test external_login successfully logs into external institution."""
    login_request = {
        "username": "testuser",
        "password": "testpass",
        "otp": None,
    }

    response = auth_client.post("/api/external/wealthsimple/login", json=login_request)

    assert response.status_code == 200
    result = response.json()

    assert result["login_succes"] is True


@pytest.mark.asyncio
async def test_external_login_failure(
    services_container, test_user: User, seed_reference_data
):
    """Test external_login handles failed login."""
    from src.external.wealthsimple import WealthsimpleApiWrapper

    # Mock the external API wrapper to return False for login
    external_api_wrapper = await services_container.aget(WealthsimpleApiWrapper)
    external_api_wrapper.login = lambda **kwargs: False

    login_request = ExternalLoginRequest(
        username="testuser",
        password="wrongpass",
        otp=None,
    )

    result = await external_login(
        institution=InstitutionEnum.WEALTHSIMPLE,
        login_request=login_request,
        services=services_container,
        user=test_user,
    )

    assert result.login_succes is False


@pytest.mark.asyncio
async def test_external_accounts_success(
    services_container, test_user: User, test_external_user: FullExternalUser
):
    """Test external_accounts returns list of external accounts."""
    from src.external.wealthsimple import WealthsimpleApiWrapper

    # Mock the external API wrapper to return test accounts
    external_api_wrapper = await services_container.aget(WealthsimpleApiWrapper)

    test_accounts_data = [
        ExternalAccount(
            id="ext_acc_1",
            type=AccountTypeEnum.TFSA,
            currency="CAD",
            display_name="TFSA Account",
            value="10000.00",
            created_at=datetime.now(UTC),
        ),
    ]

    external_api_wrapper.list_accounts = AsyncMock(return_value=test_accounts_data)

    result = await external_accounts(
        institution=InstitutionEnum.WEALTHSIMPLE,
        external_user_id=test_external_user.id,
        services=services_container,
        user=test_user,
    )

    assert len(result) == 1
    assert result[0].id == "ext_acc_1"
    assert result[0].display_name == "TFSA Account"


@pytest.mark.asyncio
async def test_external_accounts_not_owned(
    services_container, test_user: User, other_user_external_user: FullExternalUser
):
    """Test external_accounts raises 404 for non-owned external user."""
    with pytest.raises(HTTPException) as exc_info:
        await external_accounts(
            institution=InstitutionEnum.WEALTHSIMPLE,
            external_user_id=other_user_external_user.id,
            services=services_container,
            user=test_user,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_external_accounts_not_found(
    services_container, test_user: User, seed_reference_data
):
    """Test external_accounts raises 404 for non-existent external user."""
    fake_id = uuid4()

    with pytest.raises(HTTPException) as exc_info:
        await external_accounts(
            institution=InstitutionEnum.WEALTHSIMPLE,
            external_user_id=fake_id,
            services=services_container,
            user=test_user,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_external_import_accounts_success(
    services_container, test_user: User, test_external_user: FullExternalUser
):
    """Test external_import_accounts successfully imports accounts."""
    from src.external.wealthsimple import WealthsimpleApiWrapper

    # Mock the external API wrapper to return imported accounts
    external_api_wrapper = await services_container.aget(WealthsimpleApiWrapper)

    imported_accounts = [
        Account(
            id=uuid4(),
            external_id="ext_acc_1",
            name="Imported Account",
            user_id=test_user.id,
            account_type_id=1,
            institution_id=InstitutionEnum.WEALTHSIMPLE.value,
            currency="CAD",
            is_active=True,
            created_at=datetime.now(UTC),
            deleted_at=None,
        ),
    ]

    external_api_wrapper.import_accounts = AsyncMock(return_value=imported_accounts)

    import_request = ExternalImportAccountsRequest(
        external_user_id=test_external_user.id,
        external_account_ids=["ext_acc_1"],
    )

    result = await external_import_accounts(
        institution=InstitutionEnum.WEALTHSIMPLE,
        import_request=import_request,
        services=services_container,
        user=test_user,
    )

    assert result.imported_count == 1


@pytest.mark.asyncio
async def test_external_import_accounts_no_selection(
    services_container, test_user: User, test_external_user: FullExternalUser
):
    """Test external_import_accounts with no specific account selection."""
    from src.external.wealthsimple import WealthsimpleApiWrapper

    # Mock the external API wrapper to return all accounts
    external_api_wrapper = await services_container.aget(WealthsimpleApiWrapper)

    imported_accounts = [
        Account(
            id=uuid4(),
            external_id=f"ext_acc_{i}",
            name=f"Imported Account {i}",
            user_id=test_user.id,
            account_type_id=1,
            institution_id=InstitutionEnum.WEALTHSIMPLE.value,
            currency="CAD",
            is_active=True,
            created_at=datetime.now(UTC),
            deleted_at=None,
        )
        for i in range(2)
    ]

    external_api_wrapper.import_accounts = AsyncMock(return_value=imported_accounts)

    import_request = ExternalImportAccountsRequest(
        external_user_id=test_external_user.id,
        external_account_ids=[],
    )

    result = await external_import_accounts(
        institution=InstitutionEnum.WEALTHSIMPLE,
        import_request=import_request,
        services=services_container,
        user=test_user,
    )

    assert result.imported_count == 2


@pytest.mark.asyncio
async def test_external_import_accounts_not_owned(
    services_container, test_user: User, other_user_external_user: FullExternalUser
):
    """Test external_import_accounts raises 404 for non-owned external user."""
    import_request = ExternalImportAccountsRequest(
        external_user_id=other_user_external_user.id,
        external_account_ids=[],
    )

    with pytest.raises(HTTPException) as exc_info:
        await external_import_accounts(
            institution=InstitutionEnum.WEALTHSIMPLE,
            import_request=import_request,
            services=services_container,
            user=test_user,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_external_import_accounts_not_found(
    services_container, test_user: User, seed_reference_data
):
    """Test external_import_accounts raises 404 for non-existent external user."""
    fake_id = uuid4()
    import_request = ExternalImportAccountsRequest(
        external_user_id=fake_id,
        external_account_ids=[],
    )

    with pytest.raises(HTTPException) as exc_info:
        await external_import_accounts(
            institution=InstitutionEnum.WEALTHSIMPLE,
            import_request=import_request,
            services=services_container,
            user=test_user,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_external_import_positions_success(
    services_container,
    test_user: User,
    test_external_user: FullExternalUser,
    test_accounts: list[Account],
):
    """Test external_import_positions successfully imports positions."""
    from src.external.wealthsimple import WealthsimpleApiWrapper

    # Mock the external API wrapper to return imported positions
    external_api_wrapper = await services_container.aget(WealthsimpleApiWrapper)

    imported_positions = [
        Position(
            id=uuid4(),
            account_id=test_accounts[0].id,
            security_symbol="AAPL",
            quantity=10.0,
            average_cost=150.0,
            updated_at=datetime.now(UTC),
        ),
    ]

    external_api_wrapper.import_positions = AsyncMock(return_value=imported_positions)

    import_request = ExternalImportPositionsRequest(
        external_user_id=test_external_user.id,
        account_id=test_accounts[0].id,
    )

    result = await external_import_positions(
        institution=InstitutionEnum.WEALTHSIMPLE,
        import_request=import_request,
        services=services_container,
        user=test_user,
    )

    assert result.imported_count == 1


@pytest.mark.asyncio
async def test_external_import_positions_not_owned(
    services_container,
    test_user: User,
    other_user_external_user: FullExternalUser,
    test_accounts: list[Account],
):
    """Test external_import_positions raises 404 for non-owned external user."""
    import_request = ExternalImportPositionsRequest(
        external_user_id=other_user_external_user.id,
        account_id=test_accounts[0].id,
    )

    with pytest.raises(HTTPException) as exc_info:
        await external_import_positions(
            institution=InstitutionEnum.WEALTHSIMPLE,
            import_request=import_request,
            services=services_container,
            user=test_user,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_external_import_positions_external_user_not_found(
    services_container,
    test_user: User,
    test_accounts: list[Account],
    seed_reference_data,
):
    """Test external_import_positions raises 404 for non-existent external user."""
    fake_id = uuid4()
    import_request = ExternalImportPositionsRequest(
        external_user_id=fake_id,
        account_id=test_accounts[0].id,
    )

    with pytest.raises(HTTPException) as exc_info:
        await external_import_positions(
            institution=InstitutionEnum.WEALTHSIMPLE,
            import_request=import_request,
            services=services_container,
            user=test_user,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_external_import_positions_account_not_found(
    services_container,
    test_user: User,
    test_external_user: FullExternalUser,
    seed_reference_data,
):
    """Test external_import_positions raises 404 for non-existent account."""
    fake_account_id = uuid4()
    import_request = ExternalImportPositionsRequest(
        external_user_id=test_external_user.id,
        account_id=fake_account_id,
    )

    with pytest.raises(HTTPException) as exc_info:
        await external_import_positions(
            institution=InstitutionEnum.WEALTHSIMPLE,
            import_request=import_request,
            services=services_container,
            user=test_user,
        )

    assert exc_info.value.status_code == 404
