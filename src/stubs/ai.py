"""AI service stubs for testing and local development."""

import logging
from datetime import UTC, datetime

from src.auth.api_types import UserId
from src.market.api_types import SecurityId

logger = logging.getLogger(__name__)


class StubAIService:
    """Stub implementation of AIService."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize stub AI service."""

    async def analyze_fundamentals(
        self,
        security_id: SecurityId,  # noqa: ARG002
        user_id: UserId,  # noqa: ARG002
    ) -> str:
        """Stub analysis of security fundamentals."""
        return (
            "### Fundamental Analysis (Stub)\n\n"
            "This security shows strong potential based on its market position. "
            "Valuation remains within historical ranges, though competitive pressures "
            "in the sector should be monitored. Growth is driven by expansion into "
            "new markets and continued operational efficiency."
        )

    async def summarize_notes(
        self,
        security_id: SecurityId,  # noqa: ARG002
        user_id: UserId,  # noqa: ARG002
    ) -> str:
        """Stub summary of user notes."""
        return (
            "### User Notes Summary (Stub)\n\n"
            "The user has noted several key entry points and is monitoring "
            "quarterly earnings closely. Overall sentiment in the notes is "
            "cautiously optimistic, focusing on long-term value preservation."
        )

    async def analyze_portfolio_fit(
        self,
        security_id: SecurityId,  # noqa: ARG002
        user_id: UserId,  # noqa: ARG002
        portfolio_context: str,
    ) -> str:
        """Stub analysis of portfolio fit."""
        return (
            f"### Portfolio Fit Analysis (Stub)\n\n"
            f"Given the portfolio context: '{portfolio_context[:50]}...', "
            "this security provides moderate diversification benefits. "
            "It aligns with a growth-oriented strategy but adds some industry-specific "
            "concentration that should be balanced with other defensive holdings."
        )
