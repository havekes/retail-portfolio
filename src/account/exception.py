from typing import override

from src.account.api_types import AccountId, PortfolioId
from src.account.enum import InstitutionEnum
from src.exception import AuthorizationError, EntityNotFoundError


class AccountNotFoundError(EntityNotFoundError):
    """Raised when an account is not found."""

    def __init__(self, account_id: AccountId):
        self.entity_id = str(account_id)
        self.entity_name = "Account"

        super().__init__(str(self))


class AccountsDoNotBelongToUserError(AuthorizationError):
    """Raised when one or more accounts do not belong to the user."""

    def __init__(self, account_ids: list[AccountId]):
        self.account_ids = account_ids

        super().__init__()

    @override
    def log_message(self) -> str:
        return f"Accounts with IDs {self.account_ids} do not belong to the user."


class PortfolioNotFoundError(EntityNotFoundError):
    """Raised when a portfolio is not found."""

    def __init__(self, portfolio_id: PortfolioId):
        self.entity_id = str(portfolio_id)
        self.entity_name = "Portfolio"

        super().__init__(str(self))
