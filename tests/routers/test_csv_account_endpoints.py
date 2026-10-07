"""Integration tests for CSV account import and sync endpoints."""

import json
from decimal import Decimal
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.account.model import AccountModel, InstitutionModel, PositionModel
from src.auth.model import UserModel
from src.core.enum import AccountTypeEnum, InstitutionEnum
from src.main import app

WS_HEADER = (
    "Account Name,Account Type,Account Classification,Account Number,"
    "Symbol,Exchange,MIC,Name,Security Type,Quantity,Position Direction,"
    "Market Price,Market Price Currency,Book Value (CAD),Book Value Currency (CAD),"
    "Book Value,Currency,Market Value,Market Value Currency,"
    "Market Unrealized Returns,Market Unrealized Returns Currency"
)

VALID_CSV = (
    f"{WS_HEADER}\n"
    "My TFSA,Tax-Free Savings Account,Personal,W123456789,"
    "VGRO,TSX,XTSE,Vanguard Growth ETF Portfolio,Equity,100,LONG,"
    "32.50,CAD,3000.00,CAD,3000.00,CAD,3250.00,CAD,250.00,CAD\n"
    "My TFSA,Tax-Free Savings Account,Personal,W123456789,"
    "sec-c-cad,TSX,,Canadian Dollar,Cash,500.00,LONG,"
    "1.00,CAD,500.00,CAD,500.00,CAD,500.00,CAD,0.00,CAD\n"
    "My RRSP,Registered Retirement Savings Plan,Personal,W987654321,"
    "AAPL,NASDAQ,XNAS,Apple Inc.,Equity,50,LONG,"
    "150.00,USD,7500.00,USD,7500.00,USD,7500.00,USD,0.00,USD\n"
)

UPDATED_CSV = (
    f"{WS_HEADER}\n"
    "My TFSA,Tax-Free Savings Account,Personal,W123456789,"
    "MSFT,NASDAQ,XNAS,Microsoft Corp,Equity,75,LONG,"
    "300.00,USD,22500.00,USD,22500.00,USD,22500.00,USD,0.00,USD\n"
)


@pytest.mark.anyio
async def test_csv_import_unauthenticated():
    """Unauthenticated request to /csv/import returns HTTP 401."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        files = {"file": ("test.csv", VALID_CSV.encode("utf-8"), "text/csv")}
        response = await ac.post(
            "/api/v1/accounts/csv/import",
            files=files,
            data={
                "institution_id": str(InstitutionEnum.WEALTHSIMPLE.value),
                "account_numbers": "W123456789",
            },
        )
        assert response.status_code == 401


@pytest.mark.anyio
async def test_csv_sync_unauthenticated():
    """Unauthenticated request to /{account_id}/csv-sync returns HTTP 401."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        files = {"file": ("test.csv", VALID_CSV.encode("utf-8"), "text/csv")}
        response = await ac.post(
            f"/api/v1/accounts/{uuid4()}/csv-sync",
            files=files,
        )
        assert response.status_code == 401


@pytest.mark.anyio
async def test_csv_import_missing_institution_id(auth_client):
    """Missing institution_id returns HTTP 422."""
    files = {"file": ("test.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    response = await auth_client.post(
        "/api/v1/accounts/csv/import",
        files=files,
        data={"account_numbers": "W123456789"},
    )
    assert response.status_code == 422
    assert "institution_id is required" in response.json()["detail"]


@pytest.mark.anyio
async def test_csv_import_missing_account_numbers(auth_client):
    """Missing account_numbers returns HTTP 422."""
    files = {"file": ("test.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    response = await auth_client.post(
        "/api/v1/accounts/csv/import",
        files=files,
        data={"institution_id": str(InstitutionEnum.WEALTHSIMPLE.value)},
    )
    assert response.status_code == 422
    assert "account_numbers is required" in response.json()["detail"]


@pytest.mark.anyio
async def test_csv_import_disabled_institution(auth_client, db_session: AsyncSession):
    """Disabled institution returns HTTP 400 on import."""
    disabled_inst = InstitutionModel(
        id=888,
        name="Disabled Broker",
        country="CA",
        is_active=True,
        csv_import_enabled=False,
        csv_format=None,
    )
    db_session.add(disabled_inst)
    await db_session.commit()

    files = {"file": ("test.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    response = await auth_client.post(
        "/api/v1/accounts/csv/import",
        files=files,
        data={"institution_id": "888", "account_numbers": "W123456789"},
    )
    assert response.status_code == 400
    assert "CSV import is not enabled or configured" in response.json()["detail"]


@pytest.mark.anyio
async def test_csv_sync_disabled_institution(
    auth_client, test_user, db_session: AsyncSession, seed_reference_data: None
):
    """Account belonging to disabled institution returns HTTP 400 on sync."""
    account = AccountModel(
        id=uuid4(),
        external_id="W123456789",
        name="Disabled Inst Account",
        user_id=test_user.id,
        account_type_id=AccountTypeEnum.TFSA.value,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        currency="CAD",
        is_active=True,
        api_sync_enabled=False,
    )
    db_session.add(account)

    # Disable CSV import on Wealthsimple institution
    stmt = (
        update(InstitutionModel)
        .where(InstitutionModel.id == InstitutionEnum.WEALTHSIMPLE.value)
        .values(csv_import_enabled=False)
    )
    await db_session.execute(stmt)
    await db_session.commit()

    files = {"file": ("test.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    response = await auth_client.post(
        f"/api/v1/accounts/{account.id}/csv-sync",
        files=files,
    )
    assert response.status_code == 400
    assert "CSV import is not enabled or configured" in response.json()["detail"]


@pytest.mark.anyio
async def test_csv_import_empty_file(auth_client, seed_reference_data: None):
    """Empty file upload on import returns HTTP 400."""
    files = {"file": ("empty.csv", b"", "text/csv")}
    response = await auth_client.post(
        "/api/v1/accounts/csv/import",
        files=files,
        data={
            "institution_id": str(InstitutionEnum.WEALTHSIMPLE.value),
            "account_numbers": "W123456789",
        },
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


@pytest.mark.anyio
async def test_csv_sync_empty_file(
    auth_client, test_user, db_session: AsyncSession, seed_reference_data: None
):
    """Empty file upload on sync returns HTTP 400."""
    account = AccountModel(
        id=uuid4(),
        external_id="W123456789",
        name="Test Account",
        user_id=test_user.id,
        account_type_id=AccountTypeEnum.TFSA.value,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        currency="CAD",
        is_active=True,
        api_sync_enabled=False,
    )
    db_session.add(account)
    await db_session.commit()

    files = {"file": ("empty.csv", b"", "text/csv")}
    response = await auth_client.post(
        f"/api/v1/accounts/{account.id}/csv-sync",
        files=files,
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


@pytest.mark.anyio
async def test_csv_import_invalid_headers(auth_client, seed_reference_data: None):
    """Invalid headers on import returns HTTP 400."""
    invalid_csv = "Col1,Col2\nval1,val2"
    files = {"file": ("invalid.csv", invalid_csv.encode("utf-8"), "text/csv")}
    response = await auth_client.post(
        "/api/v1/accounts/csv/import",
        files=files,
        data={
            "institution_id": str(InstitutionEnum.WEALTHSIMPLE.value),
            "account_numbers": "W123456789",
        },
    )
    assert response.status_code == 400
    assert "mismatch" in response.json()["detail"].lower()


@pytest.mark.anyio
async def test_csv_sync_invalid_headers(
    auth_client, test_user, db_session: AsyncSession, seed_reference_data: None
):
    """Invalid headers on sync returns HTTP 400."""
    account = AccountModel(
        id=uuid4(),
        external_id="W123456789",
        name="Test Account",
        user_id=test_user.id,
        account_type_id=AccountTypeEnum.TFSA.value,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        currency="CAD",
        is_active=True,
        api_sync_enabled=False,
    )
    db_session.add(account)
    await db_session.commit()

    invalid_csv = "Col1,Col2\nval1,val2"
    files = {"file": ("invalid.csv", invalid_csv.encode("utf-8"), "text/csv")}
    response = await auth_client.post(
        f"/api/v1/accounts/{account.id}/csv-sync",
        files=files,
    )
    assert response.status_code == 400
    assert "mismatch" in response.json()["detail"].lower()


@pytest.mark.anyio
async def test_csv_import_existing_account_updates_positions(auth_client, seed_reference_data: None):
    """Importing an already existing account number updates its positions and returns HTTP 200."""
    files = {"file": ("ws.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    res1 = await auth_client.post(
        "/api/v1/accounts/csv/import",
        files=files,
        data={
            "institution_id": str(InstitutionEnum.WEALTHSIMPLE.value),
            "account_numbers": "W123456789",
        },
    )
    assert res1.status_code == 200
    acc_id = res1.json()[0]["id"]

    # Second attempt to import the same account number updates the existing account
    files2 = {"file": ("ws.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    res2 = await auth_client.post(
        "/api/v1/accounts/csv/import",
        files=files2,
        data={
            "institution_id": str(InstitutionEnum.WEALTHSIMPLE.value),
            "account_numbers": "W123456789",
        },
    )
    assert res2.status_code == 200
    assert res2.json()[0]["id"] == acc_id


@pytest.mark.anyio
async def test_csv_import_success(
    auth_client, db_session: AsyncSession, seed_reference_data: None
):
    """Criterion 1 & 4: Successful CSV import creates accounts and positions."""
    files = {"file": ("ws.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    response = await auth_client.post(
        "/api/v1/accounts/csv/import",
        files=files,
        data={
            "institution_id": str(InstitutionEnum.WEALTHSIMPLE.value),
            "account_numbers": ["W123456789", "W987654321"],
        },
    )
    assert response.status_code == 200
    accounts = response.json()
    assert len(accounts) == 2

    # Verify attributes of created accounts
    for acc in accounts:
        assert acc["api_sync_enabled"] is False
        assert acc["integration_user_id"] is None
        assert acc["last_sync_at"] is not None

    tfsa_acc = next(a for a in accounts if a["external_id"] == "W123456789")
    rrsp_acc = next(a for a in accounts if a["external_id"] == "W987654321")

    # Verify positions in database
    tfsa_positions_res = await db_session.execute(
        select(PositionModel).where(PositionModel.account_id == tfsa_acc["id"])
    )
    tfsa_positions = tfsa_positions_res.scalars().all()
    assert len(tfsa_positions) == 1
    assert tfsa_positions[0].quantity == Decimal("100")
    assert tfsa_positions[0].average_cost == 30.0

    rrsp_positions_res = await db_session.execute(
        select(PositionModel).where(PositionModel.account_id == rrsp_acc["id"])
    )
    rrsp_positions = rrsp_positions_res.scalars().all()
    assert len(rrsp_positions) == 1
    assert rrsp_positions[0].quantity == Decimal("50")


@pytest.mark.anyio
async def test_csv_sync_replaces_positions_success(
    auth_client, db_session: AsyncSession, seed_reference_data: None
):
    """Criterion 2 & 4: /csv-sync replaces positions and updates last_sync_at."""
    # First import account W123456789
    files1 = {"file": ("ws.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    res_import = await auth_client.post(
        "/api/v1/accounts/csv/import",
        files=files1,
        data={
            "institution_id": str(InstitutionEnum.WEALTHSIMPLE.value),
            "account_numbers": "W123456789",
        },
    )
    assert res_import.status_code == 200
    imported_acc = res_import.json()[0]
    account_id = imported_acc["id"]
    initial_sync_at = imported_acc["last_sync_at"]
    assert initial_sync_at is not None

    # Check initial position before sync
    pos_res = await db_session.execute(
        select(PositionModel).where(PositionModel.account_id == account_id)
    )
    assert len(pos_res.scalars().all()) == 1

    # Now perform csv-sync with UPDATED_CSV (which has MSFT 75 qty)
    files2 = {"file": ("ws_updated.csv", UPDATED_CSV.encode("utf-8"), "text/csv")}
    res_sync = await auth_client.post(
        f"/api/v1/accounts/{account_id}/csv-sync",
        files=files2,
    )
    assert res_sync.status_code == 200
    synced_acc = res_sync.json()
    assert synced_acc["id"] == account_id
    assert synced_acc["last_sync_at"] is not None

    # Check positions in database after sync: old position replaced with new one
    pos_after_res = await db_session.execute(
        select(PositionModel).where(PositionModel.account_id == account_id)
    )
    positions_after = pos_after_res.scalars().all()
    assert len(positions_after) == 1
    assert positions_after[0].quantity == Decimal("75")


@pytest.mark.anyio
async def test_csv_sync_no_matching_external_id(
    auth_client, test_user, db_session: AsyncSession, seed_reference_data: None
):
    """Criterion 3: Sync returns HTTP 400 when CSV has no row matching external_id."""
    account = AccountModel(
        id=uuid4(),
        external_id="NO_SUCH_EXTERNAL_ID",
        name="Unmatched Account",
        user_id=test_user.id,
        account_type_id=AccountTypeEnum.TFSA.value,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        currency="CAD",
        is_active=True,
        api_sync_enabled=False,
    )
    db_session.add(account)
    await db_session.commit()

    files = {"file": ("ws.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    response = await auth_client.post(
        f"/api/v1/accounts/{account.id}/csv-sync",
        files=files,
    )
    assert response.status_code == 400
    assert (
        "No account matching 'NO_SUCH_EXTERNAL_ID' found in CSV"
        in response.json()["detail"]
    )


@pytest.mark.anyio
async def test_csv_sync_not_owned_by_user(
    auth_client, db_session: AsyncSession, seed_reference_data: None
):
    """Account belonging to another user returns HTTP 404."""
    other_user = UserModel(
        id=uuid4(),
        email="other@example.com",
        password="hash",
        is_active=True,
        is_verified=True,
    )
    db_session.add(other_user)
    await db_session.flush()

    other_account = AccountModel(
        id=uuid4(),
        external_id="W123456789",
        name="Other Account",
        user_id=other_user.id,
        account_type_id=AccountTypeEnum.TFSA.value,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        currency="CAD",
        is_active=True,
        api_sync_enabled=False,
    )
    db_session.add(other_account)
    await db_session.commit()

    files = {"file": ("ws.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    response = await auth_client.post(
        f"/api/v1/accounts/{other_account.id}/csv-sync",
        files=files,
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_csv_sync_account_not_found(auth_client, seed_reference_data: None):
    """Non-existent account_id returns HTTP 404."""
    files = {"file": ("ws.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    response = await auth_client.post(
        f"/api/v1/accounts/{uuid4()}/csv-sync",
        files=files,
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_csv_import_with_currencies(
    auth_client, seed_reference_data: None
):
    """Import with explicit currencies parameter creates account with selected currency."""
    files = {"file": ("ws.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    response = await auth_client.post(
        "/api/v1/accounts/csv/import",
        files=files,
        data={
            "institution_id": str(InstitutionEnum.WEALTHSIMPLE.value),
            "account_numbers": "W123456789",
            "currencies": json.dumps({"W123456789": "USD"}),
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["currency"] == "USD"


async def _get_db_account(db_session: AsyncSession, account_id: str) -> AccountModel:
    result = await db_session.execute(
        select(AccountModel).where(AccountModel.id == account_id)
    )
    return result.scalar_one()


@pytest.mark.anyio
async def test_csv_import_with_net_deposits_new_account(
    auth_client, db_session: AsyncSession, seed_reference_data: None
):
    """Import stores provided net deposits for a newly created account."""
    files = {"file": ("ws.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    response = await auth_client.post(
        "/api/v1/accounts/csv/import",
        files=files,
        data={
            "institution_id": str(InstitutionEnum.WEALTHSIMPLE.value),
            "account_numbers": "W123456789",
            "net_deposits": json.dumps({"W123456789": 1500}),
        },
    )
    assert response.status_code == 200
    account = response.json()[0]
    assert account["net_deposits"] == 1500.0

    db_account = await _get_db_account(db_session, account["id"])
    assert db_account.net_deposits == Decimal("1500")


@pytest.mark.anyio
async def test_csv_import_with_net_deposits_existing_account(
    auth_client, db_session: AsyncSession, seed_reference_data: None
):
    """Import overwrites stored net deposits for an existing account."""
    files = {"file": ("ws.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    base_data = {
        "institution_id": str(InstitutionEnum.WEALTHSIMPLE.value),
        "account_numbers": "W123456789",
    }
    first = await auth_client.post(
        "/api/v1/accounts/csv/import",
        files=files,
        data={**base_data, "net_deposits": json.dumps({"W123456789": 1000})},
    )
    assert first.status_code == 200
    account_id = first.json()[0]["id"]

    second = await auth_client.post(
        "/api/v1/accounts/csv/import",
        files=files,
        data={**base_data, "net_deposits": json.dumps({"W123456789": 2500})},
    )
    assert second.status_code == 200
    assert second.json()[0]["id"] == account_id
    assert second.json()[0]["net_deposits"] == 2500.0

    db_account = await _get_db_account(db_session, account_id)
    assert db_account.net_deposits == Decimal("2500")


@pytest.mark.anyio
async def test_csv_import_without_net_deposits_leaves_value_null(
    auth_client, db_session: AsyncSession, seed_reference_data: None
):
    """Import without the field leaves a new account's value NULL."""
    files = {"file": ("ws.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    response = await auth_client.post(
        "/api/v1/accounts/csv/import",
        files=files,
        data={
            "institution_id": str(InstitutionEnum.WEALTHSIMPLE.value),
            "account_numbers": "W123456789",
        },
    )
    assert response.status_code == 200
    account = response.json()[0]
    assert account["net_deposits"] is None

    db_account = await _get_db_account(db_session, account["id"])
    assert db_account.net_deposits is None


@pytest.mark.anyio
async def test_csv_import_with_null_net_deposits_clears_value(
    auth_client, db_session: AsyncSession, seed_reference_data: None
):
    """Passing null clears the stored net deposits value."""
    files = {"file": ("ws.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    base_data = {
        "institution_id": str(InstitutionEnum.WEALTHSIMPLE.value),
        "account_numbers": "W123456789",
    }
    first = await auth_client.post(
        "/api/v1/accounts/csv/import",
        files=files,
        data={**base_data, "net_deposits": json.dumps({"W123456789": 1000})},
    )
    assert first.status_code == 200
    account_id = first.json()[0]["id"]

    cleared = await auth_client.post(
        "/api/v1/accounts/csv/import",
        files=files,
        data={**base_data, "net_deposits": json.dumps({"W123456789": None})},
    )
    assert cleared.status_code == 200
    assert cleared.json()[0]["net_deposits"] is None

    db_account = await _get_db_account(db_session, account_id)
    assert db_account.net_deposits is None


@pytest.mark.anyio
async def test_csv_import_malformed_net_deposits_returns_422(
    auth_client, seed_reference_data: None
):
    """Malformed net_deposits JSON returns HTTP 422."""
    files = {"file": ("ws.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    response = await auth_client.post(
        "/api/v1/accounts/csv/import",
        files=files,
        data={
            "institution_id": str(InstitutionEnum.WEALTHSIMPLE.value),
            "account_numbers": "W123456789",
            "net_deposits": "{not-valid-json",
        },
    )
    assert response.status_code == 422
    assert "net_deposits" in response.json()["detail"]


@pytest.mark.anyio
async def test_csv_import_non_numeric_net_deposits_returns_422(
    auth_client, seed_reference_data: None
):
    """Non-numeric net_deposits values return HTTP 422."""
    files = {"file": ("ws.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    response = await auth_client.post(
        "/api/v1/accounts/csv/import",
        files=files,
        data={
            "institution_id": str(InstitutionEnum.WEALTHSIMPLE.value),
            "account_numbers": "W123456789",
            "net_deposits": json.dumps({"W123456789": "not-a-number"}),
        },
    )
    assert response.status_code == 422
    assert "net_deposits" in response.json()["detail"]


@pytest.mark.anyio
async def test_csv_import_non_object_net_deposits_returns_422(
    auth_client, seed_reference_data: None
):
    """net_deposits that is valid JSON but not an object returns HTTP 422."""
    files = {"file": ("ws.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    response = await auth_client.post(
        "/api/v1/accounts/csv/import",
        files=files,
        data={
            "institution_id": str(InstitutionEnum.WEALTHSIMPLE.value),
            "account_numbers": "W123456789",
            "net_deposits": json.dumps([1, 2, 3]),
        },
    )
    assert response.status_code == 422
    assert "net_deposits" in response.json()["detail"]


@pytest.mark.anyio
async def test_csv_inspect_prefills_net_deposits(
    auth_client, seed_reference_data: None
):
    """Inspect returns the stored net deposits for existing accounts only."""
    files = {"file": ("ws.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    imported = await auth_client.post(
        "/api/v1/accounts/csv/import",
        files=files,
        data={
            "institution_id": str(InstitutionEnum.WEALTHSIMPLE.value),
            "account_numbers": "W123456789",
            "net_deposits": json.dumps({"W123456789": 1000}),
        },
    )
    assert imported.status_code == 200

    inspect = await auth_client.post(
        "/api/v1/accounts/csv/inspect",
        files={"file": ("ws.csv", VALID_CSV.encode("utf-8"), "text/csv")},
        data={"institution_id": str(InstitutionEnum.WEALTHSIMPLE.value)},
    )
    assert inspect.status_code == 200
    accounts = {acc["account_number"]: acc for acc in inspect.json()}
    assert accounts["W123456789"]["exists"] is True
    assert accounts["W123456789"]["net_deposits"] == 1000.0
    assert accounts["W987654321"]["exists"] is False
    assert accounts["W987654321"]["net_deposits"] is None


@pytest.mark.anyio
async def test_csv_sync_with_net_deposits(
    auth_client, db_session: AsyncSession, seed_reference_data: None
):
    """csv-sync persists the provided net deposits value."""
    files = {"file": ("ws.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    imported = await auth_client.post(
        "/api/v1/accounts/csv/import",
        files=files,
        data={
            "institution_id": str(InstitutionEnum.WEALTHSIMPLE.value),
            "account_numbers": "W123456789",
        },
    )
    assert imported.status_code == 200
    account_id = imported.json()[0]["id"]

    sync = await auth_client.post(
        f"/api/v1/accounts/{account_id}/csv-sync",
        files={"file": ("ws.csv", UPDATED_CSV.encode("utf-8"), "text/csv")},
        data={"net_deposits": "2000"},
    )
    assert sync.status_code == 200
    assert sync.json()["net_deposits"] == 2000.0

    db_account = await _get_db_account(db_session, account_id)
    assert db_account.net_deposits == Decimal("2000")


@pytest.mark.anyio
async def test_csv_sync_without_net_deposits_leaves_value_unchanged(
    auth_client, db_session: AsyncSession, seed_reference_data: None
):
    """csv-sync without the field leaves the stored net deposits unchanged."""
    files = {"file": ("ws.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    imported = await auth_client.post(
        "/api/v1/accounts/csv/import",
        files=files,
        data={
            "institution_id": str(InstitutionEnum.WEALTHSIMPLE.value),
            "account_numbers": "W123456789",
            "net_deposits": json.dumps({"W123456789": 1000}),
        },
    )
    assert imported.status_code == 200
    account_id = imported.json()[0]["id"]

    sync = await auth_client.post(
        f"/api/v1/accounts/{account_id}/csv-sync",
        files={"file": ("ws.csv", UPDATED_CSV.encode("utf-8"), "text/csv")},
    )
    assert sync.status_code == 200
    assert sync.json()["net_deposits"] == 1000.0

    db_account = await _get_db_account(db_session, account_id)
    assert db_account.net_deposits == Decimal("1000")


@pytest.mark.anyio
async def test_csv_sync_invalid_net_deposits_returns_422(
    auth_client, test_user, db_session: AsyncSession, seed_reference_data: None
):
    """A non-numeric csv-sync net_deposits value returns HTTP 422."""
    account = AccountModel(
        id=uuid4(),
        external_id="W123456789",
        name="Test Account",
        user_id=test_user.id,
        account_type_id=AccountTypeEnum.TFSA.value,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        currency="CAD",
        is_active=True,
        api_sync_enabled=False,
    )
    db_session.add(account)
    await db_session.commit()

    response = await auth_client.post(
        f"/api/v1/accounts/{account.id}/csv-sync",
        files={"file": ("ws.csv", VALID_CSV.encode("utf-8"), "text/csv")},
        data={"net_deposits": "not-a-number"},
    )
    assert response.status_code == 422
