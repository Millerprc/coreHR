# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""批量异动（方案制）的持久化模型。

方案头落在 ``hr_event_batches``；方案明细不另起表，直接复用 ``hr_events`` 行，
通过新增的 ``batch_id`` 列挂到方案头上。这样明细天然继承 hr_events 已有的
事件号、幂等键、审批挂载与执行器语义，避免同一份异动数据存在两套模型。
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, column_property, mapped_column

from hris.modules.workforce.models import HrEvent
from hris.shared.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


# Requirement: HR-BATCH-001 — 方案状态机：草稿 → 已提交 → 通过/驳回，草稿可取消。
BATCH_CHANGE_STATUS_DRAFT = "draft"
BATCH_CHANGE_STATUS_SUBMITTED = "submitted"
BATCH_CHANGE_STATUS_APPROVED = "approved"
BATCH_CHANGE_STATUS_REJECTED = "rejected"
BATCH_CHANGE_STATUS_CANCELLED = "cancelled"
BATCH_CHANGE_STATUSES = (
    BATCH_CHANGE_STATUS_DRAFT,
    BATCH_CHANGE_STATUS_SUBMITTED,
    BATCH_CHANGE_STATUS_APPROVED,
    BATCH_CHANGE_STATUS_REJECTED,
    BATCH_CHANGE_STATUS_CANCELLED,
)

# Requirement: HR-BATCH-002 — 明细在方案草稿阶段处于草稿态，不会被执行器捞起。
BATCH_CHANGE_LINE_STATUS_DRAFT = "draft"
# Requirement: HR-BATCH-003 — 方案提交后，全部明细进入待审批并共享同一个流程实例。
BATCH_CHANGE_LINE_STATUS_PENDING_APPROVAL = "pending_approval"
# Requirement: HR-BATCH-008 — 方案审批通过后明细转就绪，由现有 hr_event 执行器按生效日执行。
BATCH_CHANGE_LINE_STATUS_READY = "ready"
# Requirement: HR-BATCH-008 — 方案审批驳回后明细同步驳回，不再进入执行器。
BATCH_CHANGE_LINE_STATUS_REJECTED = "rejected"

# Requirement: HR-BATCH-001 — 单个方案最多 1000 条异动明细。
BATCH_CHANGE_MAX_LINES = 1000

# Requirement: HR-BATCH-003 — 批量方案的业务对象类型，独立于单条 hr_event 流程实例。
BATCH_CHANGE_BUSINESS_OBJECT_TYPE = "hr_event_batch"

# Requirement: HR-BATCH-009 — 提交审批时未指定流程定义时使用的默认流程编码。
BATCH_CHANGE_WORKFLOW_CODE = "BATCH_CHANGE_APPROVAL"


class HrEventBatch(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """批量异动方案头：一次提交、一次审批、整批执行。"""

    __tablename__ = "hr_event_batches"
    __table_args__ = (
        UniqueConstraint("batch_number"),
        CheckConstraint("line_count >= 0", name="line_count_nonnegative"),
    )

    batch_number: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=BATCH_CHANGE_STATUS_DRAFT,
    )
    line_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reason: Mapped[str | None] = mapped_column(Text)
    workflow_instance_id: Mapped[UUID | None] = mapped_column(Uuid)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)


# Requirement: HR-BATCH-004 — 方案明细复用 hr_events 行，用 batch_id 关联方案头。
# workforce/models.py 由主 agent 独占，因此这里以「追加列 + 列属性」的方式扩展既有映射，
# 不改动 hr_events 原有字段、约束与索引命名约定。
if "batch_id" not in HrEvent.__table__.c:
    HrEvent.__table__.append_column(
        Column(
            "batch_id",
            Uuid,
            ForeignKey("hr_event_batches.id"),
            nullable=True,
            index=True,
        )
    )
    HrEvent.batch_id = column_property(HrEvent.__table__.c.batch_id)
