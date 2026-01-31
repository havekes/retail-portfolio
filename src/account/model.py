from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    DECIMAL,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.schema import UniqueConstraint
from stockholm import Currency

from src.account.api_types import (
    AccountId,
    PositionId,
)
from src.account.enum import AccountTypeEnum, InstitutionEnum
from src.auth.api_types import UserId
from src.config.database import BaseModel
from src.integration.brokers.api_types import BrokerAccountId
from src.market.api_types import SecurityId


class AccountModel(BaseModel):
    """Account model."""

    __tablename__ = "accounts"

    id: Mapped[AccountId] = mapped_column(primary_key=True, default=uuid4)
    external_id: Mapped[BrokerAccountId] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    user_id: Mapped[UserId] = mapped_column(Uuid, ForeignKey("auth_users.id"))
    account_type_id: Mapped[AccountTypeEnum] = mapped_column(
        ForeignKey("account_types.id")
    )
    institution_id: Mapped[InstitutionEnum] = mapped_column(
        ForeignKey("institutions.id")
    )
    currency: Mapped[Currency] = mapped_column()
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint("user_id", "institution_id", "external_id"),)

    # Relationships
    account_type: Mapped[AccountTypeModel] = relationship(
        "AccountTypeModel", back_populates="accounts"
    )
    institution: Mapped[InstitutionModel] = relationship(
        "InstitutionModel", back_populates="accounts"
    )
    positions: Mapped[list[PositionModel]] = relationship(
        "PositionModel", back_populates="account"
    )


class AccountTypeModel(BaseModel):
    """Account type model."""

    __tablename__ = "account_types"

    id: Mapped[AccountTypeEnum] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    country: Mapped[str] = mapped_column(String)
    tax_advantaged: Mapped[bool] = mapped_column(Boolean)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (UniqueConstraint("name", "country"),)

    # Relationships
    accounts: Mapped[list[AccountModel]] = relationship(
        "AccountModel", back_populates="account_type"
    )


class InstitutionModel(BaseModel):
    """Institution model."""

    __tablename__ = "institutions"

    id: Mapped[InstitutionEnum] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    country: Mapped[str] = mapped_column(String)
    website: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (UniqueConstraint("name", "country"),)

    # Relationships
    accounts: Mapped[list[AccountModel]] = relationship(
        "AccountModel", back_populates="institution"
    )


class PositionModel(BaseModel):
    __tablename__ = "positions"

    id: Mapped[PositionId] = mapped_column(BigInteger, primary_key=True, default=uuid4)
    account_id: Mapped[AccountId] = mapped_column(Uuid, ForeignKey("accounts.id"))
    security_id: Mapped[SecurityId] = mapped_column(
        Uuid, ForeignKey("market_securities.id")
    )
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(16, 8))
    average_cost: Mapped[Decimal | None] = mapped_column(Float, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("account_id", "security_id"),)

    # Relationships
    account: Mapped[AccountModel] = relationship(
        "AccountModel",
        back_populates="positions",
    )
