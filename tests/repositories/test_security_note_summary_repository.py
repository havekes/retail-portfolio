"""Repository tests for the persisted note summary (market_security_note_summaries)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.market.model import SecurityModel, SecurityNoteSummaryModel
from src.market.repository_sqlalchemy import SqlAlchemySecurityNoteSummaryRepository
from src.market.schema import NoteSummaryWrite


def _summary_write(text: str) -> NoteSummaryWrite:
    return NoteSummaryWrite(summary=text, generated_at=datetime.now(UTC))


async def _create_security(
    db_session: AsyncSession, symbol: str = "AAPL", exchange: str = "NASDAQ"
) -> SecurityModel:
    security = SecurityModel(
        id=uuid4(),
        symbol=symbol,
        exchange=exchange,
        currency="USD",
        name=f"{symbol} Inc",
        is_active=True,
    )
    db_session.add(security)
    await db_session.commit()
    return security


@pytest.mark.anyio
async def test_get_returns_none_when_no_summary_exists(db_session: AsyncSession):
    security = await _create_security(db_session)
    repository = SqlAlchemySecurityNoteSummaryRepository(db_session)

    assert await repository.get(security.id, uuid4()) is None


@pytest.mark.anyio
async def test_upsert_persists_summary_and_get_returns_it(db_session: AsyncSession):
    security = await _create_security(db_session)
    user_id = uuid4()
    repository = SqlAlchemySecurityNoteSummaryRepository(db_session)

    created = await repository.upsert(
        _summary_write("First summary"), security.id, user_id
    )
    assert created.summary == "First summary"
    assert created.generated_at is not None

    fetched = await repository.get(security.id, user_id)
    assert fetched is not None
    assert fetched.summary == "First summary"
    assert fetched.generated_at is not None
    assert fetched.generated_at == created.generated_at


@pytest.mark.anyio
async def test_upsert_updates_existing_row_in_place(db_session: AsyncSession):
    security = await _create_security(db_session)
    user_id = uuid4()
    repository = SqlAlchemySecurityNoteSummaryRepository(db_session)

    first = await repository.upsert(
        _summary_write("First summary"), security.id, user_id
    )
    second = await repository.upsert(
        _summary_write("Second summary"), security.id, user_id
    )

    assert second.summary == "Second summary"
    assert second.generated_at is not None
    assert first.generated_at is not None
    assert second.generated_at >= first.generated_at

    row_count = await db_session.scalar(
        select(func.count())
        .select_from(SecurityNoteSummaryModel)
        .where(SecurityNoteSummaryModel.security_id == security.id)
        .where(SecurityNoteSummaryModel.user_id == user_id)
    )
    assert row_count == 1

    fetched = await repository.get(security.id, user_id)
    assert fetched is not None
    assert fetched.summary == "Second summary"


@pytest.mark.anyio
async def test_get_is_scoped_to_user(db_session: AsyncSession):
    security = await _create_security(db_session)
    user_id = uuid4()
    other_user_id = uuid4()
    repository = SqlAlchemySecurityNoteSummaryRepository(db_session)

    await repository.upsert(_summary_write("Mine"), security.id, user_id)
    await repository.upsert(_summary_write("Theirs"), security.id, other_user_id)

    mine = await repository.get(security.id, user_id)
    theirs = await repository.get(security.id, other_user_id)

    assert mine is not None
    assert mine.summary == "Mine"
    assert theirs is not None
    assert theirs.summary == "Theirs"


@pytest.mark.anyio
async def test_get_is_scoped_to_security(db_session: AsyncSession):
    security = await _create_security(db_session, symbol="AAPL")
    other_security = await _create_security(db_session, symbol="MSFT")
    user_id = uuid4()
    repository = SqlAlchemySecurityNoteSummaryRepository(db_session)

    await repository.upsert(_summary_write("AAPL summary"), security.id, user_id)
    await repository.upsert(_summary_write("MSFT summary"), other_security.id, user_id)

    aapl = await repository.get(security.id, user_id)
    msft = await repository.get(other_security.id, user_id)

    assert aapl is not None
    assert aapl.summary == "AAPL summary"
    assert msft is not None
    assert msft.summary == "MSFT summary"


@pytest.mark.anyio
async def test_deleting_security_cascades_to_summaries(db_session: AsyncSession):
    security = await _create_security(db_session)
    user_id = uuid4()
    repository = SqlAlchemySecurityNoteSummaryRepository(db_session)

    await repository.upsert(_summary_write("Summary"), security.id, user_id)

    await db_session.execute(
        delete(SecurityModel).where(SecurityModel.id == security.id)
    )
    await db_session.commit()

    assert await repository.get(security.id, user_id) is None


@pytest.mark.anyio
async def test_delete_removes_only_the_requested_summary(db_session: AsyncSession):
    security = await _create_security(db_session)
    user_id = uuid4()
    other_user_id = uuid4()
    repository = SqlAlchemySecurityNoteSummaryRepository(db_session)

    await repository.upsert(_summary_write("Mine"), security.id, user_id)
    await repository.upsert(_summary_write("Theirs"), security.id, other_user_id)

    await repository.delete(security.id, user_id)

    assert await repository.get(security.id, user_id) is None
    theirs = await repository.get(security.id, other_user_id)
    assert theirs is not None
    assert theirs.summary == "Theirs"


@pytest.mark.anyio
async def test_delete_is_a_noop_when_no_summary_exists(db_session: AsyncSession):
    security = await _create_security(db_session)
    repository = SqlAlchemySecurityNoteSummaryRepository(db_session)

    await repository.delete(security.id, uuid4())

    assert await repository.get(security.id, uuid4()) is None
