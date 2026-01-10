from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

if TYPE_CHECKING:
    from .account import Account
    from .action_item import ActionItem
    from .external_user import ExternalUser
    from .note import Note
    from .reminder import Reminder
    from .watchlist import Watchlist


class User(Base):
    """User model."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password: Mapped[str] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Relationships
    accounts: Mapped[list[Account]] = relationship("Account", back_populates="user")
    watchlists: Mapped[list[Watchlist]] = relationship(
        "Watchlist", back_populates="user"
    )
    notes: Mapped[list[Note]] = relationship("Note", back_populates="user")
    reminders: Mapped[list[Reminder]] = relationship("Reminder", back_populates="user")
    action_items: Mapped[list[ActionItem]] = relationship(
        "ActionItem", back_populates="user"
    )
    external_users: Mapped[list[ExternalUser]] = relationship(
        "ExternalUser", back_populates="user"
    )
