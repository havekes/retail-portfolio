import json
import logging
import re
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

logger = logging.getLogger(__name__)


MAX_TITLE_LENGTH = 50

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
        try:
            response = await self._client.chat.completions.create(
                model=self._api_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful financial analysis assistant. "
                            "Provide clear, actionable insights based on the "
                            "provided data. Use markdown formatting for readability."
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
            logger.exception("AI API request failed")
            msg = f"AI service unavailable: {e!s}"
            raise RuntimeError(msg) from None
        else:
            if not isinstance(content, str):
                self._raise_content_type_error()
            content_str = cast("str", content)
            return re.sub(
                r"<think>.*?</think>", "", content_str, count=0, flags=re.DOTALL
            ).strip()

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
            "\nProvide a concise, well-structured summary with key themes, "
            "action items and any shift in the user's view over time."
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

    async def summarize_notes(self, security_id: SecurityId, user_id: UserId) -> str:
        """
        Generate summary of user's notes for a security.

        Args:
            security_id: Security identifier
            user_id: User identifier

        Returns:
            AI-generated summary
        """
        context = await self._gather_context(security_id, user_id)

        if not context["notes"]:
            return "No notes found for this security."

        prompt = (
            "Summarize the key insights, themes, and action items from "
            "the user's notes. Organize by topic and highlight important "
            "observations or decisions."
        )
        return await self._call_ai_api(
            prompt, context, prompt_builder=self._build_notes_summary_prompt
        )

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
                            "SUMMARY: <one sentence capturing the note's point>"
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

            title, summary = self._parse_title_and_summary(cast("str", raw))
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
