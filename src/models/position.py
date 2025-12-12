from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

if TYPE_CHECKING:
    from .account import Account
    from .security import Security


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"))
    security_symbol: Mapped[str] = mapped_column(ForeignKey("securities.symbol"))
    quantity: Mapped[float] = mapped_column(Float)
    average_cost: Mapped[float | None] = mapped_column(Float, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("account_id", "security_symbol"),)

    # Relationships
    account: Mapped[Account] = relationship("Account")
    security: Mapped[Security] = relationship("Security")
