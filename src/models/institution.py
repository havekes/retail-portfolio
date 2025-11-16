from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

if TYPE_CHECKING:
    from .account import Account


class Institution(Base):
    """Institution model."""

    __tablename__ = "institutions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    website: Mapped[str] = mapped_column(String, nullable=True)
    country: Mapped[str] = mapped_column(String, default="CA")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    accounts: Mapped[list[Account]] = relationship(
        "Account", back_populates="institution"
    )
