"""Tests for the note-summary huey task.

The AI service is fully stubbed and the svcs container is mocked, so no test
performs a network, Redis or SMTP call; the testcontainers Postgres session is
the only real infrastructure.
"""

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.api_types import UserId
from src.market.ai_service import AIService
from src.market.api_types import SecurityId
from src.market.model import SecurityModel
from src.market.repository import (
    SecurityNoteRepository,
    SecurityNoteSummaryRepository,
)
from src.market.repository_sqlalchemy import (
    SqlAlchemySecurityNoteRepository,
    SqlAlchemySecurityNoteSummaryRepository,
)
from src.market.schema import NoteSummaryWrite, SecurityNoteWrite
from src.market.task import _generate_note_summary, generate_note_summary_task
from src.worker import huey


@pytest.fixture
async def note_security(db_session: AsyncSession) -> SecurityModel:
    security = SecurityModel(
        id=uuid4(),
        symbol="AAPL",
        exchange="NASDAQ",
        currency="USD",
        name="Apple Inc",
        is_active=True,
    )
    db_session.add(security)
    await db_session.commit()
    return security


def _build_container(
    note_repository: SecurityNoteRepository,
    summary_repository: SecurityNoteSummaryRepository,
    ai_service: AIService,
) -> MagicMock:
    async def _aget(service_type: type) -> object:
        if service_type is SecurityNoteRepository:
            return note_repository
        if service_type is SecurityNoteSummaryRepository:
            return summary_repository
        if service_type is AIService:
            return ai_service
        raise ValueError(f"Unexpected service type: {service_type}")

    container = MagicMock()
    container.aget = AsyncMock(side_effect=_aget)
    container.__aenter__ = AsyncMock(return_value=container)
    container.__aexit__ = AsyncMock(return_value=None)
    return container


@contextmanager
def _task_environment(
    note_repository: SecurityNoteRepository,
    summary_repository: SecurityNoteSummaryRepository,
    ai_service: AIService,
) -> Iterator[MagicMock]:
    container = _build_container(note_repository, summary_repository, ai_service)
    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=container),
    ):
        yield container


async def _seed_note(
    repository: SecurityNoteRepository,
    security_id: SecurityId,
    user_id: UserId,
    content: str = "Consider adding on weakness",
) -> None:
    await repository.create(SecurityNoteWrite(content=content), security_id, user_id)


async def _seed_summary(
    repository: SecurityNoteSummaryRepository,
    security_id: SecurityId,
    user_id: UserId,
    text: str,
) -> None:
    await repository.upsert(
        NoteSummaryWrite(summary=text, generated_at=datetime.now(UTC)),
        security_id,
        user_id,
    )


@pytest.mark.anyio
async def test_generates_and_persists_summary(
    db_session: AsyncSession, note_security: SecurityModel
):
    user_id = uuid4()
    note_repository = SqlAlchemySecurityNoteRepository(db_session)
    summary_repository = SqlAlchemySecurityNoteSummaryRepository(db_session)
    await _seed_note(note_repository, note_security.id, user_id)

    ai_service = AsyncMock(spec=AIService)
    ai_service.summarize_notes.return_value = "Fresh digest"

    with _task_environment(note_repository, summary_repository, ai_service):
        await _generate_note_summary(note_security.id, user_id)

    ai_service.summarize_notes.assert_awaited_once_with(note_security.id, user_id)
    stored = await summary_repository.get(note_security.id, user_id)
    assert stored is not None
    assert stored.summary == "Fresh digest"
    assert stored.generated_at is not None
    # generated_at comes from the DB clock (func.now()), i.e. it is fresh
    assert abs((datetime.now(UTC) - stored.generated_at).total_seconds()) < 60


@pytest.mark.anyio
async def test_upsert_updates_existing_summary_row(
    db_session: AsyncSession, note_security: SecurityModel
):
    user_id = uuid4()
    note_repository = SqlAlchemySecurityNoteRepository(db_session)
    summary_repository = SqlAlchemySecurityNoteSummaryRepository(db_session)
    await _seed_note(note_repository, note_security.id, user_id)
    await _seed_summary(summary_repository, note_security.id, user_id, "Old digest")
    previous = await summary_repository.get(note_security.id, user_id)

    ai_service = AsyncMock(spec=AIService)
    ai_service.summarize_notes.return_value = "New digest"

    with _task_environment(note_repository, summary_repository, ai_service):
        await _generate_note_summary(note_security.id, user_id)

    stored = await summary_repository.get(note_security.id, user_id)
    assert stored is not None
    assert stored.summary == "New digest"
    assert previous is not None
    assert previous.generated_at is not None
    assert stored.generated_at is not None
    assert stored.generated_at > previous.generated_at


@pytest.mark.anyio
async def test_no_notes_clears_stored_summary_without_calling_ai(
    db_session: AsyncSession, note_security: SecurityModel
):
    user_id = uuid4()
    note_repository = SqlAlchemySecurityNoteRepository(db_session)
    summary_repository = SqlAlchemySecurityNoteSummaryRepository(db_session)
    await _seed_summary(summary_repository, note_security.id, user_id, "Stale digest")

    ai_service = AsyncMock(spec=AIService)

    with _task_environment(note_repository, summary_repository, ai_service):
        await _generate_note_summary(note_security.id, user_id)

    ai_service.summarize_notes.assert_not_awaited()
    assert await summary_repository.get(note_security.id, user_id) is None


@pytest.mark.anyio
async def test_zero_notes_for_other_user_does_not_touch_this_users_summary(
    db_session: AsyncSession, note_security: SecurityModel
):
    user_id = uuid4()
    other_user_id = uuid4()
    note_repository = SqlAlchemySecurityNoteRepository(db_session)
    summary_repository = SqlAlchemySecurityNoteSummaryRepository(db_session)
    await _seed_note(note_repository, note_security.id, other_user_id)
    await _seed_summary(summary_repository, note_security.id, user_id, "Mine")
    await _seed_summary(summary_repository, note_security.id, other_user_id, "Theirs")

    ai_service = AsyncMock(spec=AIService)

    with _task_environment(note_repository, summary_repository, ai_service):
        await _generate_note_summary(note_security.id, user_id)

    ai_service.summarize_notes.assert_not_awaited()
    assert await summary_repository.get(note_security.id, user_id) is None
    other = await summary_repository.get(note_security.id, other_user_id)
    assert other is not None
    assert other.summary == "Theirs"


@pytest.mark.anyio
async def test_ai_failure_is_logged_and_keeps_previous_summary(
    db_session: AsyncSession, note_security: SecurityModel
):
    user_id = uuid4()
    note_repository = SqlAlchemySecurityNoteRepository(db_session)
    summary_repository = SqlAlchemySecurityNoteSummaryRepository(db_session)
    await _seed_note(note_repository, note_security.id, user_id)
    await _seed_summary(summary_repository, note_security.id, user_id, "Previous")

    ai_service = AsyncMock(spec=AIService)
    ai_service.summarize_notes.side_effect = RuntimeError("AI service unavailable")

    with (
        _task_environment(note_repository, summary_repository, ai_service),
        patch("src.market.task.logger") as mock_logger,
    ):
        # must not raise out of the task body
        await _generate_note_summary(note_security.id, user_id)

    mock_logger.exception.assert_called_once()
    ai_service.summarize_notes.assert_awaited_once_with(note_security.id, user_id)
    stored = await summary_repository.get(note_security.id, user_id)
    assert stored is not None
    assert stored.summary == "Previous"


@pytest.mark.anyio
async def test_no_registry_returns_without_touching_anything(
    db_session: AsyncSession, note_security: SecurityModel
):
    ai_service = AsyncMock(spec=AIService)

    with patch("src.market.task.huey.svcs_registry", None):
        await _generate_note_summary(note_security.id, uuid4())

    ai_service.summarize_notes.assert_not_awaited()


def test_task_wrapper_runs_async_logic():
    previous_immediate = huey.immediate
    huey.immediate = True
    try:
        with patch("src.market.task.asyncio.run") as mock_run:
            generate_note_summary_task(uuid4(), uuid4())

            mock_run.assert_called_once()
            coroutine = mock_run.call_args[0][0]
            assert asyncio.iscoroutine(coroutine)
            coroutine.close()
    finally:
        huey.immediate = previous_immediate
