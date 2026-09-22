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
async def test_generate_note_title_delegates_to_combined_call():
    service, create = _build_service("TITLE: Delegated title\nSUMMARY: A sentence.")

    title = await service.generate_note_title("Some note body")

    assert title == "Delegated title"
    create.assert_awaited_once()
