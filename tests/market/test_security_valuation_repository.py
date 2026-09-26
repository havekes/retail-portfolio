# ruff: noqa: ARG001, PT019
"""Tests for SecurityValuationRepository SQLAlchemy implementation."""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.market.model import SecurityModel
from src.market.repository_sqlalchemy import SqlAlchemySecurityValuationRepository
from src.market.schema import SecurityValuationWrite


@pytest.fixture
async def _test_security(db_session: AsyncSession, seed_reference_data: None):
    """Create a security for valuation tests."""
    sec_id = uuid4()
    sec = SecurityModel(
        id=sec_id,
        symbol="VALTEST",
        name="Valuation Test Corp",
        exchange="NASDAQ",
        currency="USD",
        is_active=True,
    )
    db_session.add(sec)
    await db_session.commit()
    return sec


@pytest.fixture
async def _test_security_2(db_session: AsyncSession, seed_reference_data: None):
    """Create a second security for batch tests."""
    sec_id = uuid4()
    sec = SecurityModel(
        id=sec_id,
        symbol="VALTEST2",
        name="Valuation Test Corp 2",
        exchange="NASDAQ",
        currency="USD",
        is_active=True,
    )
    db_session.add(sec)
    await db_session.commit()
    return sec


@pytest.fixture
def repo(db_session: AsyncSession) -> SqlAlchemySecurityValuationRepository:
    return SqlAlchemySecurityValuationRepository(db_session)


@pytest.mark.anyio
async def test_get_by_security_and_user_not_found(
    repo: SqlAlchemySecurityValuationRepository,
    _test_security: SecurityModel,
):
    user_id = uuid4()
    result = await repo.get_by_security_and_user(_test_security.id, user_id)
    assert result is None


@pytest.mark.anyio
async def test_upsert_and_get_valuation(
    repo: SqlAlchemySecurityValuationRepository,
    _test_security: SecurityModel,
):
    user_id = uuid4()
    val = SecurityValuationWrite(
        lower_bound=Decimal("50.00"),
        upper_bound=Decimal("75.50"),
    )

    created = await repo.upsert(val, _test_security.id, user_id)
    assert created.user_id == user_id
    assert created.security_id == _test_security.id
    assert created.lower_bound == Decimal("50.00")
    assert created.upper_bound == Decimal("75.50")
    assert created.id is not None
    assert created.created_at is not None
    assert created.updated_at is not None

    fetched = await repo.get_by_security_and_user(_test_security.id, user_id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.lower_bound == Decimal("50.00")
    assert fetched.upper_bound == Decimal("75.50")


@pytest.mark.anyio
async def test_upsert_updates_existing(
    repo: SqlAlchemySecurityValuationRepository,
    _test_security: SecurityModel,
):
    user_id = uuid4()
    val1 = SecurityValuationWrite(
        lower_bound=Decimal("50.00"),
        upper_bound=Decimal("75.50"),
    )
    created = await repo.upsert(val1, _test_security.id, user_id)

    val2 = SecurityValuationWrite(
        lower_bound=Decimal("60.00"),
        upper_bound=Decimal("90.00"),
    )
    updated = await repo.upsert(val2, _test_security.id, user_id)
    assert updated.id == created.id
    assert updated.lower_bound == Decimal("60.00")
    assert updated.upper_bound == Decimal("90.00")

    fetched = await repo.get_by_security_and_user(_test_security.id, user_id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.lower_bound == Decimal("60.00")
    assert fetched.upper_bound == Decimal("90.00")


@pytest.mark.anyio
async def test_batch_valuations(
    repo: SqlAlchemySecurityValuationRepository,
    _test_security: SecurityModel,
    _test_security_2: SecurityModel,
):
    user_id = uuid4()
    other_user = uuid4()

    await repo.upsert(
        SecurityValuationWrite(lower_bound=Decimal("10.0"), upper_bound=Decimal("20.0")),
        _test_security.id,
        user_id,
    )
    await repo.upsert(
        SecurityValuationWrite(lower_bound=Decimal("30.0"), upper_bound=Decimal("40.0")),
        _test_security_2.id,
        user_id,
    )
    # Other user valuation
    await repo.upsert(
        SecurityValuationWrite(lower_bound=Decimal("99.0"), upper_bound=Decimal("100.0")),
        _test_security.id,
        other_user,
    )

    batch = await repo.get_batch_by_user_and_securities(
        [_test_security.id, _test_security_2.id], user_id
    )
    assert len(batch) == 2
    sec_ids = {b.security_id for b in batch}
    assert sec_ids == {_test_security.id, _test_security_2.id}

    # Empty batch returns empty list
    empty = await repo.get_batch_by_user_and_securities([], user_id)
    assert empty == []
