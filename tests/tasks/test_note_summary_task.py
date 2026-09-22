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
from src.market.schema import NoteSummaryWrite, SecurityNoteRead, SecurityNoteWrite
from src.market.task import (
    _generate_note_summary,
    generate_note_summary_task,
    mark_task_cancelled,
)
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
) -> SecurityNoteRead:
    return await repository.create(
        SecurityNoteWrite(content=content), security_id, user_id
    )


async def _seed_summary(
    repository: SecurityNoteSummaryRepository,
    security_id: SecurityId,
    user_id: UserId,
    text: str,
) -> None:
    await repository.upsert(
        NoteSummaryWrite(
            short_summary=text[:160],
            long_summary=text,
            generated_at=datetime.now(UTC),
        ),
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
    ai_service.summarize_notes.return_value = {
        "short_summary": "Fresh digest",
        "long_summary": "Fresh digest paragraph.",
    }

    with _task_environment(note_repository, summary_repository, ai_service):
        await _generate_note_summary(note_security.id, user_id)

    ai_service.summarize_notes.assert_awaited_once_with(note_security.id, user_id)
    stored = await summary_repository.get(note_security.id, user_id)
    assert stored is not None
    assert stored.short_summary == "Fresh digest"
    assert stored.long_summary == "Fresh digest paragraph."
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
    ai_service.summarize_notes.return_value = {
        "short_summary": "New digest",
        "long_summary": "New digest paragraph.",
    }

    with _task_environment(note_repository, summary_repository, ai_service):
        await _generate_note_summary(note_security.id, user_id)

    stored = await summary_repository.get(note_security.id, user_id)
    assert stored is not None
    assert stored.short_summary == "New digest"
    assert stored.long_summary == "New digest paragraph."
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
    assert other.long_summary == "Theirs"


@pytest.mark.anyio
async def test_empty_summary_parts_keep_previous_summary_and_skip_upsert(
    db_session: AsyncSession,
    note_security: SecurityModel,
    caplog: pytest.LogCaptureFixture,
):
    """A thought-only response cleans to empty parts; the good row must survive."""
    user_id = uuid4()
    note_repository = SqlAlchemySecurityNoteRepository(db_session)
    summary_repository = SqlAlchemySecurityNoteSummaryRepository(db_session)
    await _seed_note(note_repository, note_security.id, user_id)
    await _seed_summary(summary_repository, note_security.id, user_id, "Good digest")
    previous = await summary_repository.get(note_security.id, user_id)

    # The configured model's thought-only response parses to two empty parts.
    empty_parts = AIService._parse_summary_parts(
        "<thought>Only reasoning, no answer at all</thought>"
    )
    assert empty_parts == {"short_summary": "", "long_summary": ""}

    ai_service = AsyncMock(spec=AIService)
    ai_service.summarize_notes.return_value = empty_parts

    with (
        _task_environment(note_repository, summary_repository, ai_service),
        caplog.at_level("WARNING"),
    ):
        await _generate_note_summary(note_security.id, user_id)

    ai_service.summarize_notes.assert_awaited_once_with(note_security.id, user_id)
    stored = await summary_repository.get(note_security.id, user_id)
    assert stored is not None
    assert stored.short_summary == "Good digest"
    assert stored.long_summary == "Good digest"
    assert previous is not None
    assert stored.generated_at == previous.generated_at
    assert "Empty summary parts" in caplog.text
    assert "keeping previous summary" in caplog.text


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
    assert stored.long_summary == "Previous"


@pytest.mark.anyio
async def test_no_registry_returns_without_touching_anything(
    db_session: AsyncSession, note_security: SecurityModel
):
    ai_service = AsyncMock(spec=AIService)

    with patch("src.market.task.huey.svcs_registry", None):
        await _generate_note_summary(note_security.id, uuid4())

    ai_service.summarize_notes.assert_not_awaited()


@pytest.mark.anyio
async def test_notes_deleted_during_ai_call_discards_result_and_clears_summary(
    db_session: AsyncSession,
    note_security: SecurityModel,
    caplog: pytest.LogCaptureFixture,
):
    """Delete-DURING the AI call: no upsert, stored summary cleared, INFO log."""
    user_id = uuid4()
    note_repository = SqlAlchemySecurityNoteRepository(db_session)
    summary_repository = SqlAlchemySecurityNoteSummaryRepository(db_session)
    note = await _seed_note(note_repository, note_security.id, user_id)
    assert note is not None
    await _seed_summary(summary_repository, note_security.id, user_id, "Stale digest")

    ai_service = AsyncMock(spec=AIService)
    ai_service.summarize_notes.return_value = {
        "short_summary": "Late digest",
        "long_summary": "Late digest paragraph.",
    }

    original_get = note_repository.get_by_security_and_user
    calls = {"n": 0}

    async def _get_then_delete(
        security_id: SecurityId, uid: UserId, offset: int = 0, limit: int = 50
    ):
        calls["n"] += 1
        if calls["n"] > 1:
            await note_repository.delete(note.id, user_id)
        return await original_get(security_id, uid, offset=offset, limit=limit)

    with (
        _task_environment(note_repository, summary_repository, ai_service),
        patch.object(
            note_repository, "get_by_security_and_user", side_effect=_get_then_delete
        ),
        patch.object(summary_repository, "upsert", new=AsyncMock()) as mock_upsert,
        caplog.at_level("INFO"),
    ):
        await _generate_note_summary(note_security.id, user_id)

    ai_service.summarize_notes.assert_awaited_once()
    mock_upsert.assert_not_awaited()
    assert await summary_repository.get(note_security.id, user_id) is None
    assert "Discarded note summary" in caplog.text
    assert "cleared stored summary — notes deleted during generation" in caplog.text


@pytest.mark.anyio
async def test_notes_still_present_after_ai_call_persists_summary(
    db_session: AsyncSession, note_security: SecurityModel
):
    """Normal path unchanged: the post-AI re-check passes and the row is written."""
    user_id = uuid4()
    note_repository = SqlAlchemySecurityNoteRepository(db_session)
    summary_repository = SqlAlchemySecurityNoteSummaryRepository(db_session)
    await _seed_note(note_repository, note_security.id, user_id)

    ai_service = AsyncMock(spec=AIService)
    ai_service.summarize_notes.return_value = {
        "short_summary": "Fresh digest",
        "long_summary": "Fresh digest paragraph.",
    }

    with _task_environment(note_repository, summary_repository, ai_service):
        await _generate_note_summary(note_security.id, user_id)

    stored = await summary_repository.get(note_security.id, user_id)
    assert stored is not None
    assert stored.long_summary == "Fresh digest paragraph."


@pytest.mark.anyio
async def test_mark_task_cancelled_writes_cancelled_row() -> None:
    db = AsyncMock()

    await mark_task_cancelled(db, "task-1", "generate_note_title_task", "note deleted")

    db.upsert_task.assert_awaited_once()
    info = db.upsert_task.await_args.args[0]
    assert info.id == "task-1"
    assert info.name == "generate_note_title_task"
    assert info.status == "cancelled"
    assert info.error == "note deleted"
    assert info.timestamp is not None


@pytest.mark.anyio
async def test_mark_task_cancelled_swallows_dashboard_errors() -> None:
    db = AsyncMock()
    db.upsert_task.side_effect = RuntimeError("dashboard db down")

    # must not raise: dashboard bookkeeping never breaks a request
    await mark_task_cancelled(db, "task-1", "generate_note_title_task", "note deleted")


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
