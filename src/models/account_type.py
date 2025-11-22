from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

if TYPE_CHECKING:
    from .account import Account


class AccountType(Base):
    """Account type model."""

    __tablename__ = "account_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    country: Mapped[str] = mapped_column(String, default="CA")
    tax_advantaged: Mapped[bool] = mapped_column(Boolean)

    # Relationships
    accounts: Mapped[list[Account]] = relationship(
        "Account", back_populates="account_type"
    )
