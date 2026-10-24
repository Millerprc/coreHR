# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

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
    # Requirement: D-107 —— 班次绑定「不可变的规则集版本行」。
    # rule_set_version 记录绑定时的规则集版本号，rule_snapshot 冻结当时的时区与规则内容，
    # 旧班次因此不会在规则集发布新版本后静默跟随新规则。
    rule_set_version: Mapped[int | None] = mapped_column(Integer)
    rule_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")


class ScheduleType(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """排班类型（固定班 / 轮班 / 弹性 / 自由）。

    Requirement: D-107 —— 类型只提供规则容器开关，取值语义由企业输入决定；
    是否允许同日多班次等字段在本轮仅作占位。
    """

    __tablename__ = "schedule_types"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="schedule_type_status_allowed",
        ),
    )

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    requires_shift_cycle: Mapped[bool] = mapped_column(nullable=False, default=False)
    requires_flexible_window: Mapped[bool] = mapped_column(nullable=False, default=False)
    allows_multiple_shifts_per_day: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
    )
    requires_publish: Mapped[bool] = mapped_column(nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    rules: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class ShiftCycle(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """轮班周期。

    Requirement: D-107 —— 周期天数、班次序列的取值语义待企业输入；
    本轮只提供容器与校验，不解释轮班算法。
    """

    __tablename__ = "shift_cycles"
    __table_args__ = (
        CheckConstraint("cycle_days > 0", name="shift_cycle_days_positive"),
        CheckConstraint(
            "status IN ('draft', 'active', 'expired')",
            name="shift_cycle_status_allowed",
        ),
    )

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    schedule_type_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("schedule_types.id"),
        nullable=False,
        index=True,
    )
    cycle_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    cycle_days: Mapped[int] = mapped_column(Integer, nullable=False)
    shift_sequence: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    rules: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class FlexibleWindow(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """弹性上下班窗口。

    Requirement: D-107 —— 浮动范围与标准工时取值待企业输入，本轮只建容器。
    """

    __tablename__ = "flexible_windows"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'active', 'expired')",
            name="flexible_window_status_allowed",
        ),
        CheckConstraint(
            "standard_daily_minutes IS NULL OR standard_daily_minutes > 0",
            name="flexible_window_standard_minutes_positive",
        ),
    )

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    schedule_type_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("schedule_types.id"),
        nullable=False,
        index=True,
    )
    arrival_window_start: Mapped[time | None] = mapped_column(Time)
    arrival_window_end: Mapped[time | None] = mapped_column(Time)
    departure_window_start: Mapped[time | None] = mapped_column(Time)
    departure_window_end: Mapped[time | None] = mapped_column(Time)
    standard_daily_minutes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    rules: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class SchedulePublishBatch(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """排班发布批次（按期间发布草稿排班）。"""

    __tablename__ = "schedule_publish_batches"
    __table_args__ = (
        UniqueConstraint("batch_number"),
        CheckConstraint(
            "status IN ('draft', 'published', 'void')",
            name="schedule_publish_batch_status_allowed",
        ),
        CheckConstraint(
            "period_end >= period_start",
            name="schedule_publish_batch_period_order",
        ),
    )

    batch_number: Mapped[str] = mapped_column(String(50), nullable=False)
    period_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    schedule_type_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("schedule_types.id"),
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    published_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ScheduleAssignment(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "schedule_assignments"
    __table_args__ = (
        UniqueConstraint(
            "employment_id",
            "work_date",
            "sequence_no",
            name="uq_schedule_assignments_employment_date_sequence",
        ),
        CheckConstraint("sequence_no >= 1", name="schedule_assignment_sequence_positive"),
        CheckConstraint(
            "publish_status IN ('draft', 'published')",
            name="schedule_assignment_publish_status_allowed",
        ),
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
    # Requirement: D-107 —— 草稿/已发布区分；batch_id 指向发布批次。
    # sequence_no 是「同日多班次」的占位字段，本轮不解释其业务规则。
    publish_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="published",
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    batch_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("schedule_publish_batches.id"),
        index=True,
    )
    schedule_type_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("schedule_types.id"),
        index=True,
    )


class ScheduleSwap(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """换班记录。"""

    __tablename__ = "schedule_swaps"
    __table_args__ = (
        UniqueConstraint("request_number"),
        CheckConstraint(
            "status IN ('draft', 'approved', 'rejected', 'cancelled')",
            name="schedule_swap_status_allowed",
        ),
        CheckConstraint(
            "employment_id_a <> employment_id_b",
            name="schedule_swap_distinct_employments",
        ),
    )

    request_number: Mapped[str] = mapped_column(String(50), nullable=False)
    employment_id_a: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("employments.id"),
        nullable=False,
        index=True,
    )
    employment_id_b: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("employments.id"),
        nullable=False,
        index=True,
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    original_shift_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("shifts.id"),
    )
    new_shift_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("shifts.id"),
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    requested_by: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    remark: Mapped[str | None] = mapped_column(Text)


class AttendancePunch(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attendance_punches"
    # Requirement: D-115 —— 打卡明细的取数模式是「某员工 + 时间区间」
    # （日/考勤计算、员工考勤明细）。原先 employment_id 与 punched_at 只有各自独立的
    # 单列索引，区间查询只能靠索引合并再回表过滤，量大时非常贵。
    # 复合索引让「某人某段时间的打卡」成为一次有序索引扫描。
    __table_args__ = (
        UniqueConstraint("source", "source_record_id"),
        Index(
            "ix_attendance_punches_employment_punched_at",
            "employment_id",
            "punched_at",
        ),
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


class LeaveGrantRule(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """发假额度规则（带生效起止日期，按版本维护）。

    Requirement: D-107 —— 计提频率、工龄折算、封顶、清零、结转上限、有效期、
    离职处理只建可配置字段容器，取值语义由企业输入决定，未到位前一律留空。
    """

    __tablename__ = "leave_grant_rules"
    __table_args__ = (
        UniqueConstraint("code", "version"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="leave_grant_rule_period_order",
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'expired')",
            name="leave_grant_rule_status_allowed",
        ),
        CheckConstraint(
            "entitlement_days IS NULL OR entitlement_days > 0",
            name="leave_grant_rule_entitlement_positive",
        ),
        CheckConstraint(
            "cap_days IS NULL OR cap_days >= 0",
            name="leave_grant_rule_cap_non_negative",
        ),
        CheckConstraint(
            "carryover_cap_days IS NULL OR carryover_cap_days >= 0",
            name="leave_grant_rule_carryover_non_negative",
        ),
        CheckConstraint(
            "seniority_min_years IS NULL OR seniority_max_years IS NULL "
            "OR seniority_max_years >= seniority_min_years",
            name="leave_grant_rule_seniority_order",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="leave_grant_rule_validity_order",
        ),
    )

    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    leave_type_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("leave_types.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    # —— 以下字段为 D-107 规则容器，未配置前保持 NULL ——
    entitlement_days: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    seniority_min_years: Mapped[int | None] = mapped_column(Integer)
    seniority_max_years: Mapped[int | None] = mapped_column(Integer)
    proration_method: Mapped[str | None] = mapped_column(String(30))
    accrual_frequency: Mapped[str | None] = mapped_column(String(30))
    cap_days: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    carryover_cap_days: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    reset_policy: Mapped[str | None] = mapped_column(String(30))
    termination_policy: Mapped[str | None] = mapped_column(String(30))
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    rules: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class LeaveGrantBatch(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """发假发放批次。"""

    __tablename__ = "leave_grant_batches"
    __table_args__ = (
        UniqueConstraint("batch_number"),
        CheckConstraint(
            "status IN ('draft', 'issued', 'void')",
            name="leave_grant_batch_status_allowed",
        ),
        CheckConstraint(
            "period_type IN ('month', 'year')",
            name="leave_grant_batch_period_type_allowed",
        ),
        CheckConstraint(
            "(status = 'issued') = (issued_at IS NOT NULL)",
            name="leave_grant_batch_issued_state_consistent",
        ),
    )

    batch_number: Mapped[str] = mapped_column(String(50), nullable=False)
    period_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    period_type: Mapped[str] = mapped_column(String(10), nullable=False)
    grant_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    issued_by: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    voided_by: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    void_reason: Mapped[str | None] = mapped_column(Text)


class LeaveGrantItem(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """发假发放明细行。

    发放后写 `leave_balance_transactions` 流水，并保持 balance_before/after 恒等约束。
    """

    __tablename__ = "leave_grant_items"
    __table_args__ = (
        UniqueConstraint(
            "batch_id",
            "employment_id",
            "leave_type_id",
            name="uq_leave_grant_items_batch_employment_leave_type",
        ),
        CheckConstraint("grant_days > 0", name="leave_grant_item_days_positive"),
        CheckConstraint(
            "source IN ('manual', 'rule_accrual')",
            name="leave_grant_item_source_allowed",
        ),
        CheckConstraint(
            "status IN ('pending', 'issued')",
            name="leave_grant_item_status_allowed",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="leave_grant_item_validity_order",
        ),
    )

    batch_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("leave_grant_batches.id"),
        nullable=False,
        index=True,
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
    account_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("leave_balance_accounts.id"),
    )
    transaction_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("leave_balance_transactions.id"),
    )
    rule_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("leave_grant_rules.id"),
    )
    grant_days: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    idempotency_key: Mapped[UUID] = mapped_column(Uuid, unique=True, nullable=False)


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
