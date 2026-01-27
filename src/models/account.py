from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

if TYPE_CHECKING:
    from .account_type import AccountType
    from .institution import Institution
    from .note import Note
    from .portfolio_account import PortfolioAccount
    from .position import Position
    from .user import User


class Account(Base):
    """Account model."""

    __tablename__ = "accounts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    external_id: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    account_type_id: Mapped[int] = mapped_column(ForeignKey("account_types.id"))
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"))
    currency: Mapped[str] = mapped_column(String(3))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    deleted_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Index on (user_id, institution_id, account_type_id)
    __table_args__ = (
        Index(
            "ix_account_user_institution_type",
            "user_id",
            "institution_id",
            "account_type_id",
        ),
    )

    # TODO add unique on institution_id and external_id

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="accounts")
    account_type: Mapped[AccountType] = relationship(
        "AccountType", back_populates="accounts"
    )
    institution: Mapped[Institution] = relationship(
        "Institution", back_populates="accounts"
    )
    positions: Mapped[list[Position]] = relationship(
        "Position", back_populates="account"
    )
    notes: Mapped[list[Note]] = relationship("Note", back_populates="account")
    portfolio_accounts: Mapped[list[PortfolioAccount]] = relationship(
        "PortfolioAccount", back_populates="account"
    )
