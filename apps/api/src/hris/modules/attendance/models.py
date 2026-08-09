from datetime import date, datetime, time
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
    Index,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from hris.shared.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class AttendanceRuleSet(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attendance_rule_sets"
    __table_args__ = (
        UniqueConstraint("code", "version"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="effective_period_order",
        ),
    )

    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    timezone: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    rules: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class Shift(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shifts"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    crosses_midnight: Mapped[bool] = mapped_column(nullable=False, default=False)
    rule_set_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("attendance_rule_sets.id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")


class ScheduleAssignment(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "schedule_assignments"
    __table_args__ = (
        UniqueConstraint("employment_id", "work_date"),
    )

    employment_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("employments.id"),
        nullable=False,
        index=True,
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    shift_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("shifts.id"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)


class AttendancePunch(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attendance_punches"
    __table_args__ = (
        UniqueConstraint("source", "source_record_id"),
    )

    employment_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("employments.id"),
        nullable=False,
        index=True,
    )
    punched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    punch_type: Mapped[str | None] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )


class LeaveType(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leave_types"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    rules: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class LeaveRequest(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leave_requests"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="leave_period_order"),
        CheckConstraint("amount > 0", name="leave_amount_positive"),
    )

    request_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )
    employment_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("employments.id"),
        nullable=False,
        index=True,
    )
    leave_type_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("leave_types.id"),
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_instance_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("workflow_instances.id"),
    )
    cancellation_of_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("leave_requests.id"),
    )


class LeaveBalanceAccount(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leave_balance_accounts"
    __table_args__ = (
        UniqueConstraint(
            "employment_id",
            "leave_type_id",
            "period_year",
        ),
        CheckConstraint(
            "period_year BETWEEN 2000 AND 2200",
            name="period_year_allowed",
        ),
        CheckConstraint("unit IN ('day', 'hour')", name="unit_allowed"),
        CheckConstraint("status IN ('active', 'closed')", name="status_allowed"),
        CheckConstraint("version >= 0", name="version_non_negative"),
    )

    employment_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("employments.id"),
        nullable=False,
        index=True,
    )
    leave_type_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("leave_types.id"),
        nullable=False,
        index=True,
    )
    period_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    current_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")


class LeaveBalanceTransaction(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leave_balance_transactions"
    __table_args__ = (
        CheckConstraint(
            "transaction_type IN "
            "('grant', 'adjustment', 'carryover', 'accrual', 'usage', 'reversal')",
            name="transaction_type_allowed",
        ),
        CheckConstraint("amount <> 0", name="amount_non_zero"),
        CheckConstraint("account_version > 0", name="account_version_positive"),
        CheckConstraint(
            "balance_after = balance_before + amount",
            name="balance_math_consistent",
        ),
        Index(
            "ix_leave_balance_transactions_account_version",
            "account_id",
            "account_version",
        ),
        Index(
            "ix_leave_balance_transactions_source",
            "source_type",
            "source_id",
        ),
    )

    account_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("leave_balance_accounts.id"),
        nullable=False,
    )
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    balance_before: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    account_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[UUID | None] = mapped_column(Uuid)
    idempotency_key: Mapped[UUID] = mapped_column(Uuid, unique=True, nullable=False)
    request_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)


class AttendanceDailyResult(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attendance_daily_results"
    __table_args__ = (
        UniqueConstraint("employment_id", "work_date", "version"),
    )

    employment_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("employments.id"),
        nullable=False,
        index=True,
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    scheduled_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    worked_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    late_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    early_leave_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    exception_codes: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(nullable=False, default=True)


class AttendanceMonthlyResult(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attendance_monthly_results"
    __table_args__ = (
        UniqueConstraint("employment_id", "period_month", "version"),
    )

    employment_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("employments.id"),
        nullable=False,
        index=True,
    )
    period_month: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    scheduled_days: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=0,
    )
    worked_days: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=0,
    )
    leave_days: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=0,
    )
    absent_days: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=0,
    )
    late_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    early_leave_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)


class AttendancePeriodFreeze(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attendance_period_freezes"
    __table_args__ = (
        CheckConstraint("date_to >= date_from", name="period_order"),
        CheckConstraint(
            "freeze_type IN ('monthly', 'special')",
            name="freeze_type_allowed",
        ),
        CheckConstraint(
            "status IN ('active', 'released')",
            name="status_allowed",
        ),
        CheckConstraint(
            "(status = 'active' AND released_at IS NULL AND released_by IS NULL "
            "AND release_reason IS NULL) OR "
            "(status = 'released' AND released_at IS NOT NULL "
            "AND released_by IS NOT NULL AND release_reason IS NOT NULL)",
            name="release_state_consistent",
        ),
        Index(
            "ix_attendance_period_freezes_status_range",
            "status",
            "date_from",
            "date_to",
        ),
    )

    freeze_type: Mapped[str] = mapped_column(String(20), nullable=False)
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    frozen_by: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    frozen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_by: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_reason: Mapped[str | None] = mapped_column(Text)
