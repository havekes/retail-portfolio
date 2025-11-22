from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

if TYPE_CHECKING:
    from .account import Account
    from .security import Security
    from .user import User


class Note(Base):  # pylint: disable=too-few-public-methods
    """Note model."""

    __tablename__ = "notes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    date: Mapped[date] = mapped_column(Date)
    content: Mapped[str] = mapped_column(Text)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    security_symbol: Mapped[str] = mapped_column(
        ForeignKey("securities.symbol"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now)  # pylint: disable=not-callable
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now,
        onupdate=func.now,  # pylint: disable=not-callable
    )

    # Unique constraint on (user_id, date)
    __table_args__ = (UniqueConstraint("user_id", "date"),)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="notes")
    account: Mapped[Account] = relationship("Account", back_populates="notes")
    security: Mapped[Security] = relationship("Security", back_populates="notes")
