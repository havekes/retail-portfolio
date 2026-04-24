import logging
import re
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

    def __init__(  # noqa: PLR0913
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

        notes = await self._notes_repository.get_by_security_and_user(
            security_id, user_id
        )

        today = datetime.now(tz=UTC).date()
        from_date = today.replace(day=1) - timedelta(days=90)

        recent_prices = await self._price_repository.get_prices(
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
        self, prompt: str, context: AIContext, timeout: int = 60
    ) -> str:
        """
        Call AI API with prompt and context.

        Args:
            prompt: User's analysis request
            context: Security context data
            timeout: Request timeout in seconds

        Returns:
            AI response content
        """
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
                        "content": self._build_context_prompt(prompt, context),
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
        return await self._call_ai_api(prompt, context)

    async def generate_note_title(self, content: str) -> str:
        """
        Generate a short, concise title for a note using AI.

        Args:
            content: The content of the note.

        Returns:
            A short title (max 50 characters).
        """
        try:
            response = await self._client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful assistant that generates short, "
                            "concise titles for notes. The title should be "
                            "maximum 50 characters and capture the essence "
                            "of the note."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Generate a title for this note:\n\n{content}",
                    },
                ],
                temperature=0.3,
                max_tokens=20,
                timeout=10,
            )
            title = response.choices[0].message.content
            if not title:
                self._raise_no_title()

            if not isinstance(title, str):
                self._raise_title_type_error()

            title_str = cast("str", title)
            title_str = title_str.strip()
            # Remove quotes if AI included them
            if (title_str.startswith('"') and title_str.endswith('"')) or (
                title_str.startswith("'") and title_str.endswith("'")
            ):
                title_str = title_str[1:-1]
            return title_str[:MAX_TITLE_LENGTH]
        except Exception:
            logger.exception("Failed to generate note title")
            # Return a truncated version of the content as fallback
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
