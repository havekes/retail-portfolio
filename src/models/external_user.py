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

    uuid: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"))
    external_user_id: Mapped[str] = mapped_column(String)

    __table_args__ = (UniqueConstraint("user_id", "institution_id"),)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="external_users")
    institution: Mapped[Institution] = relationship(
        "Institution", back_populates="external_users"
    )
