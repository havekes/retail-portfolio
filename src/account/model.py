from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    DECIMAL,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql.schema import UniqueConstraint
from stockholm import Currency

from src.account.api_types import (
    AccountId,
    AccountTypeEnum,
    InstitutionEnum,
    PositionId,
)
from src.market.api_types import SecurityId
from src.utils import EnumAsInteger


class Base(DeclarativeBase):
    pass


class AccountModel(Base):
    """Account model."""

    __tablename__ = "accounts"

    id: Mapped[AccountId] = mapped_column(primary_key=True, default=uuid4)
    external_id: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    account_type_id: Mapped[AccountTypeEnum] = mapped_column(
        ForeignKey("account_types.id")
    )
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"))
    currency: Mapped[Currency] = mapped_column(String(3))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint("user_id", "institution_id", "external_id"),)

    # Relationships
    account_type: Mapped[AccountTypeModel] = relationship(
        "AccountType", back_populates="accounts"
    )
    institution: Mapped[InstitutionModel] = relationship(
        "Institution", back_populates="accounts"
    )
    positions: Mapped[PositionModel] = relationship(
        "Position", back_populates="accounts"
    )


class AccountTypeModel(Base):
    """Account type model."""

    __tablename__ = "account_types"

    id: Mapped[AccountTypeEnum] = mapped_column(
        EnumAsInteger(AccountTypeEnum), primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String)
    country: Mapped[str] = mapped_column(String(2))
    tax_advantaged: Mapped[bool] = mapped_column(Boolean)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (UniqueConstraint("name", "country"),)

    # Relationships
    accounts: Mapped[list[AccountModel]] = relationship(
        "Account", back_populates="account_type"
    )


class InstitutionModel(Base):
    """Institution model."""

    __tablename__ = "institutions"

    id: Mapped[InstitutionEnum] = mapped_column(
        EnumAsInteger(InstitutionEnum), primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String)
    country: Mapped[str] = mapped_column(String(2))
    website: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (UniqueConstraint("name", "country"),)

    # Relationships
    accounts: Mapped[list[AccountModel]] = relationship(
        "Account", back_populates="institution"
    )


class PositionModel(Base):
    __tablename__ = "positions"

    id: Mapped[PositionId] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[AccountId] = mapped_column(ForeignKey("accounts.id"))
    security_id: Mapped[SecurityId] = mapped_column(ForeignKey("securities.id"))
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(16, 8))
    average_cost: Mapped[Decimal | None] = mapped_column(Float, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("account_id", "security_id"),)

    # Relationships
    account: Mapped[AccountModel] = relationship("Account")
