import json
import logging
import re
import time
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta, timezone
from typing import TypedDict, cast

from openai import AsyncOpenAI
from svcs import Container

from src.auth.api_types import UserId
from src.config.settings import settings
from src.market.api_types import SecurityId
from src.market.repository import (
    PriceRepository,
    SecurityNoteRepository,
    SecurityRepository,
)
from src.market.schema import MAX_SHORT_SUMMARY_LENGTH

logger = logging.getLogger(__name__)


MAX_TITLE_LENGTH = 50

# The local model (Gemma) emits reasoning in ``[think] ... [/think]`` blocks
# before the answer. ``_strip_think`` removes both complete blocks and an
# unterminated ``[think]`` prefix (generation truncated mid-reasoning).
_THINK_PAIRED_RE = re.compile(r"\[think\].*?\[/think\]", re.DOTALL)
_THINK_UNTERMINATED_RE = re.compile(r"\[think\].*", re.DOTALL)


def _strip_think(content: str) -> str:
    """Remove reasoning tokens from a model response.

    Handles the complete ``[think]...[/think]`` pair *and* an unterminated
    ``[think]`` prefix (when generation is cut off mid-reasoning, everything
    from the opening tag onward is reasoning and must not be persisted).
    """
    without_pairs = _THINK_PAIRED_RE.sub("", content)
    return _THINK_UNTERMINATED_RE.sub("", without_pairs).strip()


def _http_error_status(e: Exception) -> str | int | None:
    """Best-effort HTTP status from an OpenAI SDK exception."""
    return getattr(e, "status_code", None) or e.__class__.__name__


def _http_error_body(e: Exception) -> str | None:
    """Best-effort response/error detail from an OpenAI SDK exception (truncated)."""
    body = getattr(e, "body", None) or getattr(e, "message", None)
    return str(body)[:500] if body else None


# Stable sentence so tests (and prompt consumers) can assert the recency
# weighting instruction is present.
RECENCY_WEIGHTING_INSTRUCTION = (
    "\nWeight the most recent notes more heavily: assume newer notes reflect "
    "the user's current thinking and give them proportionally more emphasis "
    "than older notes, while preserving the evolution of the user's views.\n"
)


class AIContext(TypedDict):
    security: dict
    current_price: dict | None
    notes: list[dict]
    recent_prices: list[dict]


class AIResponse(TypedDict):
    content: str
    generated_at: str


class NoteSummaryParts(TypedDict):
    """Two-part AI summary of a user's notes for one security."""

    short_summary: str
    long_summary: str


class AIService:
    """Service for AI-powered analysis of securities."""

    def __init__(  # noqa: PLR0913, PLR0917
        self,
        security_repository: SecurityRepository,
        price_repository: PriceRepository,
        notes_repository: SecurityNoteRepository,
        api_endpoint: str,
        api_key: str,
        api_model: str,
    ):
        self._security_repository = security_repository
        self._price_repository = price_repository
        self._notes_repository = notes_repository
        self._api_base_url = api_endpoint
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=api_endpoint.replace("/chat/completions", ""),
        )
        self._api_model = api_model

    async def _gather_context(
        self, security_id: SecurityId, user_id: UserId
    ) -> AIContext:
        """
        Gather context for AI analysis.

        Args:
            security_id: Security identifier
            user_id: User identifier

        Returns:
            AIContext with security data, price, notes, and recent prices
        """
        security = await self._security_repository.get_by_id_or_fail(security_id)
        latest_price = await self._price_repository.get_latest_price(security)

        notes, _ = await self._notes_repository.get_by_security_and_user(
            security_id, user_id, limit=50
        )

        today = datetime.now(tz=UTC).date()
        from_date = today.replace(day=1) - timedelta(days=90)

        recent_prices, _ = await self._price_repository.get_prices(
            security, from_date=from_date, to_date=today
        )

        return AIContext(
            security={
                "symbol": security.symbol,
                "name": security.name,
                "exchange": security.exchange,
                "currency": security.currency,
            },
            current_price={
                "price": float(latest_price.close),
                "date": latest_price.date.isoformat(),
            }
            if latest_price
            else None,
            notes=[
                {"content": n.content, "created_at": n.created_at.isoformat()}
                for n in notes
            ],
            recent_prices=[
                {
                    "date": p.date.isoformat(),
                    "close": float(p.close),
                }
                for p in recent_prices[-30:]
            ],
        )

    async def _call_ai_api(
        self,
        prompt: str,
        context: AIContext,
        timeout: int = 60,
        prompt_builder: Callable[[str, AIContext], str] | None = None,
    ) -> str:
        """
        Call AI API with prompt and context.

        Args:
            prompt: User's analysis request
            context: Security context data
            timeout: Request timeout in seconds
            prompt_builder: Optional context renderer; defaults to the generic
                analysis prompt. Callers needing a specialised rendering (for
                example the recency-weighted notes summary) pass their own.

        Returns:
            AI response content
        """
        build_prompt = prompt_builder or self._build_context_prompt
        logger.info(
            "Calling AI API: model=%s endpoint=%s prompt_chars=%d",
            self._api_model,
            self._api_base_url,
            len(build_prompt(prompt, context)),
        )
        started_at = time.monotonic()
        try:
            response = await self._client.chat.completions.create(
                model=self._api_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful financial analysis assistant. "
                            "Provide clear, actionable insights based on the "
                            "provided data. Use markdown formatting for readability. "
                            "Answer directly: never include reasoning or "
                            "[think]...[/think] blocks in your reply."
                        ),
                    },
                    {
                        "role": "user",
                        "content": build_prompt(prompt, context),
                    },
                ],
                temperature=0.7,
                max_tokens=2000,
                timeout=timeout,
            )
            content = response.choices[0].message.content
            if not content:
                self._raise_empty_response()
        except Exception as e:
            failed_after_s = time.monotonic() - started_at
            failure_status = _http_error_status(e)
            failure_detail = _http_error_body(e)
            logger.exception(
                "AI API request failed after %.2fs: status=%s detail=%s",
                failed_after_s,
                failure_status,
                failure_detail,
            )
            msg = f"AI service unavailable: {e!s}"
            raise RuntimeError(msg) from None
        else:
            if not isinstance(content, str):
                self._raise_content_type_error()
            content_str = cast("str", content)
            logger.info(
                "AI API request completed in %.2fs: response_chars=%d",
                time.monotonic() - started_at,
                len(content_str),
            )
            return _strip_think(content_str)

    def _raise_content_type_error(self) -> None:
        msg = "AI response content is not a string"
        raise TypeError(msg)

    def _raise_empty_response(self) -> None:
        msg = "AI response content is empty"
        raise RuntimeError(msg)

    def _build_context_prompt(self, prompt: str, context: AIContext) -> str:
        """
        Build a comprehensive prompt with context.

        Args:
            prompt: User's original prompt
            context: AI context data

        Returns:
            Formatted prompt string
        """
        security = context["security"]
        current_price = context["current_price"]
        notes = context["notes"]
        recent_prices = context["recent_prices"]

        prompt_parts = [
            "Analyze the following security:\n",
            f"- Symbol: {security['symbol']}\n",
            f"- Name: {security['name']}\n",
            f"- Exchange: {security['exchange']}\n",
            f"- Currency: {security['currency']}\n",
        ]

        if current_price:
            date_str = current_price["date"]
            price_val = current_price["price"]
            price_str = f"\nCurrent Price: ${price_val:.2f} (as of {date_str})\n"
            prompt_parts.append(price_str)

        if notes:
            prompt_parts.append("\nUser Notes:\n")
            prompt_parts.extend(
                [
                    f"- ({note['created_at'][:10]}) {note['content'][:200]}...\n"
                    for note in notes[-5:]
                ]
            )

        if recent_prices:
            prompt_parts.append("\nRecent Price Trend (last 30 days):\n")
            prompt_parts.append(f"- Starting price: ${recent_prices[0]['close']:.2f}\n")
            prompt_parts.append(f"- Latest price: ${recent_prices[-1]['close']:.2f}\n")
            change = (
                (recent_prices[-1]["close"] - recent_prices[0]["close"])
                / recent_prices[0]["close"]
                * 100
            )
            prompt_parts.append(f"- Change: {change:+.2f}%\n")

        prompt_parts.append(f"\n{prompt}\n")
        prompt_parts.append(
            "\nProvide a concise, well-structured analysis with key "
            "insights and actionable recommendations."
        )

        return "".join(prompt_parts)

    def _build_notes_summary_prompt(self, prompt: str, context: AIContext) -> str:
        """
        Build a recency-weighted prompt for summarizing the user's notes.

        Every gathered note is rendered (not just the most recent few), each
        prefixed with its full creation timestamp, in the order the repository
        returns them (newest first). The prompt then instructs the model to
        weight the most recent notes proportionally more heavily — the
        weighting lives in the prompt text, not in hard-coded recency tiers.

        Args:
            prompt: User's original prompt
            context: AI context data

        Returns:
            Formatted prompt string
        """
        security = context["security"]
        notes = context["notes"]

        prompt_parts = [
            "Summarize the user's notes for the following security:\n",
            f"- Symbol: {security['symbol']}\n",
            f"- Name: {security['name']}\n",
            f"- Exchange: {security['exchange']}\n",
            f"- Currency: {security['currency']}\n",
            "\nUser Notes (ordered newest first):\n",
        ]
        prompt_parts.extend(
            f"- [{note['created_at']}] {note['content']}\n" for note in notes
        )
        prompt_parts.append(RECENCY_WEIGHTING_INSTRUCTION)
        prompt_parts.append(f"\n{prompt}\n")
        prompt_parts.append(
            "\nReply with exactly two labelled parts, nothing else:\n"
            f"SHORT: <one information-dense sentence, maximum "
            f"{MAX_SHORT_SUMMARY_LENGTH} characters>\n"
            "LONG: <one short paragraph, 3-5 sentences, no markdown headings>\n"
            "Do not include reasoning or [think]...[/think] blocks."
        )

        return "".join(prompt_parts)

    async def analyze_fundamentals(
        self, security_id: SecurityId, user_id: UserId
    ) -> str:
        """
        Generate AI analysis of security fundamentals.

        Args:
            security_id: Security identifier
            user_id: User identifier

        Returns:
            AI-generated analysis
        """
        context = await self._gather_context(security_id, user_id)
        prompt = (
            "Explain the key fundamental factors that should be considered "
            "when analyzing this security. Include valuation metrics, "
            "competitive position, growth drivers, and risk factors."
        )
        return await self._call_ai_api(prompt, context)

    async def summarize_notes(
        self, security_id: SecurityId, user_id: UserId
    ) -> NoteSummaryParts:
        """
        Generate a two-part summary of the user's notes for a security.

        A single AI call produces both parts: a dense ``short_summary`` (hard
        capped at :data:`MAX_SHORT_SUMMARY_LENGTH`) and a one-paragraph
        ``long_summary``. The model is asked for ``SHORT:``/``LONG:`` labels; a
        tolerant parser accepts bare lines too and derives the short part from
        the long one when the model only produces that.

        Args:
            security_id: Security identifier
            user_id: User identifier

        Returns:
            ``NoteSummaryParts`` with both summary parts
        """
        context = await self._gather_context(security_id, user_id)

        if not context["notes"]:
            placeholder = "No notes found for this security."
            return NoteSummaryParts(short_summary=placeholder, long_summary=placeholder)

        prompt = (
            "Summarize the key insights, themes, and action items from "
            "the user's notes. Organize by topic and highlight important "
            "observations or decisions."
        )
        raw = await self._call_ai_api(
            prompt, context, prompt_builder=self._build_notes_summary_prompt
        )
        return self._parse_summary_parts(raw)

    @staticmethod
    def _parse_summary_parts(raw: str) -> NoteSummaryParts:
        """Parse a model response into the two summary parts.

        Tolerates the labelled ``SHORT:``/``LONG:`` format (labels on separate
        lines, or a single line), a JSON object, and an unlabelled response
        (everything becomes the long part). The short part is always derived
        from the long part when missing, and truncated to the hard cap.
        """
        short: str | None = None
        long: str | None = None

        text = raw.strip()
        payload = AIService._parse_json_summary_parts(text)
        if payload is not None:
            short, long = payload

        if short is None and long is None:
            short, long = AIService._parse_labelled_summary_parts(text)

        if long is None:
            # Unlabelled or SHORT-only response: the whole text is the paragraph.
            long = text

        long_summary = AIService._clean_summary(long) or ""
        short_summary = AIService._clean_summary(short)
        if not short_summary:
            short_summary = AIService._derive_short_summary(long_summary)
        else:
            short_summary = short_summary[:MAX_SHORT_SUMMARY_LENGTH]

        return NoteSummaryParts(
            short_summary=short_summary[:MAX_SHORT_SUMMARY_LENGTH],
            long_summary=long_summary,
        )

    @staticmethod
    def _parse_labelled_summary_parts(text: str) -> tuple[str | None, str | None]:
        """Parse ``SHORT:``/``LONG:`` labelled output, else ``(None, None)``."""
        short: str | None = None
        long: str | None = None
        long_buffer: list[str] = []
        collecting_long = False

        for line in text.splitlines():
            upper = line.strip().upper()
            if upper.startswith("SHORT:"):
                short = line.strip()[len("SHORT:") :].strip()
                collecting_long = False
            elif upper.startswith("LONG:"):
                first = line.strip()[len("LONG:") :].strip()
                long_buffer = [first] if first else []
                collecting_long = True
            elif collecting_long:
                long_buffer.append(line)

        if long_buffer:
            long = "\n".join(long_buffer).strip()

        if long is None:
            long = AIService._rest_after_short(text) if short is not None else None

        return short, long

    @staticmethod
    def _parse_json_summary_parts(text: str) -> tuple[str | None, str | None] | None:
        """Extract summary parts from a JSON body, else ``None``."""
        if not text.startswith("{"):
            return None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None

        raw_short = payload.get("short") or payload.get("short_summary")
        raw_long = payload.get("long") or payload.get("long_summary")
        return (
            raw_short if isinstance(raw_short, str) else None,
            raw_long if isinstance(raw_long, str) else None,
        )

    @staticmethod
    def _rest_after_short(text: str) -> str | None:
        """Text following the ``SHORT:`` line — used when no ``LONG:`` label exists."""
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if line.strip().upper().startswith("SHORT:"):
                rest = "\n".join(lines[index + 1 :]).strip()
                return rest or None
        return None

    @staticmethod
    def _derive_short_summary(long_summary: str) -> str:
        """Derive a dense short digest from the paragraph's first sentence(s).

        Takes leading sentences until they would overflow
        :data:`MAX_SHORT_SUMMARY_LENGTH`, then hard-truncates. Returns ``""``
        when there is nothing to derive from.
        """
        text = " ".join(long_summary.split())
        if not text:
            return ""
        if len(text) <= MAX_SHORT_SUMMARY_LENGTH:
            return text

        sentences = re.split(r"(?<=[.!?])\s+", text)
        digest = ""
        for sentence in sentences:
            candidate = f"{digest} {sentence}".strip()
            if len(candidate) > MAX_SHORT_SUMMARY_LENGTH:
                break
            digest = candidate
        if digest:
            return digest
        return text[:MAX_SHORT_SUMMARY_LENGTH]

    async def generate_note_title(self, content: str) -> str:
        """Generate a short, concise title for a note using AI.

        Thin wrapper kept for existing callers; the underlying AI request is
        shared with the summary so a note create costs a single call.
        """
        title, _ = await self.generate_note_title_and_summary(content)
        return title

    async def generate_note_title_and_summary(
        self, content: str
    ) -> tuple[str, str | None]:
        """Generate a note title and a one-sentence summary in a single AI call.

        Returns ``(title, summary)``. When the AI is unavailable the title
        falls back to a truncated version of the content and the summary is
        ``None`` (also when the response can't be parsed as a summary), so the
        caller can persist a nullable summary without losing the title.
        """
        try:
            response = await self._client.chat.completions.create(
                model=self._api_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You generate short titles and one-sentence "
                            "summaries for notes. Reply with exactly two lines:\n"
                            "TITLE: <short title, maximum 50 characters>\n"
                            "SUMMARY: <one sentence capturing the note's point>\n"
                            "Answer directly: never include reasoning or "
                            "[think]...[/think] blocks in your reply."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "Generate a title and one-sentence summary for "
                            f"this note:\n\n{content}"
                        ),
                    },
                ],
                temperature=0.3,
                max_tokens=120,
                timeout=10,
            )
            raw = response.choices[0].message.content
            if not raw:
                self._raise_no_title()

            if not isinstance(raw, str):
                self._raise_title_type_error()

            # Defensive second pass: the combined call bypasses `_call_ai_api`,
            # so reasoning tokens are stripped here before parsing.
            title, summary = self._parse_title_and_summary(
                _strip_think(cast("str", raw))
            )
            if not title:
                self._raise_no_title()
        except Exception:
            logger.exception("Failed to generate note title and summary")
            return self._fallback_title(content), None
        else:
            return title, summary

    @staticmethod
    def _parse_title_and_summary(raw: str) -> tuple[str, str | None]:
        """Best-effort parse of the model response into ``(title, summary)``.

        Tolerates JSON objects (``{"title": ..., "summary": ...}``) and the
        ``TITLE:``/``SUMMARY:`` two-line format. Anything else is treated as a
        bare title so a malformed summary never costs us the title.
        """
        text = raw.strip()
        title, summary = AIService._parse_json_title_and_summary(text)

        if title is None:
            for line in text.splitlines():
                stripped = line.strip()
                upper = stripped.upper()
                if upper.startswith("TITLE:"):
                    title = stripped[len("TITLE:") :].strip()
                elif upper.startswith("SUMMARY:"):
                    summary = stripped[len("SUMMARY:") :].strip()

        if title is None:
            # Untagged response: the first non-empty line is the title and we
            # deliberately don't guess at a summary.
            title = next(
                (line.strip() for line in text.splitlines() if line.strip()), ""
            )

        return AIService._clean_title(title), AIService._clean_summary(summary)

    @staticmethod
    def _parse_json_title_and_summary(text: str) -> tuple[str | None, str | None]:
        """Extract ``(title, summary)`` from a JSON body, else ``(None, None)``."""
        if not text.startswith("{"):
            return None, None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return None, None
        if not isinstance(payload, dict):
            return None, None

        raw_title = payload.get("title")
        raw_summary = payload.get("summary")
        title = raw_title if isinstance(raw_title, str) else None
        summary = raw_summary if isinstance(raw_summary, str) else None
        return title, summary

    @staticmethod
    def _clean_title(title: str) -> str:
        cleaned = title.strip()
        if (cleaned.startswith('"') and cleaned.endswith('"')) or (
            cleaned.startswith("'") and cleaned.endswith("'")
        ):
            cleaned = cleaned[1:-1]
        return cleaned[:MAX_TITLE_LENGTH]

    @staticmethod
    def _clean_summary(summary: str | None) -> str | None:
        if summary is None:
            return None
        cleaned = summary.strip()
        if (cleaned.startswith('"') and cleaned.endswith('"')) or (
            cleaned.startswith("'") and cleaned.endswith("'")
        ):
            cleaned = cleaned[1:-1]
        return cleaned or None

    @staticmethod
    def _fallback_title(content: str) -> str:
        if len(content) > MAX_TITLE_LENGTH:
            return content[: MAX_TITLE_LENGTH - 3] + "..."
        return content

    def _raise_title_type_error(self) -> None:
        msg = "AI title is not a string"
        raise TypeError(msg)

    def _raise_no_title(self) -> None:
        msg = "AI failed to generate a title"
        raise RuntimeError(msg)

    async def analyze_portfolio_fit(
        self,
        security_id: SecurityId,
        user_id: UserId,
        portfolio_context: str,
    ) -> str:
        """
        Generate AI analysis of how a security fits in the user's portfolio.

        Args:
            security_id: Security identifier
            user_id: User identifier
            portfolio_context: Description of current portfolio

        Returns:
            AI-generated analysis
        """
        context = await self._gather_context(security_id, user_id)
        prompt = (
            f"Analyze how this security fits into the following portfolio:\n\n"
            f"{portfolio_context}\n\n"
            "Consider diversification benefits, correlation with existing holdings, "
            "risk profile, and whether this position aligns with typical portfolio "
            "construction principles."
        )
        return await self._call_ai_api(prompt, context)


async def ai_service_factory(
    container: Container,
) -> AIService:
    return AIService(
        security_repository=await container.aget(SecurityRepository),
        price_repository=await container.aget(PriceRepository),
        notes_repository=await container.aget(SecurityNoteRepository),
        api_endpoint=settings.ai_api_endpoint,
        api_key=settings.ai_api_key,
        api_model=settings.ai_api_model,
    )
