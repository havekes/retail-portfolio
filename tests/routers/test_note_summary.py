"""Tests for GET /market/securities/{security_id}/ai/notes-summary."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.api_types import UserId
from src.auth.schema import UserSchema
from src.main import app
from src.market.api_types import SecurityId
from src.market.model import SecurityModel
from src.market.repository import SecurityNoteSummaryRepository
from src.market.repository_sqlalchemy import SqlAlchemySecurityNoteSummaryRepository
from src.market.schema import NoteSummaryResponse, NoteSummaryWrite


@pytest.fixture
async def test_security(db_session: AsyncSession) -> SecurityModel:
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


@pytest.fixture
def mock_summary_repository() -> AsyncMock:
    return AsyncMock(spec=SecurityNoteSummaryRepository)


def _notes_summary_url(security_id: SecurityId) -> str:
    return f"/api/v1/market/securities/{security_id}/ai/notes-summary"


async def _store_summary(
    db_session: AsyncSession, security_id: SecurityId, user_id: UserId, text: str
) -> None:
    repository = SqlAlchemySecurityNoteSummaryRepository(db_session)
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
async def test_returns_persisted_summary_for_current_user(
    auth_client,
    db_session: AsyncSession,
    test_user: UserSchema,
    test_security: SecurityModel,
):
    await _store_summary(db_session, test_security.id, test_user.id, "Digest text")

    response = await auth_client.get(_notes_summary_url(test_security.id))

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["short_summary"] == "Digest text"
    assert data["long_summary"] == "Digest text"
    assert data["generated_at"] is not None


@pytest.mark.anyio
async def test_returns_nulls_when_nothing_generated(
    auth_client,
    test_security: SecurityModel,
):
    response = await auth_client.get(_notes_summary_url(test_security.id))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "short_summary": None,
        "long_summary": None,
        "generated_at": None,
    }


async def _store_raw_summary(
    db_session: AsyncSession,
    security_id: SecurityId,
    user_id: UserId,
    short: str,
    long: str,
) -> None:
    """Store an already-dirty summary row directly, emulating a legacy record."""
    repository = SqlAlchemySecurityNoteSummaryRepository(db_session)
    await repository.upsert(
        NoteSummaryWrite(
            short_summary=short,
            long_summary=long,
            generated_at=datetime.now(UTC),
        ),
        security_id,
        user_id,
    )


@pytest.mark.anyio
async def test_cleans_legacy_reasoning_markers_on_read(
    auth_client,
    db_session: AsyncSession,
    test_user: UserSchema,
    test_security: SecurityModel,
):
    """A legacy row with reasoning/markdown must render clean without a migration."""
    await _store_raw_summary(
        db_session,
        test_security.id,
        test_user.id,
        short="<thought>DRAFT</thought>Dense digest.",
        long=(
            "<thought>*   reasoning that must never render</thought>"
            "# Heading\n- Bullet\nReal paragraph with <think>inline</think> noise."
        ),
    )

    response = await auth_client.get(_notes_summary_url(test_security.id))

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["short_summary"] == "Dense digest."
    assert data["long_summary"] == "Heading Bullet Real paragraph with noise."
    assert "<thought" not in data["long_summary"]
    assert "</thought>" not in data["long_summary"]
    assert "#" not in data["long_summary"]


@pytest.mark.anyio
async def test_derives_short_digest_for_legacy_row_without_one(
    auth_client,
    db_session: AsyncSession,
    test_user: UserSchema,
    test_security: SecurityModel,
):
    await _store_raw_summary(
        db_session,
        test_security.id,
        test_user.id,
        short="",
        long="A clean long paragraph that has no short digest stored.",
    )

    response = await auth_client.get(_notes_summary_url(test_security.id))

    data = response.json()
    assert data["short_summary"] == "A clean long paragraph that has no short digest stored."
    assert data["long_summary"] == "A clean long paragraph that has no short digest stored."


@pytest.mark.anyio
async def test_returns_404_for_unknown_security(auth_client):
    response = await auth_client.get(_notes_summary_url(uuid4()))

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.anyio
async def test_scopes_lookup_to_current_user(
    auth_client,
    test_user: UserSchema,
    test_security: SecurityModel,
    mock_summary_repository: AsyncMock,
):
    mock_summary_repository.get.return_value = NoteSummaryResponse(
        short_summary="Scoped digest",
        long_summary="Scoped summary",
        generated_at=datetime.now(UTC),
    )
    app.state.svcs_registry.register_value(
        SecurityNoteSummaryRepository, mock_summary_repository
    )

    response = await auth_client.get(_notes_summary_url(test_security.id))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["long_summary"] == "Scoped summary"
    assert response.json()["short_summary"] == "Scoped digest"
    mock_summary_repository.get.assert_awaited_once_with(test_security.id, test_user.id)


@pytest.mark.anyio
async def test_does_not_leak_across_users_or_securities(
    auth_client,
    db_session: AsyncSession,
    test_user: UserSchema,
    other_user: UserSchema,
    test_security: SecurityModel,
):
    other_security = SecurityModel(
        id=uuid4(),
        symbol="MSFT",
        exchange="NASDAQ",
        currency="USD",
        name="Microsoft Corp",
        is_active=True,
    )
    db_session.add(other_security)
    await db_session.commit()

    await _store_summary(db_session, test_security.id, test_user.id, "Mine")
    await _store_summary(db_session, test_security.id, other_user.id, "Theirs")
    await _store_summary(db_session, other_security.id, test_user.id, "Other security")

    response = await auth_client.get(_notes_summary_url(test_security.id))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["long_summary"] == "Mine"

    response = await auth_client.get(_notes_summary_url(other_security.id))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["long_summary"] == "Other security"
