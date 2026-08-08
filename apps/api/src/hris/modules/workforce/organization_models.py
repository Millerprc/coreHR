from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from hris.shared.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class OrganizationEvent(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organization_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key"),
        CheckConstraint("expected_version >= 1", name="expected_version_positive"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="planned")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    expected_version: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    change_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrganizationLeader(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organization_leaders"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "person_id",
            "effective_from",
            "version",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="effective_period_order",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    person_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("persons.id"),
        nullable=False,
        index=True,
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")


class PersonBpMembership(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "person_bp_memberships"
    __table_args__ = (
        UniqueConstraint("person_id", "effective_from", "version"),
        CheckConstraint(
            "bp_type IN ('HRBP', 'EBP', 'TBP', 'FBP')",
            name="bp_type_allowed",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="effective_period_order",
        ),
    )

    person_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("persons.id"),
        nullable=False,
        index=True,
    )
    bp_type: Mapped[str] = mapped_column(String(10), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")


class BpServiceScope(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bp_service_scopes"
    __table_args__ = (
        UniqueConstraint("membership_id", "organization_id", "effective_from"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="effective_period_order",
        ),
    )

    membership_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("person_bp_memberships.id"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)


class RevenueTargetMonth(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "revenue_target_months"
    __table_args__ = (
        UniqueConstraint("revenue_target_id", "month"),
        CheckConstraint("month BETWEEN 1 AND 12", name="month_range"),
        CheckConstraint("amount >= 0", name="amount_nonnegative"),
    )

    revenue_target_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("revenue_targets.id"),
        nullable=False,
        index=True,
    )
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
