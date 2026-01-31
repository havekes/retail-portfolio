from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.auth.api_types import UserId
from src.config.database import BaseModel
from src.integration.api_types import IntegrationUserId


class IntegrationUserModel(BaseModel):
    """External integration user model."""

    __tablename__ = "integration_users"

    id: Mapped[IntegrationUserId] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UserId] = mapped_column(Uuid, ForeignKey("auth_users.id"))
    institution_id: Mapped[int] = mapped_column(Integer, ForeignKey("institutions.id"))
    external_user_id: Mapped[str] = mapped_column(String)
    display_name: Mapped[str] = mapped_column(String)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("user_id", "institution_id", "external_user_id"),
    )
