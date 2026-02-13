"""Account, position, and security fixtures."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.account.api_types import AccountTypeEnum
from src.account.enum import InstitutionEnum
from src.account.model import (
    AccountModel,
    PositionModel,
)
from src.account.schema import AccountSchema, PositionSchema
from src.auth.schema import UserSchema
from src.integration.model import IntegrationUserModel
from src.integration.schema import IntegrationUserSchema
from src.market.model import SecurityModel
from src.market.schema import SecuritySchema


@pytest.fixture
async def test_account(
    db_session: AsyncSession, test_user: UserSchema
) -> AccountSchema:
    """Create and persist a single test account for the test user."""
    account_model = AccountModel(
        id=uuid4(),
        external_id="ext_id_0",
        name="Test Account",
        user_id=test_user.id,
        account_type_id=AccountTypeEnum.TFSA.value,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        currency="CAD",
        is_active=True,
        created_at=datetime.now(UTC),
        deleted_at=None,
    )
    db_session.add(account_model)
    await db_session.commit()
    await db_session.refresh(account_model)

    return AccountSchema.model_validate(account_model)


@pytest.fixture
async def test_accounts(
    db_session: AsyncSession, test_user: UserSchema
) -> list[AccountSchema]:
    """Create and persist two test accounts for the test user."""
    accounts = []
    for i in range(2):
        account_model = AccountModel(
            id=uuid4(),
            external_id=f"ext_id_{i}",
            name=f"Test Account {i}",
            user_id=test_user.id,
            account_type_id=AccountTypeEnum.TFSA.value,
            institution_id=InstitutionEnum.WEALTHSIMPLE.value,
            currency="CAD",
            is_active=True,
            created_at=datetime.now(UTC),
            deleted_at=None,
        )
        db_session.add(account_model)
        await db_session.flush()
        await db_session.refresh(account_model)

        accounts.append(AccountSchema.model_validate(account_model))

    await db_session.commit()
    return accounts


@pytest.fixture
async def other_user_account(
    db_session: AsyncSession, other_user: UserSchema
) -> AccountSchema:
    """Create and persist an account owned by a different user."""
    account_model = AccountModel(
        id=uuid4(),
        external_id="other_ext_id",
        name="Other Account",
        user_id=other_user.id,
        account_type_id=AccountTypeEnum.RRSP.value,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        currency="CAD",
        is_active=True,
        created_at=datetime.now(UTC),
        deleted_at=None,
    )

    db_session.add(account_model)
    await db_session.commit()
    await db_session.refresh(account_model)

    return AccountSchema.model_validate(account_model)


@pytest.fixture
async def test_security(db_session: AsyncSession) -> SecuritySchema:
    """Create and persist a test security."""
    security = SecurityModel(
        id=uuid4(),
        symbol="AAPL",
        exchange="NASDAQ",
        currency="USD",
        name="Apple Inc.",
        isin="US0378331005",
        is_active=True,
    )

    db_session.add(security)
    await db_session.commit()
    await db_session.refresh(security)

    return SecuritySchema(
        id=security.id,
        symbol=security.symbol,
        exchange=security.exchange,
        currency=security.currency,
        name=security.name,
        isin=security.isin,
        is_active=security.is_active,
        updated_at=security.updated_at,
    )


@pytest.fixture
async def test_position(
    db_session: AsyncSession,
    test_account: AccountSchema,
    test_security: SecuritySchema,
) -> PositionSchema:
    """Create and persist a test position."""
    position_model = PositionModel(
        id=uuid4(),
        account_id=test_account.id,
        security_id=test_security.id,
        quantity=Decimal("10.0"),
        average_cost=Decimal("150.0"),
    )
    db_session.add(position_model)
    await db_session.commit()
    await db_session.refresh(position_model)

    return PositionSchema(
        id=position_model.id,
        account_id=position_model.account_id,
        security_id=position_model.security_id,
        quantity=position_model.quantity,
        average_cost=position_model.average_cost,
        updated_at=position_model.updated_at,
    )


@pytest.fixture
async def test_positions(
    db_session: AsyncSession,
    test_accounts: list[AccountSchema],
    test_security: SecuritySchema,
) -> list[PositionSchema]:
    """Create and persist test positions for the first test account."""
    position_model = PositionModel(
        id=uuid4(),
        account_id=test_accounts[0].id,
        security_id=test_security.id,
        quantity=Decimal("10.0"),
        average_cost=Decimal("150.0"),
    )
    db_session.add(position_model)
    await db_session.commit()
    await db_session.refresh(position_model)

    return [
        PositionSchema(
            id=position_model.id,
            account_id=position_model.account_id,
            security_id=position_model.security_id,
            quantity=position_model.quantity,
            average_cost=position_model.average_cost,
            updated_at=position_model.updated_at,
        )
    ]


@pytest.fixture
async def test_position_for_first_account(
    db_session: AsyncSession,
    test_accounts: list[AccountSchema],
    test_security: SecuritySchema,
) -> PositionSchema:
    """Create and persist a test position for the first test account."""
    position_model = PositionModel(
        id=uuid4(),
        account_id=test_accounts[0].id,
        security_id=test_security.id,
        quantity=Decimal("10.0"),
        average_cost=Decimal("150.0"),
    )
    db_session.add(position_model)
    await db_session.commit()
    await db_session.refresh(position_model)

    return PositionSchema(
        id=position_model.id,
        account_id=position_model.account_id,
        security_id=position_model.security_id,
        quantity=position_model.quantity,
        average_cost=position_model.average_cost,
        updated_at=position_model.updated_at,
    )


@pytest.fixture
async def test_integration_user(
    db_session: AsyncSession, test_user: UserSchema
) -> IntegrationUserSchema:
    """Create and persist a test integration user."""
    integration_user_model = IntegrationUserModel(
        id=uuid4(),
        user_id=test_user.id,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        external_user_id="ext_user_123",
        display_name="John Doe",
        last_used_at=datetime.now(UTC),
    )

    db_session.add(integration_user_model)
    await db_session.commit()
    await db_session.refresh(integration_user_model)

    return IntegrationUserSchema.model_validate(integration_user_model)


@pytest.fixture
async def test_external_user(
    db_session: AsyncSession, test_user: UserSchema
) -> IntegrationUserSchema:
    """Create and persist a test external user for the test user."""
    integration_user_model = IntegrationUserModel(
        id=uuid4(),
        user_id=test_user.id,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        external_user_id="ext_user_test",
        display_name="Test External User",
        last_used_at=datetime.now(UTC),
    )

    db_session.add(integration_user_model)
    await db_session.commit()
    await db_session.refresh(integration_user_model)

    return IntegrationUserSchema.model_validate(integration_user_model)


@pytest.fixture
async def other_user_external_user(
    db_session: AsyncSession, other_user: UserSchema
) -> IntegrationUserSchema:
    """Create and persist an external user owned by a different user."""
    integration_user_model = IntegrationUserModel(
        id=uuid4(),
        user_id=other_user.id,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        external_user_id="ext_user_other",
        display_name="Other User External",
        last_used_at=datetime.now(UTC),
    )

    db_session.add(integration_user_model)
    await db_session.commit()
    await db_session.refresh(integration_user_model)

    return IntegrationUserSchema.model_validate(integration_user_model)
