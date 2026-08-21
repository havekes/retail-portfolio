# ruff: noqa: ARG001, PT019
"""Tests for PriceAlertRepository SQLAlchemy implementation."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.market.model import PriceAlertModel, SecurityModel
from src.market.repository_sqlalchemy import SqlAlchemyPriceAlertRepository
from src.market.schema import PriceAlertWrite


@pytest.fixture
async def _test_security(db_session: AsyncSession, seed_reference_data: None):
    """Create a security for alert tests."""
    sec_id = uuid4()
    sec = SecurityModel(
        id=sec_id,
        symbol="TEST",
        name="Test Corp",
        exchange="NASDAQ",
        currency="USD",
        is_active=True,
    )
    db_session.add(sec)
    await db_session.commit()
    return sec


@pytest.fixture
async def _test_user_id():
    """Return a fake user UUID for alert tests."""
    return uuid4()


@pytest.fixture
async def active_alert(
    db_session: AsyncSession,
    _test_security: SecurityModel,
    _test_user_id,
):
    """Create an active (not triggered) price alert."""
    alert = PriceAlertModel(
        security_id=_test_security.id,
        user_id=_test_user_id,
        target_price=Decimal("100.00"),
        condition="above",
        triggered_at=None,
        created_at=datetime.now(UTC),
    )
    db_session.add(alert)
    await db_session.commit()
    await db_session.refresh(alert)
    return alert


@pytest.fixture
async def triggered_alert(
    db_session: AsyncSession,
    _test_security: SecurityModel,
    _test_user_id,
):
    """Create a triggered price alert."""
    alert = PriceAlertModel(
        security_id=_test_security.id,
        user_id=_test_user_id,
        target_price=Decimal("90.00"),
        condition="below",
        triggered_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    db_session.add(alert)
    await db_session.commit()
    await db_session.refresh(alert)
    return alert


@pytest.fixture
def repo(db_session: AsyncSession):
    """Provide the SQLAlchemy price alert repository."""
    return SqlAlchemyPriceAlertRepository(session=db_session)


@pytest.mark.anyio
async def test_get_active_alerts_for_evaluation_returns_only_untriggered(
    repo,
    active_alert,
    triggered_alert,
):
    """Only alerts with triggered_at IS NULL are returned."""
    result = await repo.get_active_alerts_for_evaluation()
    alert_ids = {a.alert_id for a in result}
    assert active_alert.id in alert_ids
    assert triggered_alert.id not in alert_ids


@pytest.mark.anyio
async def test_get_active_alerts_for_evaluation_includes_security_info(
    repo,
    active_alert,
    _test_security,
):
    """The evaluation schema carries security symbol and name."""
    result = await repo.get_active_alerts_for_evaluation()
    matching = [a for a in result if a.alert_id == active_alert.id]
    assert len(matching) == 1
    ev = matching[0]
    assert ev.security_symbol == _test_security.symbol
    assert ev.security_name == _test_security.name
    assert ev.target_price == active_alert.target_price
    assert ev.condition == active_alert.condition


@pytest.mark.anyio
async def test_get_active_alerts_for_evaluation_empty_when_none_exist(repo):
    """Returns empty list when no alerts exist."""
    result = await repo.get_active_alerts_for_evaluation()
    assert result == []


@pytest.mark.anyio
async def test_mark_triggered_sets_timestamp(
    repo,
    active_alert,
):
    """mark_triggered sets triggered_at to the provided datetime."""
    trigger_ts = datetime(2026, 7, 15, 10, 30, 0, tzinfo=UTC)
    await repo.mark_triggered(active_alert.id, trigger_ts)

    refreshed = await repo.get_by_id(active_alert.id)
    assert refreshed is not None
    assert refreshed.triggered_at == trigger_ts


@pytest.mark.anyio
async def test_mark_triggered_does_not_affect_other_alerts(
    db_session,
    _test_security,
    _test_user_id,
):
    """mark_triggered only updates the targeted alert."""
    other = PriceAlertModel(
        security_id=_test_security.id,
        user_id=_test_user_id,
        target_price=Decimal("200.00"),
        condition="above",
        triggered_at=None,
        created_at=datetime.now(UTC),
    )
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)

    repo = SqlAlchemyPriceAlertRepository(session=db_session)
    trigger_ts = datetime.now(UTC)
    await repo.mark_triggered(other.id, trigger_ts)

    # other is now triggered
    refreshed = await repo.get_by_id(other.id)
    assert refreshed is not None
    assert refreshed.triggered_at == trigger_ts


@pytest.mark.anyio
async def test_get_by_id_returns_none_for_missing(repo):
    """get_by_id returns None for non-existent alert."""
    result = await repo.get_by_id(99999)
    assert result is None


@pytest.mark.anyio
async def test_get_by_id_returns_full_alert(
    repo,
    active_alert,
):
    """get_by_id returns all fields including triggered_at."""
    result = await repo.get_by_id(active_alert.id)
    assert result is not None
    assert result.id == active_alert.id
    assert result.triggered_at is None
    assert result.target_price == active_alert.target_price


@pytest.mark.anyio
async def test_create_persists_wave_source(
    repo,
    _test_security,
    _test_user_id,
):
    """create with source='wave' round-trips via get_by_id."""
    created = await repo.create(
        PriceAlertWrite(
            target_price=Decimal("100.00"),
            condition="above",
            source="wave",
        ),
        security_id=_test_security.id,
        user_id=_test_user_id,
    )
    assert created.source == "wave"
    persisted = await repo.get_by_id(created.id)
    assert persisted is not None
    assert persisted.source == "wave"


@pytest.mark.anyio
async def test_create_defaults_to_manual_source(
    repo,
    _test_security,
    _test_user_id,
):
    """create without source defaults to 'manual'."""
    created = await repo.create(
        PriceAlertWrite(
            target_price=Decimal("100.00"),
            condition="above",
        ),
        security_id=_test_security.id,
        user_id=_test_user_id,
    )
    assert created.source == "manual"
    persisted = await repo.get_by_id(created.id)
    assert persisted is not None
    assert persisted.source == "manual"
