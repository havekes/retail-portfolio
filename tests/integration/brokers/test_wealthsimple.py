"""Integration tests for WealthsimpleApiGateway."""

import json
import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from ws_api.exceptions import (
    LoginFailedException,
    ManualLoginRequired,
    OTPRequiredException,
    UnexpectedException,
)

from src.account.enum import AccountTypeEnum, InstitutionEnum
from src.integration.brokers.api_types import BrokerAccount, BrokerPosition
from src.integration.brokers.exception import (
    AccountTypeUnkownError,
    LoginFailedError,
    OTPRequiredError,
    SessionDoesNotExistError,
    SessionExpiredError,
    UnknownError,
)
from src.integration.brokers.wealthsimple import (
    WealthsimpleApiGateway,
    wealthsimple_api_wrapper_factory,
)
from src.integration.schema import IntegrationUserSchema
from src.stubs.wealthsimple import StubWealthsimpleAPI, StubWSAPISession


@pytest.fixture
def gateway() -> WealthsimpleApiGateway:
    """Fixture providing a fresh WealthsimpleApiGateway instance."""
    return WealthsimpleApiGateway()


@pytest.fixture
def dummy_user() -> IntegrationUserSchema:
    """Fixture providing a test user schema."""
    return IntegrationUserSchema(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        external_user_id="user@example.com",
        display_name="Test User",
    )


def test_save_session(gateway: WealthsimpleApiGateway) -> None:
    """Test saving session token to keyring."""
    with patch("keyring.set_password") as mock_set_pw:
        gateway._save_session("dummy_session_data", "user@example.com")
        mock_set_pw.assert_called_once_with(
            "retail_prtofolio_wealthsimple.user@example.com",
            "session",
            "dummy_session_data",
        )


def test_get_session_success(gateway: WealthsimpleApiGateway) -> None:
    """Test getting cached session token from keyring."""
    stub_session = StubWSAPISession()
    stub_session.access_token = "token123"
    json_str = stub_session.to_json()

    with patch("keyring.get_password", return_value=json_str):
        session = gateway._get_session("user@example.com")
        assert session.access_token == "token123"


def test_get_session_not_found(gateway: WealthsimpleApiGateway) -> None:
    """Test getting session when none exists in keyring."""
    with patch("keyring.get_password", return_value=None):
        with pytest.raises(SessionDoesNotExistError):
            gateway._get_session("user@example.com")


def test_login_cached_session_valid(gateway: WealthsimpleApiGateway) -> None:
    """Test login when valid cached session exists."""
    stub_session = StubWSAPISession()
    json_str = stub_session.to_json()

    mock_client = MagicMock()
    mock_client.get_accounts.return_value = []

    with (
        patch("keyring.get_password", return_value=json_str),
        patch.object(gateway, "_get_client", return_value=mock_client),
    ):
        result = gateway.login("user@example.com")
        assert result is True
        mock_client.get_accounts.assert_called_once()


def test_login_no_session_no_password(gateway: WealthsimpleApiGateway) -> None:
    """Test login fails when no session cached and no password provided."""
    with patch("keyring.get_password", return_value=None):
        with pytest.raises(LoginFailedError):
            gateway.login("user@example.com", password=None)


def test_login_no_session_successful_credentials(gateway: WealthsimpleApiGateway) -> None:
    """Test login succeeds with credentials when no session exists."""
    stub_session = StubWSAPISession()

    with (
        patch("keyring.get_password", return_value=None),
        patch.object(gateway, "_ws_login", return_value=stub_session) as mock_ws_login,
    ):
        result = gateway.login("user@example.com", password="password123", otp="123456")
        assert result is True
        mock_ws_login.assert_called_once_with("user@example.com", "password123", "123456")


@pytest.mark.parametrize(
    ("ws_exception", "expected_exception"),
    [
        (LoginFailedException("Failed"), LoginFailedError),
        (OTPRequiredException("OTP needed"), OTPRequiredError),
        (ManualLoginRequired("Manual required"), SessionExpiredError),
    ],
)
def test_login_credentials_exceptions(
    gateway: WealthsimpleApiGateway,
    ws_exception: Exception,
    expected_exception: type[Exception],
) -> None:
    """Test exception translation during login with credentials."""
    with (
        patch("keyring.get_password", return_value=None),
        patch.object(gateway, "_ws_login", side_effect=ws_exception),
    ):
        with pytest.raises(expected_exception):
            gateway.login("user@example.com", password="wrongpassword")


def test_ws_login_internal_call(gateway: WealthsimpleApiGateway) -> None:
    """Test _ws_login invokes WealthsimpleAPI.login_internal and wraps send_get."""
    mock_ws = MagicMock()
    stub_session = StubWSAPISession()
    mock_ws.login_internal.return_value = stub_session
    mock_ws.send_get.return_value = "response_data"

    with patch("src.integration.brokers.wealthsimple.WealthsimpleAPI", return_value=mock_ws):
        session = gateway._ws_login("user@example.com", "secret", "654321")

        assert session == stub_session
        mock_ws.login_internal.assert_called_once_with(
            "user@example.com",
            "secret",
            "654321",
            persist_session_fct=gateway._save_session,
        )

        # Verify send_get wrapper behavior
        resp = mock_ws.send_get("http://example.com")
        assert resp == "response_data"
        assert getattr(mock_ws, "_last_response") == "response_data"


def test_ws_login_unexpected_exception(gateway: WealthsimpleApiGateway) -> None:
    """Test _ws_login re-raises UnexpectedException."""
    mock_ws = MagicMock()
    mock_ws.login_internal.side_effect = UnexpectedException("API Error")

    with patch("src.integration.brokers.wealthsimple.WealthsimpleAPI", return_value=mock_ws):
        with pytest.raises(UnexpectedException):
            gateway._ws_login("user@example.com", "secret", None)


@pytest.mark.asyncio
async def test_get_accounts(
    gateway: WealthsimpleApiGateway,
    dummy_user: IntegrationUserSchema,
) -> None:
    """Test get_accounts returns parsed open accounts."""
    stub_api = StubWealthsimpleAPI()
    with patch.object(gateway, "_get_client", return_value=stub_api):
        accounts = await gateway.get_accounts(dummy_user)

        # Stub provides 2 open accounts and 1 closed account
        assert len(accounts) == 2

        tfsa_acc = accounts[0]
        assert tfsa_acc.id == "acc-tfsa-001"
        assert tfsa_acc.type == AccountTypeEnum.TFSA
        assert tfsa_acc.institution == InstitutionEnum.WEALTHSIMPLE
        assert tfsa_acc.currency == "CAD"
        assert tfsa_acc.broker_display_name == "Test User"
        assert tfsa_acc.value == Decimal("25000.50")
        assert tfsa_acc.net_deposits is None


@pytest.mark.asyncio
async def test_get_accounts_with_debug_options(
    gateway: WealthsimpleApiGateway,
    dummy_user: IntegrationUserSchema,
    tmp_path,
) -> None:
    """Test get_accounts with debug logging and dump path enabled."""
    stub_api = StubWealthsimpleAPI()
    dump_file = tmp_path / "accounts_dump.json"

    gateway.debug_api_responses = True
    gateway.debug_dump_path = str(dump_file)

    with patch.object(gateway, "_get_client", return_value=stub_api):
        accounts = await gateway.get_accounts(dummy_user)
        assert len(accounts) == 2
        assert dump_file.exists()

        content = json.loads(dump_file.read_text())
        assert isinstance(content, list)
        assert len(content) == 2


def test_parse_account_net_deposits(gateway: WealthsimpleApiGateway) -> None:
    """Test _parse_account correctly parses optional net_deposits field."""
    raw_account = {
        "id": "acc-fhsa-001",
        "status": "open",
        "unifiedAccountType": "SELF_DIRECTED_FHSA",
        "currency": "CAD",
        "createdAt": "2024-01-15T10:30:00.000Z",
        "custodianAccounts": [
            {
                "id": "cust-fhsa-001",
                "financials": {
                    "current": {"netLiquidationValue": {"amount": 10000.00}}
                },
            }
        ],
        "financials": {
            "currentCombined": {
                "netDeposits": {"amount": 8000.00}
            }
        },
    }

    parsed = gateway._parse_account(raw_account, "Display Name")
    assert parsed is not None
    assert parsed.type == AccountTypeEnum.FHSA
    assert parsed.value == Decimal("10000.00")
    assert parsed.net_deposits == Decimal("8000.00")


def test_parse_account_unknown_type(gateway: WealthsimpleApiGateway) -> None:
    """Test _parse_account returns None when account type is unknown."""
    raw_account = {
        "id": "acc-unknown",
        "status": "open",
        "unifiedAccountType": "UNKNOWN_ACCOUNT_TYPE",
        "currency": "CAD",
        "createdAt": "2024-01-15T10:30:00.000Z",
        "custodianAccounts": [
            {
                "id": "cust-unknown",
                "financials": {
                    "current": {"netLiquidationValue": {"amount": 100.00}}
                },
            }
        ],
    }

    parsed = gateway._parse_account(raw_account)
    assert parsed is None


@pytest.mark.asyncio
async def test_get_positions_by_account(
    gateway: WealthsimpleApiGateway,
    dummy_user: IntegrationUserSchema,
) -> None:
    """Test get_positions_by_account parses and returns positions."""
    stub_api = StubWealthsimpleAPI()
    with patch.object(gateway, "_get_client", return_value=stub_api):
        positions = await gateway.get_positions_by_account(dummy_user, "acc-tfsa-001")

        # Stub balance has sec-tsx-xyr, sec-us-nflx, sec-us-aapl, sec-c-cad (cash skipped)
        assert len(positions) == 3

        symbols = [p.symbol for p in positions]
        assert "XYR" in symbols
        assert "NFLX" in symbols
        assert "AAPL" in symbols

        nflx = next(p for p in positions if p.symbol == "NFLX")
        assert nflx.exchange == "NASDAQ"
        assert nflx.currency == "USD"
        assert nflx.quantity == Decimal("25.0")
        assert nflx.average_cost == Decimal("450.0")

        xyr = next(p for p in positions if p.symbol == "XYR")
        assert xyr.exchange == "TSX"
        assert xyr.currency == "CAD"
        assert xyr.quantity == Decimal("100.0")


@pytest.mark.asyncio
async def test_get_positions_by_account_with_debug_options(
    gateway: WealthsimpleApiGateway,
    dummy_user: IntegrationUserSchema,
    tmp_path,
) -> None:
    """Test get_positions_by_account with debug logging and dump path enabled."""
    stub_api = StubWealthsimpleAPI()
    dump_file = tmp_path / "positions_dump.json"

    gateway.debug_api_responses = True
    gateway.debug_dump_path = str(dump_file)

    with patch.object(gateway, "_get_client", return_value=stub_api):
        positions = await gateway.get_positions_by_account(dummy_user, "acc-tfsa-001")
        assert len(positions) == 3
        assert dump_file.exists()


def test_parse_position_malformed_market_data(gateway: WealthsimpleApiGateway) -> None:
    """Test _parse_position raises UnknownError on malformed market data response."""
    mock_client = MagicMock()
    mock_client.get_security_market_data.return_value = "invalid_response_type"

    with pytest.raises(UnknownError):
        gateway._parse_position(
            ws_client=mock_client,
            broker_account_id="acc-tfsa-001",
            security_id="[sec-test]",
            ws_balance=10.0,
        )


def test_parse_position_unsupported_primary_exchange(gateway: WealthsimpleApiGateway) -> None:
    """Test _parse_position returns None when primaryExchange is None."""
    mock_client = MagicMock()
    mock_client.get_security_market_data.return_value = {
        "stock": {
            "symbol": "UNSUP",
            "name": "Unsupported Security",
            "primaryExchange": None,
        }
    }

    pos, raw = gateway._parse_position(
        ws_client=mock_client,
        broker_account_id="acc-tfsa-001",
        security_id="[sec-unsupported]",
        ws_balance=10.0,
    )
    assert pos is None
    assert raw is None


def test_parse_position_malformed_identity_positions(gateway: WealthsimpleApiGateway) -> None:
    """Test _parse_position raises UnknownError on malformed identity positions response."""
    mock_client = MagicMock()
    mock_client.get_security_market_data.return_value = {
        "stock": {
            "symbol": "TEST",
            "name": "Test Inc.",
            "primaryExchange": "TSX",
        }
    }

    with patch.object(gateway, "_ws_get_identity_positions", return_value="not_a_list"):
        with pytest.raises(UnknownError):
            gateway._parse_position(
                ws_client=mock_client,
                broker_account_id="acc-tfsa-001",
                security_id="[sec-test]",
                ws_balance=10.0,
            )


def test_get_average_cost_not_found(gateway: WealthsimpleApiGateway) -> None:
    """Test _get_average_cost returns None when account is not in position accounts."""
    positions = [
        {
            "accounts": [{"id": "other-acc-001"}],
            "averagePrice": {"amount": 100.0},
        }
    ]
    avg_cost = gateway._get_average_cost("acc-tfsa-001", positions)
    assert avg_cost is None


def test_helper_mappings(gateway: WealthsimpleApiGateway) -> None:
    """Test symbol and exchange helper mapping methods."""
    assert gateway._map_eodhd_symbol("SU.TO") == "SU-TO"
    assert gateway._map_eodhd_exchange("CSE") == "CA"
    assert gateway._map_eodhd_exchange("TSX") == "TO"
    assert gateway._map_eodhd_exchange("NYSE") == "US"
    assert gateway._map_eodhd_exchange("NASDAQ") == "US"


@pytest.mark.asyncio
async def test_wealthsimple_api_wrapper_factory() -> None:
    """Test gateway factory initialization."""
    gateway = await wealthsimple_api_wrapper_factory(
        debug_api_responses=True,
        debug_dump_path="/tmp/dump.json",
    )
    assert isinstance(gateway, WealthsimpleApiGateway)
    assert gateway.debug_api_responses is True
    assert gateway.debug_dump_path == "/tmp/dump.json"
