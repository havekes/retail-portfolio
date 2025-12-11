from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

if TYPE_CHECKING:
    from .institution import Institution
    from .user import User


class ExternalUser(Base):
    """External user model."""

    __tablename__ = "external_users"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id"), primary_key=True
    )
    external_user_id: Mapped[str] = mapped_column(String, primary_key=True)

    __table_args__ = (
        UniqueConstraint("user_id", "institution_id", "external_user_id"),
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="external_users")
    institution: Mapped[Institution] = relationship(
        "Institution", back_populates="external_users"
    )
