"""Unit tests for the shared reasoning/markdown cleaner in ``ai_service``.

The fixtures are real (sanitized) responses captured from the worktree stack's
configured endpoint. No test here performs a network call: the cleaner is a
pure function of the response text.
"""

from src.market.ai_service import (
    MAX_LONG_SUMMARY_LENGTH,
    MAX_TITLE_LENGTH,
    clean_note_title,
    clean_short_summary,
    normalize_long_summary,
    remove_reasoning_tags,
    strip_reasoning,
)

# Captured verbatim from the configured endpoint for the notes-summary prompt.
REAL_THOUGHT_SUMMARY_RESPONSE = (
    "<thought>*   Security: VOO (Vanguard S&P 500 ETF)\n"
    "    *   Notes:\n"
    "        1. 2026-09-20: Added to position on dip, saving cash for October.\n"
    "    *   SHORT: DRAFT SHORT that must never be persisted.\n"
    "    *   LONG: DRAFT LONG that must never be persisted.</thought>"
    "SHORT: User maintains a long-term DCA strategy for VOO, buying the dip.\n\n"
    "LONG: The user continues a long-term investment thesis."
)

# Captured title response whose 120-token budget was consumed by reasoning.
REAL_ANSWERLESS_THOUGHT_RESPONSE = (
    "<thought>*   Input: A short note about investing in VOO (S&P 500 ETF).\n"
    "    *   Key points: Added to VOO on a dip, holding cash for October.\n"
    "    </thought>"
)


def test_strips_paired_html_thought_block():
    assert (
        strip_reasoning("<thought>weighing it up</thought>SHORT: Dense digest.")
        == "SHORT: Dense digest."
    )


def test_strips_html_think_block_case_insensitively():
    assert strip_reasoning("<THINK>reasoning</THINK>answer") == "answer"
    assert strip_reasoning("<Think>reasoning</Think>answer") == "answer"


def test_strips_bracket_think_block_case_insensitively():
    assert strip_reasoning("[think]reasoning[/think]answer") == "answer"
    assert strip_reasoning("[THINK]reasoning[/THINK]answer") == "answer"


def test_strips_multiple_blocks_at_any_position():
    text = "<thought>one</thought>middle<thought>two</thought>[think]three[/think]end"
    assert strip_reasoning(text) == "middleend"


def test_strips_unterminated_html_thought_everything_after():
    assert strip_reasoning("answer<thought>truncated mid-thought") == "answer"


def test_strips_unterminated_tag_when_it_is_the_whole_response():
    assert strip_reasoning(REAL_ANSWERLESS_THOUGHT_RESPONSE) == ""


def test_strips_unterminated_bracket_think():
    assert strip_reasoning("SHORT: a\nLONG: b\n[think]and then it stops") == (
        "SHORT: a\nLONG: b"
    )


def test_strips_stray_closing_tag_glued_to_a_label():
    assert strip_reasoning("</thought>TITLE: Real title") == "TITLE: Real title"


def test_real_paired_sample_keeps_only_the_answer():
    cleaned = strip_reasoning(REAL_THOUGHT_SUMMARY_RESPONSE)
    assert cleaned.startswith("SHORT: User maintains")
    assert "DRAFT" not in cleaned
    assert "<thought" not in cleaned
    assert "</thought>" not in cleaned


def test_remove_reasoning_tags_keeps_the_inner_text():
    assert remove_reasoning_tags("<thought>inner</thought>") == "inner"
    assert remove_reasoning_tags("[think]inner[/think]") == "inner"
    assert remove_reasoning_tags("<think>inner") == "inner"


def test_strip_reasoning_is_idempotent():
    once = strip_reasoning(REAL_THOUGHT_SUMMARY_RESPONSE)
    assert strip_reasoning(once) == once


def test_normalize_long_summary_strips_markdown_and_collapses_newlines():
    raw = "# Heading\n\n- Bullet one\n- Bullet two\n\nBold **text** and `code`."
    assert normalize_long_summary(raw) == (
        "Heading Bullet one Bullet two Bold text and code."
    )


def test_normalize_long_summary_hard_caps_length():
    assert len(normalize_long_summary("x" * (MAX_LONG_SUMMARY_LENGTH + 500))) == (
        MAX_LONG_SUMMARY_LENGTH
    )


def test_normalize_long_summary_strips_reasoning_first():
    assert (
        normalize_long_summary("<thought>noise</thought>## Real paragraph")
        == "Real paragraph"
    )


def test_clean_short_summary_caps_at_160_and_returns_none_for_blank():
    capped = clean_short_summary("y" * 400)
    assert capped is not None
    assert len(capped) == 160
    assert clean_short_summary(None) is None
    assert clean_short_summary("   ") is None


def test_clean_short_summary_strips_reasoning_and_markdown():
    assert clean_short_summary("<thought>x</thought>**Dense** digest.") == (
        "Dense digest."
    )


def test_clean_note_title_caps_length_and_strips_markers():
    assert clean_note_title("<thought>x</thought>## Real title") == "Real title"
    capped = clean_note_title("z" * 200)
    assert capped is not None
    assert len(capped) == MAX_TITLE_LENGTH
    assert clean_note_title(None) is None
    assert clean_note_title("   ") is None
    assert clean_note_title('"Quoted title"') == "Quoted title"
