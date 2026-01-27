from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

if TYPE_CHECKING:
    from .account import Account
    from .portfolio import Portfolio


class PortfolioAccount(Base):
    """PortfolioAccount model - join table linking portfolios to accounts."""

    __tablename__ = "portfolio_accounts"

    # Composite primary key
    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey("portfolios.id"), primary_key=True
    )
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id"), primary_key=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Relationships
    portfolio: Mapped[Portfolio] = relationship(
        "Portfolio", back_populates="portfolio_accounts"
    )
    account: Mapped[Account] = relationship(
        "Account", back_populates="portfolio_accounts"
    )
