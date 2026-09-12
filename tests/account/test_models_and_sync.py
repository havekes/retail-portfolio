"""Tests for AccountModel, InstitutionModel, schemas, and PositionService sync guard."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.account.api_types import Account, Institution
from src.account.exception import ApiSyncDisabledError
from src.account.model import AccountModel, InstitutionModel
from src.account.schema import AccountSchema, InstitutionSchema
from src.account.service.position import PositionService
from src.core.enum import AccountTypeEnum, InstitutionEnum


@pytest.mark.anyio
async def test_account_model(db_session: AsyncSession, seed_reference_data: None) -> None:
    """Verify AccountModel defaults api_sync_enabled to True in DB and Python."""
    account = AccountModel(
        id=uuid4(),
        external_id=str(uuid4()),
        name="Test Account Model",
        user_id=uuid4(),
        account_type_id=AccountTypeEnum.TFSA.value,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        currency="CAD",
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)

    assert account.api_sync_enabled is True

    # Also test explicit False
    account_false = AccountModel(
        id=uuid4(),
        external_id=str(uuid4()),
        name="Test Account Disabled",
        user_id=uuid4(),
        account_type_id=AccountTypeEnum.TFSA.value,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        currency="CAD",
        api_sync_enabled=False,
    )
    db_session.add(account_false)
    await db_session.commit()
    await db_session.refresh(account_false)

    assert account_false.api_sync_enabled is False


@pytest.mark.anyio
async def test_institution_model(db_session: AsyncSession) -> None:
    """Verify InstitutionModel defaults csv_import_enabled to False and csv_format to None."""
    inst = InstitutionModel(
        id=999,
        name="Test Inst",
        country="US",
    )
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    assert inst.csv_import_enabled is False
    assert inst.csv_format is None

    SAMPLE_CSV_FORMAT = (
        "{account_name},{account_type},{account_classification},{account_number},"
        "{symbol},{exchange},{mic},{name},{security_type},{quantity},"
        "{position_direction},{market_price},{market_price_currency},"
        "{book_value_cad},{book_value_currency_cad},{book_value},{currency},"
        "{market_value},{market_value_currency},{market_unrealized_returns},"
        "{market_unrealized_returns_currency}"
    )

    # Also test with custom CSV format positional template and enabled
    inst_csv = InstitutionModel(
        id=998,
        name="Test CSV Inst",
        country="US",
        csv_import_enabled=True,
        csv_format=SAMPLE_CSV_FORMAT,
    )
    db_session.add(inst_csv)
    await db_session.commit()
    await db_session.refresh(inst_csv)

    assert inst_csv.csv_import_enabled is True
    assert inst_csv.csv_format == SAMPLE_CSV_FORMAT


def test_schema_and_api_types_serialization() -> None:
    """Verify serialization and validation of new fields in schemas and api types."""
    account_schema = AccountSchema(
        id=uuid4(),
        external_id="ext-1",
        name="Schema Account",
        user_id=uuid4(),
        account_type_id=AccountTypeEnum.TFSA,
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        currency="CAD",
    )
    assert account_schema.api_sync_enabled is True

    account_schema_disabled = AccountSchema(
        id=uuid4(),
        external_id="ext-2",
        name="Disabled Account",
        user_id=uuid4(),
        account_type_id=AccountTypeEnum.TFSA,
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        currency="CAD",
        api_sync_enabled=False,
    )
    assert account_schema_disabled.api_sync_enabled is False

    inst_schema = InstitutionSchema(
        id=InstitutionEnum.WEALTHSIMPLE,
        name="Wealthsimple",
        country="CA",
        website="https://www.wealthsimple.com",
        is_active=True,
        integration_enabled=True,
    )
    assert inst_schema.csv_import_enabled is False
    assert inst_schema.csv_format is None

    sample_csv_format = (
        "{account_name},{account_type},{account_classification},{account_number},"
        "{symbol},{exchange},{mic},{name},{security_type},{quantity},"
        "{position_direction},{market_price},{market_price_currency},"
        "{book_value_cad},{book_value_currency_cad},{book_value},{currency},"
        "{market_value},{market_value_currency},{market_unrealized_returns},"
        "{market_unrealized_returns_currency}"
    )
    inst_api = Institution(
        id=InstitutionEnum.WEALTHSIMPLE,
        name="Wealthsimple",
        country="CA",
        website="https://www.wealthsimple.com",
        is_active=True,
        integration_enabled=True,
        csv_import_enabled=True,
        csv_format=sample_csv_format,
    )
    assert inst_api.csv_import_enabled is True
    assert inst_api.csv_format == sample_csv_format

    account_api = Account(
        id=uuid4(),
        external_id="ext-1",
        name="API Account",
        user_id=uuid4(),
        account_type_id=AccountTypeEnum.TFSA,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        currency="CAD",
    )
    assert account_api.api_sync_enabled is True


@pytest.mark.anyio
async def test_position_service_sync_raises_api_sync_disabled_error() -> None:
    """PositionService.sync_account_positions raises ApiSyncDisabledError when api_sync_enabled is False."""
    account_service_mock = MagicMock()
    account_id = uuid4()
    user_id = uuid4()

    disabled_account = AccountSchema(
        id=account_id,
        external_id="ext-123",
        name="CSV Account",
        user_id=user_id,
        account_type_id=AccountTypeEnum.TFSA,
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        currency="CAD",
        api_sync_enabled=False,
    )
    account_service_mock.get_account = AsyncMock(return_value=disabled_account)

    service = PositionService(
        account_service=account_service_mock,
        fx_rates=MagicMock(),
        integration_account_api=MagicMock(),
        integration_user_api=MagicMock(),
        market_prices=MagicMock(),
        position_repository=MagicMock(),
        security_service=MagicMock(),
    )

    with pytest.raises(ApiSyncDisabledError) as exc_info:
        await service.sync_account_positions(user_id=user_id, account_id=account_id)

    assert exc_info.value.account_id == account_id
    assert f"API sync is not enabled for account {account_id}" in str(exc_info.value)
