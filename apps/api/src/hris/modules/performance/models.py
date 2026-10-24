# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""Performance OKR tables: cycles, objectives (O) and key results (KR)."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from hris.shared.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


# Requirement: HR-PERF-001 — 绩效周期类型固定为季度、年度、专项三种，值域由代码层定义。
CYCLE_TYPE_QUARTERLY = "quarterly"
CYCLE_TYPE_ANNUAL = "annual"
CYCLE_TYPE_SPECIAL = "special"
CYCLE_TYPES = (CYCLE_TYPE_QUARTERLY, CYCLE_TYPE_ANNUAL, CYCLE_TYPE_SPECIAL)

# Requirement: HR-PERF-002 — 绩效周期状态固定为草稿、进行中、已关闭三种。
CYCLE_STATUS_DRAFT = "draft"
CYCLE_STATUS_ACTIVE = "active"
CYCLE_STATUS_CLOSED = "closed"
CYCLE_STATUSES = (CYCLE_STATUS_DRAFT, CYCLE_STATUS_ACTIVE, CYCLE_STATUS_CLOSED)

# Requirement: HR-PERF-008 — 目标与关键结果共用一套状态值域，归档项不计入权重与计分卡。
OKR_STATUS_DRAFT = "draft"
OKR_STATUS_SUBMITTED = "submitted"
OKR_STATUS_APPROVED = "approved"
OKR_STATUS_ARCHIVED = "archived"
OKR_STATUSES = (
    OKR_STATUS_DRAFT,
    OKR_STATUS_SUBMITTED,
    OKR_STATUS_APPROVED,
    OKR_STATUS_ARCHIVED,
)

# Requirement: HR-PERF-004 — 单个目标或关键结果的权重上限为 100。
MAX_OKR_WEIGHT = Decimal("100")

# Requirement: HR-PERF-007 — 关键结果得分区间为 0 到 100。
MIN_OKR_SCORE = Decimal("0")
MAX_OKR_SCORE = Decimal("100")


class PerformanceCycle(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "performance_cycles"
    __table_args__ = (
        UniqueConstraint("code"),
        CheckConstraint(
            "end_date >= start_date",
            name="cycle_date_order",
        ),
        CheckConstraint(
            "cycle_type IN ('quarterly', 'annual', 'special')",
            name="cycle_type_allowed",
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'closed')",
            name="cycle_status_allowed",
        ),
    )

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    cycle_type: Mapped[str] = mapped_column(String(30), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=CYCLE_STATUS_DRAFT,
        index=True,
    )


class PerformanceObjective(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "performance_objectives"
    __table_args__ = (
        CheckConstraint(
            "weight > 0",
            name="objective_weight_positive",
        ),
        CheckConstraint(
            "weight <= 100",
            name="objective_weight_upper_bound",
        ),
        CheckConstraint(
            "status IN ('draft', 'submitted', 'approved', 'archived')",
            name="objective_status_allowed",
        ),
    )

    cycle_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("performance_cycles.id"),
        nullable=False,
        index=True,
    )
    person_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("persons.id"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    weight: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=OKR_STATUS_DRAFT,
        index=True,
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class PerformanceKeyResult(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "performance_key_results"
    __table_args__ = (
        CheckConstraint(
            "weight > 0",
            name="key_result_weight_positive",
        ),
        CheckConstraint(
            "weight <= 100",
            name="key_result_weight_upper_bound",
        ),
        CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)",
            name="key_result_score_range",
        ),
        CheckConstraint(
            "status IN ('draft', 'submitted', 'approved', 'archived')",
            name="key_result_status_allowed",
        ),
    )

    objective_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("performance_objectives.id"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    target_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    actual_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    unit: Mapped[str | None] = mapped_column(String(50))
    weight: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=OKR_STATUS_DRAFT,
        index=True,
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
