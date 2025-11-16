from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.enums import ActionEnum

from . import Base

if TYPE_CHECKING:
    from .security import Security
    from .user import User


class ActionItem(Base):
    """Action item model."""

    __tablename__ = "action_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    security_symbol: Mapped[str] = mapped_column(ForeignKey("securities.symbol"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    action: Mapped[ActionEnum] = mapped_column(SAEnum(ActionEnum))
    reason: Mapped[str] = mapped_column(Text, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=func.now)  # pylint: disable=not-callable

    # Unique constraint on (user_id, security_symbol)
    __table_args__ = (UniqueConstraint("user_id", "security_symbol"),)

    # Relationships
    security: Mapped[Security] = relationship("Security", back_populates="action_items")
    user: Mapped[User] = relationship("User", back_populates="action_items")
