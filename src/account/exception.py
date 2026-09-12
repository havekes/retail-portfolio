from typing import override

from src.account.api_types import AccountId, PortfolioId
from src.account.csv.exceptions import (
    CsvEmptyError,
    CsvHeaderValidationError,
    CsvParserError,
    CsvRowValidationError,
)
from src.core.enum import InstitutionEnum
from src.core.exception import AuthorizationError, EntityNotFoundError


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


class ApiSyncDisabledError(Exception):
    """Raised when an API sync is attempted on an account
    with api_sync_enabled=False.
    """

    def __init__(self, account_id: AccountId):
        self.account_id = account_id
        super().__init__(f"API sync is not enabled for account {account_id}")


class InstitutionNotFoundError(EntityNotFoundError):
    """Raised when an institution is not found."""

    def __init__(self, institution_id: int):
        self.entity_id = str(institution_id)
        self.entity_name = "Institution"
        self.message = f"Institution {institution_id} not found"
        super().__init__(self.message)

    @override
    def __str__(self) -> str:
        return self.message


class CsvFileEmptyError(CsvEmptyError):
    """Raised when the CSV file or content is empty."""

    def __init__(self, message: str = "CSV file is empty") -> None:
        super().__init__(message)


class CsvImportDisabledError(Exception):
    """Raised when CSV import is not enabled or configured for an institution."""

    def __init__(self, institution_name: str):
        self.institution_name = institution_name
        super().__init__(
            f"CSV import is not enabled or configured for institution "
            f"'{institution_name}'"
        )


class CsvAccountDuplicateError(Exception):
    """Raised when one or more accounts being imported already exist."""

    def __init__(self, duplicates: list[str]):
        self.duplicates = duplicates
        super().__init__(
            f"Account(s) already exist for this institution: {', '.join(duplicates)}"
        )


class NoMatchingAccountsInCsvError(Exception):
    """Raised when CSV has no accounts matching requested account numbers."""

    DEFAULT_MESSAGE = "No matching accounts found in CSV for requested account numbers"

    def __init__(
        self,
        message: str = DEFAULT_MESSAGE,
    ):
        super().__init__(message)


class AccountNotInCsvError(Exception):
    """Raised when the account's external_id is not found in the CSV."""

    def __init__(self, external_id: str):
        self.external_id = external_id
        super().__init__(f"No account matching '{external_id}' found in CSV")


class SecurityResolutionError(Exception):
    """Raised when resolving a security from broker details fails."""

    def __init__(self, symbol: str, reason: str):
        self.symbol = symbol
        self.reason = reason
        super().__init__(f"Failed to resolve security for symbol '{symbol}': {reason}")
