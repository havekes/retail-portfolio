import pytest
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.account.api.position import PositionApi
from src.account.api_types import Position
from src.account.model import PositionModel
from src.account.repository_sqlalchemy import SqlAlchemyPositionRepository

@pytest.mark.anyio
async def test_position_api_create_persists_positions(
    db_session: AsyncSession, 
    test_account, 
    test_security
):
    """
    Test that PositionApi.create correctly persists positions to the database.
    """
    repo = SqlAlchemyPositionRepository(db_session)
    api = PositionApi(repo)

    positions = [
        Position(
            account_id=test_account.id,
            security_id=test_security.id,
            quantity=Decimal("10.0"),
            average_cost=Decimal("150.0"),
        ),
        Position(
            account_id=test_account.id,
            security_id=uuid4(), # different security
            quantity=Decimal("5.0"),
            average_cost=Decimal("200.0"),
        ),
    ]

    await api.create(positions)

    # Verify persistence
    result = await db_session.execute(
        select(PositionModel).where(PositionModel.account_id == test_account.id)
    )
    saved_positions = result.scalars().all()
    
    assert len(saved_positions) == 2
    assert any(p.quantity == Decimal("10.0") for p in saved_positions)
    assert any(p.quantity == Decimal("5.0") for p in saved_positions)

@pytest.mark.anyio
async def test_position_api_create_syncs_multiple_accounts(
    db_session: AsyncSession, 
    test_accounts, 
    test_security
):
    """
    Test that PositionApi.create correctly groups and syncs positions for multiple accounts.
    """
    repo = SqlAlchemyPositionRepository(db_session)
    api = PositionApi(repo)

    # Create positions for two different accounts
    positions = [
        Position(
            account_id=test_accounts[0].id,
            security_id=test_security.id,
            quantity=Decimal("10.0"),
            average_cost=Decimal("150.0"),
        ),
        Position(
            account_id=test_accounts[1].id,
            security_id=test_security.id,
            quantity=Decimal("20.0"),
            average_cost=Decimal("160.0"),
        ),
    ]

    await api.create(positions)

    # Verify first account
    res1 = await db_session.execute(
        select(PositionModel).where(PositionModel.account_id == test_accounts[0].id)
    )
    assert len(res1.scalars().all()) == 1

    # Verify second account
    res2 = await db_session.execute(
        select(PositionModel).where(PositionModel.account_id == test_accounts[1].id)
    )
    assert len(res2.scalars().all()) == 1

@pytest.mark.anyio
async def test_position_api_create_overwrites_existing_positions(
    db_session: AsyncSession, 
    test_account, 
    test_security
):
    """
    Test that PositionApi.create (via sync_by_account) replaces existing positions for an account.
    """
    repo = SqlAlchemyPositionRepository(db_session)
    api = PositionApi(repo)

    # Initial position
    initial_positions = [
        Position(
            account_id=test_account.id,
            security_id=test_security.id,
            quantity=Decimal("10.0"),
            average_cost=Decimal("150.0"),
        ),
    ]
    await api.create(initial_positions)

    # New positions for the same account
    new_positions = [
        Position(
            account_id=test_account.id,
            security_id=test_security.id,
            quantity=Decimal("15.0"),
            average_cost=Decimal("155.0"),
        ),
    ]
    await api.create(new_positions)

    # Verify only the latest position exists
    result = await db_session.execute(
        select(PositionModel).where(PositionModel.account_id == test_account.id)
    )
    saved = result.scalars().all()
    assert len(saved) == 1
    assert saved[0].quantity == Decimal("15.0")
