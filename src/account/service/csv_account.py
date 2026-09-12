import uuid

from stockholm import Currency
from svcs import Container

from src.account.api.position import PositionApi
from src.account.api_types import AccountId, Position
from src.account.csv import (
    CsvDiscoveredAccount,
    CsvPositionRecord,
    GenericCsvParser,
)
from src.account.exception import (
    AccountNotFoundError,
    AccountNotInCsvError,
    CsvAccountDuplicateError,
    CsvFileEmptyError,
    CsvImportDisabledError,
    InstitutionNotFoundError,
    NoMatchingAccountsInCsvError,
    SecurityResolutionError,
)
from src.account.repository import (
    AccountRepository,
    InstitutionRepository,
    PositionRepository,
)
from src.account.schema import AccountSchema, InstitutionSchema
from src.auth.api_types import UserId
from src.core.enum import InstitutionEnum
from src.market.api import SecurityApi


class CsvAccountService:
    _account_repository: AccountRepository
    _institution_repository: InstitutionRepository
    _position_api: PositionApi
    _position_repository: PositionRepository
    _security_api: SecurityApi
    _csv_parser: GenericCsvParser

    def __init__(  # noqa: PLR0913, PLR0917
        self,
        account_repository: AccountRepository,
        institution_repository: InstitutionRepository,
        position_api: PositionApi,
        position_repository: PositionRepository,
        security_api: SecurityApi,
        csv_parser: GenericCsvParser,
    ):
        self._account_repository = account_repository
        self._institution_repository = institution_repository
        self._position_api = position_api
        self._position_repository = position_repository
        self._security_api = security_api
        self._csv_parser = csv_parser

    async def validate_csv_institution(
        self, institution_id: int | InstitutionEnum
    ) -> InstitutionSchema:
        """Verify that institution exists and has CSV import enabled."""
        raw_id = int(institution_id)
        institution = await self._institution_repository.get(raw_id)
        if institution is None:
            raise InstitutionNotFoundError(raw_id)

        if not institution.csv_import_enabled or not institution.csv_format:
            inst_name = institution.name if institution else str(raw_id)
            raise CsvImportDisabledError(inst_name)

        return institution

    async def inspect_csv(
        self, institution_id: int | InstitutionEnum, csv_content: str
    ) -> list[CsvDiscoveredAccount]:
        """Inspect CSV content for an institution and return discovered accounts."""
        institution = await self.validate_csv_institution(institution_id)
        assert institution.csv_format is not None

        if not csv_content or not csv_content.strip():
            raise CsvFileEmptyError

        return self._csv_parser.parse(csv_content, institution.csv_format)

    async def import_accounts(
        self,
        user_id: UserId,
        institution_id: int | InstitutionEnum,
        account_numbers: list[str],
        csv_content: str,
    ) -> list[AccountSchema]:
        """Import selected accounts and positions from CSV content."""
        institution = await self.validate_csv_institution(institution_id)
        assert institution.csv_format is not None

        if not csv_content or not csv_content.strip():
            raise CsvFileEmptyError

        discovered_accounts = self._csv_parser.parse(
            csv_content, institution.csv_format
        )

        requested_set = set(account_numbers)
        matching_discovered = [
            acc for acc in discovered_accounts if acc.account_number in requested_set
        ]
        if not matching_discovered:
            raise NoMatchingAccountsInCsvError

        raw_institution_id = int(institution_id)
        user_accounts = await self._account_repository.get_by_user(user_id)
        self._check_duplicate_accounts(
            user_accounts, matching_discovered, raw_institution_id
        )

        created_accounts: list[AccountSchema] = []
        for disc_acc in matching_discovered:
            account_schema = AccountSchema(
                id=uuid.uuid4(),
                external_id=disc_acc.account_number,
                name=disc_acc.account_name,
                user_id=user_id,
                integration_user_id=None,
                account_type_id=disc_acc.account_type_id,
                institution_id=InstitutionEnum(raw_institution_id),
                currency=Currency(disc_acc.currency),
                broker_display_name=disc_acc.account_name,
                is_active=True,
                api_sync_enabled=False,
            )
            created = await self._account_repository.create(account_schema)
            await self.sync_account_csv_positions(
                account_id=created.id,
                institution_id=InstitutionEnum(raw_institution_id),
                csv_positions=disc_acc.positions,
            )
            refreshed = await self._account_repository.get(created.id)
            created_accounts.append(refreshed if refreshed is not None else created)

        return created_accounts

    async def sync_account_from_csv(
        self,
        account: AccountSchema | AccountId,
        csv_content: str,
    ) -> AccountSchema:
        """Update positions of an existing account from CSV content."""
        if isinstance(account, AccountSchema):
            target_account = account
        else:
            found = await self._account_repository.get(account)
            if found is None:
                raise AccountNotFoundError(account)
            target_account = found

        institution = await self.validate_csv_institution(target_account.institution_id)
        assert institution.csv_format is not None

        if not csv_content or not csv_content.strip():
            raise CsvFileEmptyError

        discovered_accounts = self._csv_parser.parse(
            csv_content, institution.csv_format
        )

        matching_account = next(
            (
                acc
                for acc in discovered_accounts
                if acc.account_number == target_account.external_id
            ),
            None,
        )
        if matching_account is None:
            raise AccountNotInCsvError(target_account.external_id)

        await self.sync_account_csv_positions(
            account_id=target_account.id,
            institution_id=InstitutionEnum(target_account.institution_id),
            csv_positions=matching_account.positions,
        )

        refreshed = await self._account_repository.get(target_account.id)
        if refreshed is None:
            raise AccountNotFoundError(target_account.id)

        return refreshed

    async def sync_account_csv_positions(
        self,
        account_id: AccountId,
        institution_id: InstitutionEnum,
        csv_positions: list[CsvPositionRecord],
    ) -> None:
        """Resolve securities and persist positions for a CSV account."""
        positions: list[Position] = []
        for pos in csv_positions:
            try:
                security = await self._security_api.get_or_create_from_broker(
                    institution_id=institution_id,
                    broker_symbol=pos.symbol,
                    broker_exchange=pos.exchange or "",
                    broker_name=pos.name or "",
                )
            except ValueError as e:
                raise SecurityResolutionError(symbol=pos.symbol, reason=str(e)) from e

            positions.append(
                Position(
                    account_id=account_id,
                    security_id=security.id,
                    quantity=pos.quantity,
                    average_cost=pos.average_cost,
                    currency=pos.currency,
                )
            )

        if positions:
            await self._position_api.create(positions)
        else:
            await self._position_repository.sync_by_account(account_id, [])

        await self._account_repository.update_last_sync_at(account_id)

    def _check_duplicate_accounts(
        self,
        user_accounts: list[AccountSchema],
        matching_discovered: list[CsvDiscoveredAccount],
        institution_id: int,
    ) -> None:
        """Ensure accounts to import do not exist for this user & institution."""
        existing_external_ids = {
            acc.external_id
            for acc in user_accounts
            if int(acc.institution_id) == institution_id
        }
        duplicates = [
            acc.account_number
            for acc in matching_discovered
            if acc.account_number in existing_external_ids
        ]
        if duplicates:
            raise CsvAccountDuplicateError(duplicates)


async def csv_account_service_factory(container: Container) -> CsvAccountService:
    return CsvAccountService(
        account_repository=await container.aget(AccountRepository),
        institution_repository=await container.aget(InstitutionRepository),
        position_api=await container.aget(PositionApi),
        position_repository=await container.aget(PositionRepository),
        security_api=await container.aget(SecurityApi),
        csv_parser=await container.aget(GenericCsvParser),
    )
