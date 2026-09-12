from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from stockholm import Currency
from svcs import Container

from src.account.api.position import PositionApi
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
from src.account.service.csv_account import (
    CsvAccountService,
    csv_account_service_factory,
)
from src.core.enum import AccountTypeEnum, InstitutionEnum
from src.market.api import SecurityApi
from src.market.api_types import Security


def _create_mock_institution(
    inst_id: int = 1,
    name: str = "Wealthsimple",
    enabled: bool = True,
    csv_format: str | None = "Account Number,Symbol,Quantity",
) -> InstitutionSchema:
    return InstitutionSchema(
        id=inst_id,
        name=name,
        country="CA",
        website=None,
        is_active=True,
        integration_enabled=True,
        csv_import_enabled=enabled,
        csv_format=csv_format,
    )



def _create_service(
    account_repo: AsyncMock | None = None,
    inst_repo: AsyncMock | None = None,
    pos_api: AsyncMock | None = None,
    pos_repo: AsyncMock | None = None,
    sec_api: AsyncMock | None = None,
    parser: MagicMock | None = None,
) -> CsvAccountService:
    return CsvAccountService(
        account_repository=account_repo or AsyncMock(spec=AccountRepository),
        institution_repository=inst_repo or AsyncMock(spec=InstitutionRepository),
        position_api=pos_api or AsyncMock(spec=PositionApi),
        position_repository=pos_repo or AsyncMock(spec=PositionRepository),
        security_api=sec_api or AsyncMock(spec=SecurityApi),
        csv_parser=parser or MagicMock(spec=GenericCsvParser),
    )


@pytest.mark.asyncio
async def test_validate_csv_institution_not_found():
    inst_repo = AsyncMock(spec=InstitutionRepository)
    inst_repo.get.return_value = None
    service = _create_service(inst_repo=inst_repo)

    with pytest.raises(InstitutionNotFoundError) as exc:
        await service.validate_csv_institution(999)
    assert "Institution 999 not found" in str(exc.value)


@pytest.mark.asyncio
async def test_validate_csv_institution_disabled():
    inst_repo = AsyncMock(spec=InstitutionRepository)
    inst_repo.get.return_value = _create_mock_institution(enabled=False)
    service = _create_service(inst_repo=inst_repo)

    with pytest.raises(CsvImportDisabledError) as exc:
        await service.validate_csv_institution(1)
    assert "CSV import is not enabled or configured" in str(exc.value)


@pytest.mark.asyncio
async def test_validate_csv_institution_missing_format():
    inst_repo = AsyncMock(spec=InstitutionRepository)
    inst_repo.get.return_value = _create_mock_institution(enabled=True, csv_format=None)
    service = _create_service(inst_repo=inst_repo)

    with pytest.raises(CsvImportDisabledError) as exc:
        await service.validate_csv_institution(1)
    assert "CSV import is not enabled or configured" in str(exc.value)


@pytest.mark.asyncio
async def test_inspect_csv_empty_content():
    inst_repo = AsyncMock(spec=InstitutionRepository)
    inst_repo.get.return_value = _create_mock_institution()
    service = _create_service(inst_repo=inst_repo)

    with pytest.raises(CsvFileEmptyError):
        await service.inspect_csv(1, "   ")


@pytest.mark.asyncio
async def test_inspect_csv_success():
    inst_repo = AsyncMock(spec=InstitutionRepository)
    inst_repo.get.return_value = _create_mock_institution()
    parser = MagicMock(spec=GenericCsvParser)
    expected_accounts = [
        CsvDiscoveredAccount(
            account_number="ACC-1",
            account_name="TFSA",
            account_type_id=AccountTypeEnum.TFSA.value,
            account_type_name="TFSA",
            currency="CAD",
            positions_count=1,
            positions=[
                CsvPositionRecord(
                    symbol="VGRO",
                    quantity=Decimal("10"),
                    average_cost=Decimal("30"),
                    currency="CAD",
                )
            ],
        )
    ]
    parser.parse.return_value = expected_accounts
    service = _create_service(inst_repo=inst_repo, parser=parser)

    result = await service.inspect_csv(1, "valid,csv,content")
    assert result == expected_accounts
    parser.parse.assert_called_once_with("valid,csv,content", "Account Number,Symbol,Quantity")


@pytest.mark.asyncio
async def test_import_accounts_no_matching():
    inst_repo = AsyncMock(spec=InstitutionRepository)
    inst_repo.get.return_value = _create_mock_institution()
    parser = MagicMock(spec=GenericCsvParser)
    parser.parse.return_value = [
        CsvDiscoveredAccount(
            account_number="ACC-1",
            account_name="TFSA",
            account_type_id=AccountTypeEnum.TFSA.value,
            account_type_name="TFSA",
            currency="CAD",
            positions_count=0,
            positions=[],
        )
    ]
    service = _create_service(inst_repo=inst_repo, parser=parser)

    with pytest.raises(NoMatchingAccountsInCsvError):
        await service.import_accounts(
            user_id=uuid4(),
            institution_id=1,
            account_numbers=["DIFFERENT-ACC"],
            csv_content="content",
        )


@pytest.mark.asyncio
async def test_import_accounts_duplicate_detected():
    inst_repo = AsyncMock(spec=InstitutionRepository)
    inst_repo.get.return_value = _create_mock_institution(inst_id=1)
    parser = MagicMock(spec=GenericCsvParser)
    parser.parse.return_value = [
        CsvDiscoveredAccount(
            account_number="ACC-1",
            account_name="TFSA",
            account_type_id=AccountTypeEnum.TFSA.value,
            account_type_name="TFSA",
            currency="CAD",
            positions_count=0,
            positions=[],
        )
    ]
    account_repo = AsyncMock(spec=AccountRepository)
    user_id = uuid4()
    account_repo.get_by_user.return_value = [
        AccountSchema(
            id=uuid4(),
            external_id="ACC-1",
            name="Existing TFSA",
            user_id=user_id,
            account_type_id=AccountTypeEnum.TFSA,
            institution_id=InstitutionEnum.WEALTHSIMPLE,
            currency=Currency.CAD,
        )
    ]
    service = _create_service(
        inst_repo=inst_repo, parser=parser, account_repo=account_repo
    )

    with pytest.raises(CsvAccountDuplicateError) as exc:
        await service.import_accounts(
            user_id=user_id,
            institution_id=1,
            account_numbers=["ACC-1"],
            csv_content="content",
        )
    assert "already exist" in str(exc.value)


@pytest.mark.asyncio
async def test_import_accounts_success():
    inst_repo = AsyncMock(spec=InstitutionRepository)
    inst_repo.get.return_value = _create_mock_institution(inst_id=1)
    parser = MagicMock(spec=GenericCsvParser)
    parser.parse.return_value = [
        CsvDiscoveredAccount(
            account_number="ACC-1",
            account_name="TFSA",
            account_type_id=AccountTypeEnum.TFSA.value,
            account_type_name="TFSA",
            currency="CAD",
            positions_count=1,
            positions=[
                CsvPositionRecord(
                    symbol="VGRO",
                    exchange="TSX",
                    name="Vanguard Growth",
                    quantity=Decimal("100"),
                    average_cost=Decimal("30"),
                    currency="CAD",
                )
            ],
        )
    ]
    account_repo = AsyncMock(spec=AccountRepository)
    account_repo.get_by_user.return_value = []
    created_id = uuid4()

    def mock_create(acc: AccountSchema):
        acc_dict = acc.model_dump()
        acc_dict["id"] = created_id
        return AccountSchema.model_validate(acc_dict)

    account_repo.create.side_effect = mock_create
    refreshed_acc = AccountSchema(
        id=created_id,
        external_id="ACC-1",
        name="TFSA",
        user_id=uuid4(),
        account_type_id=AccountTypeEnum.TFSA,
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        currency=Currency.CAD,
        api_sync_enabled=False,
    )
    account_repo.get.return_value = refreshed_acc

    sec_api = AsyncMock(spec=SecurityApi)
    mock_sec = MagicMock(spec=Security)
    mock_sec.id = uuid4()
    sec_api.get_or_create_from_broker.return_value = mock_sec

    pos_api = AsyncMock(spec=PositionApi)

    service = _create_service(
        account_repo=account_repo,
        inst_repo=inst_repo,
        pos_api=pos_api,
        sec_api=sec_api,
        parser=parser,
    )

    imported = await service.import_accounts(
        user_id=refreshed_acc.user_id,
        institution_id=1,
        account_numbers=["ACC-1"],
        csv_content="valid,content",
    )

    assert len(imported) == 1
    assert imported[0].id == created_id
    account_repo.create.assert_awaited_once()
    sec_api.get_or_create_from_broker.assert_awaited_once_with(
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        broker_symbol="VGRO",
        broker_exchange="TSX",
        broker_name="Vanguard Growth",
    )
    pos_api.create.assert_awaited_once()
    account_repo.update_last_sync_at.assert_awaited_once_with(created_id)


@pytest.mark.asyncio
async def test_sync_account_not_found_by_id():
    account_repo = AsyncMock(spec=AccountRepository)
    account_repo.get.return_value = None
    service = _create_service(account_repo=account_repo)

    with pytest.raises(AccountNotFoundError):
        await service.sync_account_from_csv(uuid4(), "content")


@pytest.mark.asyncio
async def test_sync_account_no_matching_in_csv():
    account_id = uuid4()
    target_account = AccountSchema(
        id=account_id,
        external_id="EXTERNAL-TARGET",
        name="Target TFSA",
        user_id=uuid4(),
        account_type_id=AccountTypeEnum.TFSA,
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        currency=Currency.CAD,
    )
    inst_repo = AsyncMock(spec=InstitutionRepository)
    inst_repo.get.return_value = _create_mock_institution(inst_id=1)
    parser = MagicMock(spec=GenericCsvParser)
    parser.parse.return_value = [
        CsvDiscoveredAccount(
            account_number="SOME-OTHER-ID",
            account_name="TFSA",
            account_type_id=AccountTypeEnum.TFSA.value,
            account_type_name="TFSA",
            currency="CAD",
            positions_count=0,
            positions=[],
        )
    ]
    service = _create_service(
        inst_repo=inst_repo, parser=parser
    )

    with pytest.raises(AccountNotInCsvError) as exc:
        await service.sync_account_from_csv(target_account, "content")
    assert "No account matching 'EXTERNAL-TARGET' found in CSV" in str(exc.value)


@pytest.mark.asyncio
async def test_sync_account_csv_positions_security_resolution_error():
    account_id = uuid4()
    sec_api = AsyncMock(spec=SecurityApi)
    sec_api.get_or_create_from_broker.side_effect = ValueError("Symbol not found on EODHD")
    service = _create_service(sec_api=sec_api)

    csv_positions = [
        CsvPositionRecord(
            symbol="BAD_SYMBOL",
            exchange="TSX",
            name="Unknown",
            quantity=Decimal("10"),
            average_cost=Decimal("5"),
            currency="CAD",
        )
    ]

    with pytest.raises(SecurityResolutionError) as exc:
        await service.sync_account_csv_positions(
            account_id=account_id,
            institution_id=InstitutionEnum.WEALTHSIMPLE,
            csv_positions=csv_positions,
        )
    assert "Failed to resolve security for symbol 'BAD_SYMBOL'" in str(exc.value)


@pytest.mark.asyncio
async def test_csv_account_service_factory():
    container = AsyncMock(spec=Container)
    container.aget.side_effect = lambda cls: AsyncMock(spec=cls)

    service = await csv_account_service_factory(container)
    assert isinstance(service, CsvAccountService)
