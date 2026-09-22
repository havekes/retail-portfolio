"""Prompt tests for the recency-weighted AIService.summarize_notes path.

The OpenAI client is stubbed: no test here performs a network call.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.market.ai_service import (
    RECENCY_WEIGHTING_INSTRUCTION,
    AIService,
)
from src.market.api_types import SecurityId
from src.market.repository import (
    PriceRepository,
    SecurityNoteRepository,
    SecurityRepository,
)
from src.market.schema import PriceSchema, SecurityNoteRead, SecuritySchema

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)


def _security(security_id: SecurityId) -> SecuritySchema:
    return SecuritySchema(
        id=security_id,
        symbol="AAPL",
        exchange="NASDAQ",
        currency="USD",
        name="Apple Inc",
        isin=None,
        is_active=True,
        updated_at=NOW,
        current_price=Decimal("190.00"),
    )


def _note(content: str, created_at: datetime) -> SecurityNoteRead:
    return SecurityNoteRead(
        id=1,
        security_id=uuid4(),
        user_id=uuid4(),
        title=None,
        content=content,
        created_at=created_at,
        updated_at=created_at,
    )


def _price(security_id: SecurityId, day: date, close: str) -> PriceSchema:
    value = Decimal(close)
    return PriceSchema(
        id=None,
        security_id=security_id,
        date=day,
        open=value,
        high=value,
        low=value,
        close=value,
        adjusted_close=value,
        volume=1000,
    )


def _build_service(
    notes: list[SecurityNoteRead],
) -> tuple[AIService, AsyncMock]:
    security_id = uuid4()
    security_repository = AsyncMock(spec=SecurityRepository)
    security_repository.get_by_id_or_fail.return_value = _security(security_id)

    price_repository = AsyncMock(spec=PriceRepository)
    price_repository.get_latest_price.return_value = _price(
        security_id, NOW.date(), "190.00"
    )
    price_repository.get_prices.return_value = (
        [_price(security_id, NOW.date(), "190.00")],
        1,
    )

    notes_repository = AsyncMock(spec=SecurityNoteRepository)
    notes_repository.get_by_security_and_user.return_value = (notes, len(notes))

    service = AIService(
        security_repository,
        price_repository,
        notes_repository,
        api_endpoint="https://ai.example.invalid/v1/chat/completions",
        api_key="test-key",
        api_model="test-model",
    )

    create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="### Summary\nDigest text")
                )
            ]
        )
    )
    client = MagicMock()
    client.chat.completions.create = create
    service._client = client

    return service, create


def _user_message(create: AsyncMock) -> str:
    messages = create.call_args.kwargs["messages"]
    return messages[1]["content"]


@pytest.mark.anyio
async def test_prompt_includes_every_note_with_timestamps_and_recency_instruction():
    notes = [
        _note(f"Note {i}", NOW - timedelta(days=i)) for i in range(7)
    ]
    service, create = _build_service(notes)

    summary = await service.summarize_notes(uuid4(), uuid4())

    assert summary == "### Summary\nDigest text"
    create.assert_awaited_once()

    message = _user_message(create)
    # (a) timestamps are present
    for note in notes:
        assert note.created_at.isoformat() in message
    # (b) the stable recency-weighting instruction is present
    assert RECENCY_WEIGHTING_INSTRUCTION in message
    assert "newest first" in message
    # every gathered note is rendered, not just the 5 most recent
    for note in notes:
        assert note.content in message


@pytest.mark.anyio
async def test_prompt_lists_notes_newest_first():
    newer = _note("Newer note", NOW)
    older = _note("Older note", NOW - timedelta(days=30))
    service, create = _build_service([newer, older])

    await service.summarize_notes(uuid4(), uuid4())

    message = _user_message(create)
    assert message.index("Newer note") < message.index("Older note")


@pytest.mark.anyio
async def test_no_notes_short_circuits_without_calling_the_api():
    service, create = _build_service([])

    summary = await service.summarize_notes(uuid4(), uuid4())

    assert summary == "No notes found for this security."
    create.assert_not_awaited()
