"""Unit tests for the combined per-note title + summary AI call.

The OpenAI client is stubbed: no test here performs a network call.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.market.ai_service import MAX_TITLE_LENGTH, AIService
from src.market.repository import (
    PriceRepository,
    SecurityNoteRepository,
    SecurityRepository,
)


def _build_service(content: str | None = None) -> tuple[AIService, AsyncMock]:
    service = AIService(
        AsyncMock(spec=SecurityRepository),
        AsyncMock(spec=PriceRepository),
        AsyncMock(spec=SecurityNoteRepository),
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


@pytest.mark.anyio
async def test_parses_tagged_title_and_summary_in_one_call():
    service, create = _build_service(
        "TITLE: Earnings beat expectations\n"
        "SUMMARY: The company beat earnings estimates and raised margin guidance."
    )

    title, summary = await service.generate_note_title_and_summary("Some note body")

    assert title == "Earnings beat expectations"
    assert summary == "The company beat earnings estimates and raised margin guidance."
    create.assert_awaited_once()
    # The combined call uses the configured model, not a hard-coded one.
    assert create.call_args.kwargs["model"] == "test-model"


@pytest.mark.anyio
async def test_parses_json_response_tolerantly():
    service, _ = _build_service(
        '{"title": "Margin guidance", "summary": "Guidance was raised."}'
    )

    title, summary = await service.generate_note_title_and_summary("Some note body")

    assert title == "Margin guidance"
    assert summary == "Guidance was raised."


@pytest.mark.anyio
async def test_unparsed_summary_falls_back_to_title_only():
    service, _ = _build_service("Just a bare title line")

    title, summary = await service.generate_note_title_and_summary("Some note body")

    assert title == "Just a bare title line"
    assert summary is None


@pytest.mark.anyio
async def test_ai_failure_falls_back_to_content_title_without_summary():
    service, create = _build_service()
    create.side_effect = RuntimeError("ai down")

    long_content = "x" * 200
    title, summary = await service.generate_note_title_and_summary(long_content)

    assert title == long_content[: MAX_TITLE_LENGTH - 3] + "..."
    assert summary is None


@pytest.mark.anyio
async def test_blank_response_falls_back_without_summary():
    service, _ = _build_service("   ")

    title, summary = await service.generate_note_title_and_summary("Short note")

    assert title == "Short note"
    assert summary is None


@pytest.mark.anyio
async def test_thinking_tokens_are_stripped_before_parsing():
    service, _ = _build_service(
        "[think]Let me reason about this note...[/think]\n"
        "TITLE: Earnings beat\n"
        "SUMMARY: The company beat earnings and raised guidance."
    )

    title, summary = await service.generate_note_title_and_summary("Some note body")

    assert title == "Earnings beat"
    assert summary == "The company beat earnings and raised guidance."
    assert "[think]" not in title
    assert summary is not None
    assert "[think]" not in summary


@pytest.mark.anyio
async def test_unterminated_thinking_prefix_swallows_the_tagged_lines():
    """A truncated `[think]` prefix must never leak; title falls back, no summary."""
    service, _ = _build_service(
        "TITLE: Real title\nSUMMARY: Real summary.\n[think]and generation stops here"
    )

    title, summary = await service.generate_note_title_and_summary("Some note body")

    # Everything from `[think]` onward is reasoning, but the tagged lines before
    # it still parse (the strip only cuts at the opening tag).
    assert title == "Real title"
    assert summary == "Real summary."


@pytest.mark.anyio
async def test_whole_response_is_thinking_falls_back_to_content_title():
    service, _ = _build_service("[think]Only reasoning, no answer at all")

    title, summary = await service.generate_note_title_and_summary("Actual content")

    assert title == "Actual content"
    assert summary is None


@pytest.mark.anyio
async def test_generate_note_title_delegates_to_combined_call():
    service, create = _build_service("TITLE: Delegated title\nSUMMARY: A sentence.")

    title = await service.generate_note_title("Some note body")

    assert title == "Delegated title"
    create.assert_awaited_once()


# --- Real captured responses ------------------------------------------------
# Verbatim (sanitized) samples captured from the worktree stack's configured
# endpoint. The per-note call used to budget 120 tokens and 10 seconds; the
# model spends both on its reasoning first.
REAL_ANSWERLESS_THOUGHT_RESPONSE = (
    "<thought>*   Input: A short note about investing in VOO (S&P 500 ETF).\n"
    "    *   Key points: Added to VOO on a dip, holding cash for October.\n"
    "    *   Constraint 1: Short title (max 50 chars).\n"
    "    *   Constraint 2: One-sentence summary.\n"
    "    </thought>"
)

REAL_THOUGHT_GLUED_TO_TITLE_RESPONSE = (
    "<thought>*   Input text: Bought more VOO on the dip.\n"
    "    *   Goal: Short title and one-sentence summary.</thought>"
    "TITLE: VOO Position Update\n"
    "SUMMARY: Increased VOO holdings during a dip while managing "
    "concentration risk through dollar cost averaging."
)


@pytest.mark.anyio
async def test_answerless_thought_block_never_leaks_into_the_title():
    """The old 120-token budget produced a thought-only response (real sample)."""
    service, _ = _build_service(REAL_ANSWERLESS_THOUGHT_RESPONSE)

    title, summary = await service.generate_note_title_and_summary(
        "Actual note content"
    )

    assert title == "Actual note content"
    assert summary is None
    assert "<thought" not in title
    assert "</thought>" not in title


@pytest.mark.anyio
async def test_thought_block_glued_to_title_is_stripped_before_parsing():
    """A paired <thought> block whose closing tag is glued to ``TITLE:`` parses."""
    service, _ = _build_service(REAL_THOUGHT_GLUED_TO_TITLE_RESPONSE)

    title, summary = await service.generate_note_title_and_summary("Some note body")

    assert title == "VOO Position Update"
    assert summary == (
        "Increased VOO holdings during a dip while managing concentration "
        "risk through dollar cost averaging."
    )
    assert "<thought" not in title


@pytest.mark.anyio
async def test_think_tag_variants_are_stripped():
    for marker in (
        "<think>reasoning</think>",
        "[THINK]reasoning[/THINK]",
        "[Think]reasoning[/Think]",
    ):
        service, _ = _build_service(
            f"{marker}TITLE: Variant title\nSUMMARY: Variant summary."
        )

        title, summary = await service.generate_note_title_and_summary("note body")

        assert title == "Variant title", marker
        assert summary == "Variant summary.", marker


@pytest.mark.anyio
async def test_title_call_budget_survives_real_latency():
    """Regression guard: 10s/120 tokens raised APITimeoutError for every note."""
    service, create = _build_service("TITLE: T\nSUMMARY: S.")

    await service.generate_note_title_and_summary("note")

    assert create.call_args.kwargs["timeout"] >= 120
    assert create.call_args.kwargs["max_tokens"] >= 1000


# Captured: the model put its only labelled answer *inside* the thought block
# and emitted nothing afterwards.
REAL_THOUGHT_ONLY_TITLE_RESPONSE = (
    "<thought>*   Input: A note about adding to a VOO position, managing cash "
    "for October.\n"
    "    *   Constraint 1: Short title (max 50 chars).\n"
    "    *   Title: VOO Position Update\n"
    "    *   Summary: The user increased their VOO holding during a dip.\n"
    "    *   TITLE: VOO Position Update\n"
    "    *   SUMMARY: Increased VOO holdings on a dip while managing "
    "concentration risk through dollar cost averaging.\n"
    "    *   Plain text? Yes.</thought>"
)


@pytest.mark.anyio
async def test_thought_only_response_salvages_its_labelled_answer():
    """The real model often keeps the answer inside <thought>; salvage it."""
    service, _ = _build_service(REAL_THOUGHT_ONLY_TITLE_RESPONSE)

    title, summary = await service.generate_note_title_and_summary("Some note body")

    assert title == "VOO Position Update"
    assert summary == (
        "Increased VOO holdings on a dip while managing concentration risk "
        "through dollar cost averaging."
    )


@pytest.mark.anyio
async def test_thought_only_prose_never_becomes_a_title():
    """Salvage accepts only labelled lines, so reasoning prose can't leak."""
    service, _ = _build_service(
        "<thought>We should think hard about this note and then answer.</thought>"
    )

    title, summary = await service.generate_note_title_and_summary("Actual content")

    assert title == "Actual content"
    assert summary is None
