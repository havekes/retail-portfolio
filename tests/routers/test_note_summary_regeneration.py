"""End-to-end (HTTP) tests for background note-summary regeneration.

These run the huey task body with a stubbed AI service / svcs container, then
assert what the T02 GET endpoint serves — no network, Redis or SMTP involved.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.api_types import UserId
from src.auth.schema import UserSchema
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
from src.market.schema import SecurityNoteWrite
from src.market.task import _generate_note_summary


def _notes_summary_url(security_id: SecurityId) -> str:
    return f"/api/v1/market/securities/{security_id}/ai/notes-summary"


def _container(
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


async def _run_task(
    security_id: SecurityId,
    user_id: UserId,
    note_repository: SecurityNoteRepository,
    summary_repository: SecurityNoteSummaryRepository,
    ai_service: AIService,
) -> None:
    container = _container(note_repository, summary_repository, ai_service)
    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=container),
    ):
        await _generate_note_summary(security_id, user_id)


@pytest.mark.anyio
async def test_regenerated_summary_and_clearing_are_visible_through_get(
    auth_client,
    db_session: AsyncSession,
    test_user: UserSchema,
    test_security: SecurityModel,
):
    note_repository = SqlAlchemySecurityNoteRepository(db_session)
    summary_repository = SqlAlchemySecurityNoteSummaryRepository(db_session)
    note = await note_repository.create(
        SecurityNoteWrite(content="Adding on weakness"), test_security.id, test_user.id
    )

    ai_service = AsyncMock(spec=AIService)
    ai_service.summarize_notes.return_value = {
        "short_summary": "Regenerated digest",
        "long_summary": "Regenerated digest paragraph.",
    }

    await _run_task(
        test_security.id, test_user.id, note_repository, summary_repository, ai_service
    )

    response = await auth_client.get(_notes_summary_url(test_security.id))
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["short_summary"] == "Regenerated digest"
    assert body["long_summary"] == "Regenerated digest paragraph."
    assert body["generated_at"] is not None
    generated_at = datetime.fromisoformat(body["generated_at"])
    assert abs((datetime.now(UTC) - generated_at).total_seconds()) < 60

    # Last note removed → the task clears the stored summary without calling AI
    await note_repository.delete(note.id, test_user.id)
    await _run_task(
        test_security.id, test_user.id, note_repository, summary_repository, ai_service
    )

    response = await auth_client.get(_notes_summary_url(test_security.id))
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "short_summary": None,
        "long_summary": None,
        "generated_at": None,
    }
    assert ai_service.summarize_notes.await_count == 1


@pytest.mark.anyio
async def test_ai_failure_keeps_serving_the_previous_summary(
    auth_client,
    db_session: AsyncSession,
    test_user: UserSchema,
    test_security: SecurityModel,
):
    note_repository = SqlAlchemySecurityNoteRepository(db_session)
    summary_repository = SqlAlchemySecurityNoteSummaryRepository(db_session)
    await note_repository.create(
        SecurityNoteWrite(content="Existing note"), test_security.id, test_user.id
    )

    working_ai = AsyncMock(spec=AIService)
    working_ai.summarize_notes.return_value = {
        "short_summary": "First digest",
        "long_summary": "First digest paragraph.",
    }
    await _run_task(
        test_security.id, test_user.id, note_repository, summary_repository, working_ai
    )

    failing_ai = AsyncMock(spec=AIService)
    failing_ai.summarize_notes.side_effect = RuntimeError("AI service unavailable")
    await _run_task(
        test_security.id, test_user.id, note_repository, summary_repository, failing_ai
    )

    response = await auth_client.get(_notes_summary_url(test_security.id))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["long_summary"] == "First digest paragraph."


@pytest.mark.anyio
async def test_unknown_security_is_untouched(db_session: AsyncSession):
    """Regeneration for a security with no notes is a no-op, not an error."""
    summary_repository = SqlAlchemySecurityNoteSummaryRepository(db_session)
    note_repository = SqlAlchemySecurityNoteRepository(db_session)
    ai_service = AsyncMock(spec=AIService)

    await _run_task(uuid4(), uuid4(), note_repository, summary_repository, ai_service)

    ai_service.summarize_notes.assert_not_awaited()
