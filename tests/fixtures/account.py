"""Account, portfolio, position, and security fixtures."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.account.api_types import AccountTypeEnum
from src.account.enum import InstitutionEnum
from src.account.model import (
    AccountModel,
    PortfolioAccountModel,
    PortfolioModel,
    PositionModel,
)
from src.account.schema import (
    AccountSchema,
    PortfolioAccountSchema,
    PortfolioSchema,
    PositionSchema,
)
from src.auth.schema import UserSchema
from src.integration.model import IntegrationUserModel
from src.integration.schema import IntegrationUserSchema
from src.market.model import SecurityModel
from src.market.schema import SecuritySchema


# Account fixtures
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
    """Create and persist three test accounts for the test user."""
    accounts = []
    for i in range(3):
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


# Portfolio fixtures
@pytest.fixture
async def test_portfolio(
    db_session: AsyncSession, test_user: UserSchema
) -> PortfolioSchema:
    """Create and persist a single test portfolio for the test user."""
    portfolio_model = PortfolioModel(
        id=uuid4(),
        user_id=test_user.id,
        name="Test Portfolio",
        created_at=datetime.now(UTC),
        deleted_at=None,
    )
    db_session.add(portfolio_model)
    await db_session.commit()
    await db_session.refresh(portfolio_model)

    return PortfolioSchema(
        id=portfolio_model.id,
        user_id=portfolio_model.user_id,
        name=portfolio_model.name,
        created_at=portfolio_model.created_at,
        deleted_at=portfolio_model.deleted_at,
    )


@pytest.fixture
async def test_portfolios(
    db_session: AsyncSession, test_user: UserSchema
) -> list[PortfolioSchema]:
    """Create and persist two test portfolios for the test user."""
    portfolios = []
    for i in range(2):
        portfolio_model = PortfolioModel(
            id=uuid4(),
            user_id=test_user.id,
            name=f"Test Portfolio {i}",
            created_at=datetime.now(UTC),
            deleted_at=None,
        )
        db_session.add(portfolio_model)
        await db_session.flush()
        await db_session.refresh(portfolio_model)

        portfolios.append(
            PortfolioSchema(
                id=portfolio_model.id,
                user_id=portfolio_model.user_id,
                name=portfolio_model.name,
                created_at=portfolio_model.created_at,
                deleted_at=portfolio_model.deleted_at,
            )
        )

    await db_session.commit()
    return portfolios


@pytest.fixture
async def other_user_portfolio(
    db_session: AsyncSession, other_user: UserSchema
) -> PortfolioSchema:
    """Create and persist a portfolio owned by a different user."""
    portfolio_model = PortfolioModel(
        id=uuid4(),
        user_id=other_user.id,
        name="Other Portfolio",
        created_at=datetime.now(UTC),
        deleted_at=None,
    )

    db_session.add(portfolio_model)
    await db_session.commit()
    await db_session.refresh(portfolio_model)

    return PortfolioSchema(
        id=portfolio_model.id,
        user_id=portfolio_model.user_id,
        name=portfolio_model.name,
        created_at=portfolio_model.created_at,
        deleted_at=portfolio_model.deleted_at,
    )


@pytest.fixture
async def test_portfolio_with_accounts(
    db_session: AsyncSession,
    test_user: UserSchema,
    test_accounts: list[AccountSchema],
) -> PortfolioSchema:
    """Create and persist a test portfolio with accounts."""
    portfolio_model = PortfolioModel(
        id=uuid4(),
        user_id=test_user.id,
        name="Portfolio with Accounts",
        created_at=datetime.now(UTC),
        deleted_at=None,
    )
    db_session.add(portfolio_model)
    await db_session.flush()
    await db_session.refresh(portfolio_model)

    # Add account associations
    account_schemas = [
        PortfolioAccountSchema(account_id=acc.id)
        for acc in test_accounts[:2]  # Only use first 2 accounts
    ]

    for acc_schema in account_schemas:
        portfolio_account_model = PortfolioAccountModel(
            portfolio_id=portfolio_model.id,
            account_id=acc_schema.account_id,
        )
        db_session.add(portfolio_account_model)

    await db_session.commit()
    await db_session.refresh(portfolio_model)

    return PortfolioSchema(
        id=portfolio_model.id,
        user_id=portfolio_model.user_id,
        name=portfolio_model.name,
        created_at=portfolio_model.created_at,
        deleted_at=portfolio_model.deleted_at,
    )


# Position fixtures
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


# Integration user fixtures
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
