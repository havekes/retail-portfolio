"""Wealthsimple API stubs for testing and local development."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from src.account.enum import AccountTypeEnum, InstitutionEnum
from src.integration.brokers import BrokerApiGateway
from src.integration.brokers.api_types import BrokerAccount, BrokerPosition
from src.integration.schema import IntegrationUserSchema


class StubWealthsimpleAPI:
    """Stub implementation of ws_api.WealthsimpleAPI."""

    def __init__(self, sess=None) -> None:
        self.session = sess or StubWSAPISession()

    @staticmethod
    def from_token(
        sess, _persist_session_fct=None, _username=None
    ) -> StubWealthsimpleAPI:
        """Create API instance from session token."""
        return StubWealthsimpleAPI(sess)

    @staticmethod
    def login(
        username: str,
        _password: str,
        _otp_answer: str | None = None,
        persist_session_fct=None,
        _scope: str = "invest.read trade.read tax.read",
    ) -> StubWSAPISession:
        """Login to Wealthsimple and return a session."""
        session = StubWSAPISession()
        session.access_token = "stub_access_token_12345"  # noqa: S105
        session.refresh_token = "stub_refresh_token_67890"  # noqa: S105
        session.session_id = "stub_session_id_abcde"
        session.wssdi = "stub_wssdi_fghij"
        session.client_id = "stub_client_id_klmno"

        if persist_session_fct:
            persist_session_fct(session.to_json(), username)

        return session

    def get_accounts(
        self,
        open_only: bool = True,  # noqa: FBT001, FBT002
        _use_cache: bool = True,  # noqa: FBT001, FBT002
    ) -> list[dict[str, Any]]:
        """Get Wealthsimple accounts."""
        accounts = [
            {
                "id": "acc-tfsa-001",
                "status": "open",
                "unifiedAccountType": "SELF_DIRECTED_TFSA",
                "currency": "CAD",
                "createdAt": "2024-01-15T10:30:00.000Z",
                "custodianAccounts": [
                    {
                        "id": "cust-tfsa-001",
                        "financials": {
                            "current": {"netLiquidationValue": {"amount": 25000.50}}
                        },
                    }
                ],
            },
            {
                "id": "acc-rrsp-002",
                "status": "open",
                "unifiedAccountType": "SELF_DIRECTED_RRSP",
                "currency": "CAD",
                "createdAt": "2023-06-20T14:45:00.000Z",
                "custodianAccounts": [
                    {
                        "id": "cust-rrsp-002",
                        "financials": {
                            "current": {"netLiquidationValue": {"amount": 50000.00}}
                        },
                    }
                ],
            },
            {
                "id": "acc-closed-003",
                "status": "closed",
                "unifiedAccountType": "SELF_DIRECTED_NON_REGISTERED",
                "currency": "CAD",
                "createdAt": "2022-03-10T09:00:00.000Z",
                "custodianAccounts": [
                    {
                        "id": "cust-nonreg-003",
                        "financials": {
                            "current": {"netLiquidationValue": {"amount": 0.00}}
                        },
                    }
                ],
            },
        ]

        if open_only:
            return [acc for acc in accounts if acc["status"] == "open"]
        return accounts

    def get_account_balances(self, account_id: str) -> dict[str, float]:
        """Get account balances (positions)."""
        balances = {
            "acc-tfsa-001": {
                "[sec-tsx-xyr]": 100.0,
                "[sec-us-nflx]": 25.0,
                "[sec-us-aapl]": 50.0,
                "sec-c-cad": 1500.25,
            },
            "acc-rrsp-002": {
                "[sec-tsx-ryt]": 200.0,
                "[sec-us-msft]": 75.0,
                "sec-c-cad": 5000.00,
            },
        }
        return balances.get(account_id, {})

    def get_security_market_data(
        self,
        security_id: str,
        _use_cache: bool = True,  # noqa: FBT001, FBT002
    ) -> dict[str, Any]:
        """Get security market data."""
        security_data = {
            "sec-tsx-xyr": {
                "stock": {
                    "symbol": "XYR",
                    "name": "Royal Bank of Canada",
                    "primaryExchange": "TSX",
                }
            },
            "sec-us-nflx": {
                "stock": {
                    "symbol": "NFLX",
                    "name": "Netflix Inc.",
                    "primaryExchange": "NASDAQ",
                }
            },
            "sec-us-aapl": {
                "stock": {
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "primaryExchange": "NASDAQ",
                }
            },
            "sec-tsx-ryt": {
                "stock": {
                    "symbol": "RYT",
                    "name": "Royal Trust",
                    "primaryExchange": "TSX",
                }
            },
            "sec-us-msft": {
                "stock": {
                    "symbol": "MSFT",
                    "name": "Microsoft Corporation",
                    "primaryExchange": "NASDAQ",
                }
            },
        }
        return security_data.get(security_id, {"stock": {}})

    def get_identity_positions(
        self, security_ids: list[str] | None, _currency: str
    ) -> list[dict[str, Any]]:
        """Get identity positions."""
        positions = [
            {
                "securityId": "sec-tsx-xyr",
                "accounts": [
                    {
                        "id": "acc-tfsa-001",
                        "quantity": 100.0,
                        "averagePrice": {"amount": 120.50},
                    }
                ],
                "averagePrice": {"amount": 120.50},
            },
            {
                "securityId": "sec-us-nflx",
                "accounts": [
                    {
                        "id": "acc-tfsa-001",
                        "quantity": 25.0,
                        "averagePrice": {"amount": 450.00},
                    }
                ],
                "averagePrice": {"amount": 450.00},
            },
            {
                "securityId": "sec-us-aapl",
                "accounts": [
                    {
                        "id": "acc-tfsa-001",
                        "quantity": 50.0,
                        "averagePrice": {"amount": 175.25},
                    }
                ],
                "averagePrice": {"amount": 175.25},
            },
            {
                "securityId": "sec-tsx-ryt",
                "accounts": [
                    {
                        "id": "acc-rrsp-002",
                        "quantity": 200.0,
                        "averagePrice": {"amount": 95.00},
                    }
                ],
                "averagePrice": {"amount": 95.00},
            },
            {
                "securityId": "sec-us-msft",
                "accounts": [
                    {
                        "id": "acc-rrsp-002",
                        "quantity": 75.0,
                        "averagePrice": {"amount": 380.00},
                    }
                ],
                "averagePrice": {"amount": 380.00},
            },
        ]

        if security_ids:
            return [p for p in positions if p["securityId"] in security_ids]
        return positions


class StubWSAPISession:
    """Stub implementation of ws_api.session.WSAPISession."""

    def __init__(self) -> None:
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.session_id: str | None = None
        self.wssdi: str | None = None
        self.client_id: str | None = None
        self.token_info: dict | None = None

    def to_json(self) -> str:
        """Serialize session to JSON string."""
        return json.dumps(
            {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "session_id": self.session_id,
                "wssdi": self.wssdi,
                "client_id": self.client_id,
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> StubWSAPISession:
        """Deserialize session from JSON string."""
        data = json.loads(json_str)
        session = cls()
        session.access_token = data.get("access_token")
        session.refresh_token = data.get("refresh_token")
        session.session_id = data.get("session_id")
        session.wssdi = data.get("wssdi")
        session.client_id = data.get("client_id")
        return session


class StubWealthsimpleApiGateway(BrokerApiGateway):
    """Stub Wealthsimple API gateway for testing."""

    _keyring_prefix: str = "retail_portfolio_wealthsimple_stub"
    _institution: InstitutionEnum = InstitutionEnum.WEALTHSIMPLE

    def __init__(self) -> None:
        super().__init__()
        self._username: str | None = None

    def _get_client(self, _username: str) -> StubWealthsimpleAPI:
        """Get stub Wealthsimple API client."""
        return StubWealthsimpleAPI()

    def login(
        self,
        username: str,
        password: str | None = None,
        otp: str | None = None,
    ) -> bool:
        """Login to Wealthsimple using stub credentials."""
        _ = password, otp  # Unused in stub mode
        self._username = username
        return True

    async def get_accounts(
        self, integration_user: IntegrationUserSchema
    ) -> list[BrokerAccount]:
        """Get Wealthsimple accounts using stub data."""
        ws_client = self._get_client(integration_user.external_user_id)
        ws_accounts = ws_client.get_accounts()

        accounts: list[BrokerAccount] = []
        for ws_account in ws_accounts:
            account = self._parse_account(ws_account, integration_user.display_name)
            if account is not None:
                accounts.append(account)

        return accounts

    async def get_positions_by_account(
        self,
        integration_user: IntegrationUserSchema,
        broker_account_id: str,
    ) -> list[BrokerPosition]:
        """Get Wealthsimple positions using stub data."""
        ws_client = self._get_client(integration_user.external_user_id)
        ws_balances = ws_client.get_account_balances(broker_account_id)
        positions: list[BrokerPosition] = []

        for security_id, ws_balance in ws_balances.items():
            if security_id == "sec-c-cad":
                continue

            trimmed_security_id = (
                security_id[1:-1] if security_id.startswith("[") else security_id
            )

            ws_security_market_data = ws_client.get_security_market_data(
                trimmed_security_id
            )
            if not isinstance(ws_security_market_data, dict):
                continue

            ws_positions = self._ws_get_identity_positions(
                client=ws_client,
                security_ids=[trimmed_security_id],
            )
            if not isinstance(ws_positions, list):
                continue

            average_cost = Decimal(
                self._get_average_cost(broker_account_id, ws_positions) or 0
            )
            stock_info = ws_security_market_data.get("stock", {})

            if not stock_info.get("primaryExchange"):
                continue

            position = BrokerPosition(
                broker_account_id=broker_account_id,
                name=stock_info["name"],
                symbol=stock_info["symbol"],
                exchange=stock_info["primaryExchange"],
                quantity=Decimal(str(ws_balance)),
                average_cost=average_cost,
            )
            positions.append(position)

        return positions

    def _ws_get_identity_positions(
        self,
        client: StubWealthsimpleAPI,
        security_ids: list[str] | None = None,
        _currency: str = "CAD",
    ):
        """Get identity positions from Wealthsimple stub client."""
        return client.get_identity_positions(security_ids, _currency)

    def _parse_account(
        self,
        ws_account: dict[str, Any],
        broker_display_name: str | None = None,
    ) -> BrokerAccount | None:
        """Parse a Wealthsimple account into a BrokerAccount."""
        if ws_account["status"] != "open":
            return None

        ws_account_type = ws_account["unifiedAccountType"]
        try:
            account_type = self._get_account_type(ws_account_type)
        except KeyError:
            return None

        custodian_account = ws_account["custodianAccounts"][0]
        current_amount = Decimal(
            custodian_account["financials"]["current"]["netLiquidationValue"]["amount"]
        )

        return BrokerAccount(
            id=ws_account["id"],
            type=account_type,
            institution=InstitutionEnum.WEALTHSIMPLE,
            currency=ws_account["currency"],
            display_name=custodian_account["id"],
            broker_display_name=broker_display_name,
            value=current_amount,
            created_at=datetime.strptime(
                ws_account["createdAt"], "%Y-%m-%dT%H:%M:%S.%fZ"
            ).astimezone(UTC),
        )

    def _get_average_cost(
        self,
        broker_account_id: str,
        ws_positions: list[dict[str, Any]],
    ) -> Decimal | None:
        """Get average cost for a position."""
        for ws_position in ws_positions:
            if ws_position["accounts"][0]["id"] == broker_account_id:
                return ws_position["averagePrice"]["amount"]
        return None

    def _get_account_type(self, ws_unified_account_type: str) -> AccountTypeEnum:
        """Map Wealthsimple account type to AccountTypeEnum."""
        _wealthsimple_account_type_map = {
            "SELF_DIRECTED_TFSA": AccountTypeEnum.TFSA,
            "SELF_DIRECTED_RRSP": AccountTypeEnum.RRSP,
            "SELF_DIRECTED_FHSA": AccountTypeEnum.FHSA,
            "SELF_DIRECTED_NON_REGISTERED": AccountTypeEnum.NON_REGISTERED,
        }
        return _wealthsimple_account_type_map[ws_unified_account_type]
