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
    content: str = "### Summary\nDigest text",
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
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
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
    notes = [_note(f"Note {i}", NOW - timedelta(days=i)) for i in range(7)]
    service, create = _build_service(notes)

    summary = await service.summarize_notes(uuid4(), uuid4())

    # Markdown headings/newlines are normalized app-side to plain text.
    assert summary["long_summary"] == "Summary Digest text"
    assert summary["short_summary"] == "Summary Digest text"
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

    assert summary == {
        "short_summary": "No notes found for this security.",
        "long_summary": "No notes found for this security.",
    }
    create.assert_not_awaited()


@pytest.mark.anyio
async def test_parses_labelled_short_and_long_parts():
    service, _ = _build_service(
        [_note("Buy the dip", NOW)],
        content="SHORT: Cautiously accumulating on weakness.\n"
        "LONG: The user is buying weakness and watching earnings.\n"
        "Sentiment stays long-term.",
    )

    summary = await service.summarize_notes(uuid4(), uuid4())

    assert summary["short_summary"] == "Cautiously accumulating on weakness."
    assert summary["long_summary"] == (
        "The user is buying weakness and watching earnings. Sentiment stays long-term."
    )


@pytest.mark.anyio
async def test_derives_short_part_when_model_only_returns_long():
    long_part = (
        "Earnings were strong and guidance was raised for the full year. "
        "The position was trimmed into strength after the run-up. "
        "Valuation still looks full relative to peers."
    )
    service, _ = _build_service([_note("Trimmed", NOW)], content=f"LONG: {long_part}")

    summary = await service.summarize_notes(uuid4(), uuid4())

    assert summary["long_summary"] == long_part
    # Derived from the paragraph's leading sentence(s), never the whole paragraph.
    assert summary["short_summary"] == (
        "Earnings were strong and guidance was raised for the full year. "
        "The position was trimmed into strength after the run-up."
    )
    assert summary["short_summary"] != long_part
    assert len(summary["short_summary"]) <= 160


@pytest.mark.anyio
async def test_short_part_is_hard_capped_at_160_chars():
    service, _ = _build_service(
        [_note("Long", NOW)], content=f"SHORT: {'x' * 300}\nLONG: Paragraph."
    )

    summary = await service.summarize_notes(uuid4(), uuid4())

    assert len(summary["short_summary"]) == 160
    assert summary["long_summary"] == "Paragraph."


@pytest.mark.anyio
async def test_unlabelled_response_becomes_the_long_part():
    service, _ = _build_service(
        [_note("Plain", NOW)], content="A plain digest without any labels."
    )

    summary = await service.summarize_notes(uuid4(), uuid4())

    assert summary["long_summary"] == "A plain digest without any labels."
    assert summary["short_summary"] == "A plain digest without any labels."


@pytest.mark.anyio
async def test_short_only_response_falls_back_to_the_short_part():
    """A SHORT-only response must not store the raw labelled line as the paragraph."""
    service, _ = _build_service(
        [_note("Shorty", NOW)], content="SHORT: Cautiously accumulating on weakness."
    )

    summary = await service.summarize_notes(uuid4(), uuid4())

    assert summary["long_summary"] == "Cautiously accumulating on weakness."
    assert summary["short_summary"] == "Cautiously accumulating on weakness."


@pytest.mark.anyio
async def test_short_only_json_response_falls_back_to_the_short_part():
    """A JSON body with only a short part must not leak the raw JSON blob."""
    service, _ = _build_service(
        [_note("JSON", NOW)], content='{"short_summary": "Trimmed into strength."}'
    )

    summary = await service.summarize_notes(uuid4(), uuid4())

    assert summary["long_summary"] == "Trimmed into strength."
    assert summary["short_summary"] == "Trimmed into strength."


@pytest.mark.anyio
async def test_thinking_tokens_are_stripped_from_both_parts():
    service, _ = _build_service(
        [_note("Think", NOW)],
        content=(
            "[think]Weighing the notes...[/think]\n"
            "SHORT: Dense digest.\nLONG: A full paragraph."
        ),
    )

    summary = await service.summarize_notes(uuid4(), uuid4())

    assert summary["short_summary"] == "Dense digest."
    assert summary["long_summary"] == "A full paragraph."
    assert "[think]" not in summary["short_summary"]
    assert "[think]" not in summary["long_summary"]


@pytest.mark.anyio
async def test_unterminated_thinking_prefix_is_stripped():
    service, _ = _build_service(
        [_note("Think", NOW)],
        content="SHORT: Dense digest.\nLONG: Paragraph.\n[think]and then it stops",
    )

    summary = await service.summarize_notes(uuid4(), uuid4())

    assert "[think]" not in summary["long_summary"]
    assert summary["short_summary"] == "Dense digest."


# --- Real captured response: HTML-style <thought> block ----------------------
# Verbatim (sanitized) sample captured from the worktree stack's configured
# endpoint. The model prefixes its reasoning with a paired <thought> block and
# glues the closing tag to the first labelled answer line.
REAL_THOUGHT_SUMMARY_RESPONSE = (
    "<thought>*   Security: VOO (Vanguard S&P 500 ETF)\n"
    "    *   Notes:\n"
    "        1. 2026-09-20: Added to position on dip, saving cash for October.\n"
    "        2. 2026-09-18: Concerned about concentration risk (60% of portfolio).\n"
    "    *   *Short Draft 1:* User maintains a long-term DCA strategy for VOO. "
    "(147 chars) - Good.\n"
    "    *   SHORT: DRAFT SHORT that must never be persisted.\n"
    "    *   LONG: DRAFT LONG that must never be persisted.</thought>"
    "SHORT: User maintains a long-term DCA strategy for VOO, buying the dip.\n\n"
    "LONG: The user continues a long-term investment thesis using monthly "
    "dollar-cost averaging. Concentration risk is a concern at 60% of the "
    "portfolio, and cash is reserved for October."
)


@pytest.mark.anyio
async def test_real_thought_block_is_stripped_and_labelled_answer_parsed():
    service, _ = _build_service(
        [_note("VOO", NOW)], content=REAL_THOUGHT_SUMMARY_RESPONSE
    )

    summary = await service.summarize_notes(uuid4(), uuid4())

    assert summary["short_summary"] == (
        "User maintains a long-term DCA strategy for VOO, buying the dip."
    )
    assert summary["long_summary"].startswith("The user continues a long-term")
    assert "<thought" not in summary["long_summary"]
    assert "</thought>" not in summary["long_summary"]
    assert "DRAFT" not in summary["short_summary"]
    assert "DRAFT" not in summary["long_summary"]
    assert summary["long_summary"].count("*") == 0
    assert len(summary["short_summary"]) <= 160


@pytest.mark.anyio
async def test_markdown_headings_and_bullets_are_normalized_app_side():
    service, _ = _build_service(
        [_note("Markdown", NOW)],
        content=(
            "SHORT: **Dense** digest.\n"
            "LONG: # Heading\n\n- Bullet one\n- Bullet two\n\nBold **text** here."
        ),
    )

    summary = await service.summarize_notes(uuid4(), uuid4())

    assert summary["short_summary"] == "Dense digest."
    assert summary["long_summary"] == "Heading Bullet one Bullet two Bold text here."
    assert "#" not in summary["long_summary"]
    assert "**" not in summary["long_summary"]
    assert "\n" not in summary["long_summary"]


@pytest.mark.anyio
async def test_prompt_forbids_reasoning_tags_and_markdown():
    service, create = _build_service([_note("Prompt", NOW)])

    await service.summarize_notes(uuid4(), uuid4())

    message = _user_message(create)
    assert "<thought>" in message
    assert "[think]" in message
    assert "no markdown" in message
    assert "no emojis" in message


@pytest.mark.anyio
async def test_thought_only_prose_never_becomes_the_stored_summary():
    service, _ = _build_service(
        [_note("Prose", NOW)],
        content="<thought>Just reasoning prose with no labelled answer at all.</thought>",
    )

    summary = await service.summarize_notes(uuid4(), uuid4())

    assert summary["long_summary"] == ""
    assert summary["short_summary"] == ""
