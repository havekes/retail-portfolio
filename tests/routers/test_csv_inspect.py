"""Integration tests for POST /api/v1/accounts/csv/inspect."""

from decimal import Decimal
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.account.model import InstitutionModel
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


@pytest.mark.anyio
async def test_csv_inspect_unauthenticated():
    """Unauthenticated request returns HTTP 401."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        files = {"file": ("test.csv", b"dummy", "text/csv")}
        response = await ac.post(
            "/api/v1/accounts/csv/inspect",
            files=files,
            data={"institution_id": str(InstitutionEnum.WEALTHSIMPLE.value)},
        )
        assert response.status_code == 401


@pytest.mark.anyio
async def test_csv_inspect_institution_not_found(auth_client):
    """Non-existent institution_id returns HTTP 404."""
    files = {"file": ("test.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    response = await auth_client.post(
        "/api/v1/accounts/csv/inspect",
        files=files,
        data={"institution_id": "99999"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Institution 99999 not found"


@pytest.mark.anyio
async def test_csv_inspect_csv_import_disabled(
    auth_client, db_session: AsyncSession
):
    """Institution with csv_import_enabled=False returns HTTP 400."""
    disabled_inst = InstitutionModel(
        id=888,
        name="No CSV Broker",
        country="CA",
        is_active=True,
        csv_import_enabled=False,
        csv_format=None,
    )
    db_session.add(disabled_inst)
    await db_session.commit()

    files = {"file": ("test.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    response = await auth_client.post(
        "/api/v1/accounts/csv/inspect",
        files=files,
        data={"institution_id": "888"},
    )
    assert response.status_code == 400
    assert (
        "CSV import is not enabled or configured" in response.json()["detail"]
    )


@pytest.mark.anyio
async def test_csv_inspect_csv_format_missing(
    auth_client, db_session: AsyncSession
):
    """Institution with csv_import_enabled=True but csv_format=None returns HTTP 400."""
    no_format_inst = InstitutionModel(
        id=889,
        name="No Format Broker",
        country="CA",
        is_active=True,
        csv_import_enabled=True,
        csv_format=None,
    )
    db_session.add(no_format_inst)
    await db_session.commit()

    files = {"file": ("test.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    response = await auth_client.post(
        "/api/v1/accounts/csv/inspect",
        files=files,
        data={"institution_id": "889"},
    )
    assert response.status_code == 400
    assert (
        "CSV import is not enabled or configured" in response.json()["detail"]
    )


@pytest.mark.anyio
async def test_csv_inspect_empty_file(auth_client, seed_reference_data: None):
    """Empty file upload returns HTTP 400."""
    files = {"file": ("empty.csv", b"", "text/csv")}
    response = await auth_client.post(
        "/api/v1/accounts/csv/inspect",
        files=files,
        data={"institution_id": str(InstitutionEnum.WEALTHSIMPLE.value)},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


@pytest.mark.anyio
async def test_csv_inspect_invalid_headers(
    auth_client, seed_reference_data: None
):
    """Invalid header CSV returns HTTP 400 with descriptive error message."""
    invalid_csv = "Invalid Header 1,Invalid Header 2\nval1,val2"
    files = {"file": ("invalid.csv", invalid_csv.encode("utf-8"), "text/csv")}
    response = await auth_client.post(
        "/api/v1/accounts/csv/inspect",
        files=files,
        data={"institution_id": str(InstitutionEnum.WEALTHSIMPLE.value)},
    )
    assert response.status_code == 400
    assert "mismatch" in response.json()["detail"].lower()


@pytest.mark.anyio
async def test_csv_inspect_valid_wealthsimple_csv(
    auth_client, seed_reference_data: None
):
    """Valid Wealthsimple CSV returns discovered accounts with preview positions."""
    files = {"file": ("wealthsimple.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    response = await auth_client.post(
        "/api/v1/accounts/csv/inspect",
        files=files,
        data={"institution_id": str(InstitutionEnum.WEALTHSIMPLE.value)},
    )

    assert response.status_code == 200
    accounts = response.json()
    assert len(accounts) == 2

    # TFSA Account
    tfsa = accounts[0]
    assert tfsa["account_number"] == "W123456789"
    assert tfsa["account_name"] == "My TFSA"
    assert tfsa["account_type_id"] == AccountTypeEnum.TFSA.value
    assert tfsa["account_type_name"] == "TFSA"
    assert tfsa["currency"] == "CAD"
    assert tfsa["positions_count"] == 1  # cash position sec-c-cad filtered out
    assert len(tfsa["positions"]) == 1
    pos1 = tfsa["positions"][0]
    assert pos1["symbol"] == "VGRO"
    assert pos1["exchange"] == "TSX"
    assert pos1["name"] == "Vanguard Growth ETF Portfolio"
    assert pos1["quantity"] == "100" or pos1["quantity"] == 100.0 or Decimal(str(pos1["quantity"])) == Decimal("100")
    assert pos1["average_cost"] == "30.0000" or Decimal(str(pos1["average_cost"])) == Decimal("30.0000")
    assert pos1["currency"] == "CAD"

    # RRSP Account
    rrsp = accounts[1]
    assert rrsp["account_number"] == "W987654321"
    assert rrsp["account_name"] == "My RRSP"
    assert rrsp["account_type_id"] == AccountTypeEnum.RRSP.value
    assert rrsp["account_type_name"] == "RRSP"
    assert rrsp["currency"] == "USD"
    assert rrsp["positions_count"] == 1
    assert len(rrsp["positions"]) == 1
    pos2 = rrsp["positions"][0]
    assert pos2["symbol"] == "AAPL"
    assert pos2["exchange"] == "NASDAQ"
    assert pos2["name"] == "Apple Inc."
    assert Decimal(str(pos2["quantity"])) == Decimal("50")
    assert Decimal(str(pos2["average_cost"])) == Decimal("150.0000")
    assert pos2["currency"] == "USD"


@pytest.mark.anyio
async def test_csv_inspect_query_parameter_fallback(
    auth_client, seed_reference_data: None
):
    """Verify institution_id passed via query parameters works as fallback."""
    files = {"file": ("wealthsimple.csv", VALID_CSV.encode("utf-8"), "text/csv")}
    response = await auth_client.post(
        f"/api/v1/accounts/csv/inspect?institution_id={InstitutionEnum.WEALTHSIMPLE.value}",
        files=files,
    )
    assert response.status_code == 200
    assert len(response.json()) == 2
