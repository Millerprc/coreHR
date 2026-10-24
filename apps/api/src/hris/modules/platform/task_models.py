# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""Platform kernel background task table.

Requirement: D-110 — 长任务（导入、报表、未来生效）从请求链路搬进可重试后台任务框架。
任务表是后台任务的唯一事实来源：状态机、尝试次数、退避时间与领取租约都落在这里。
``payload`` 只允许放任务坐标（批次 id、发起人 id、链路 id、执行原因）这类非个人信息。
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from hris.shared.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


TASK_STATUS_PENDING = "pending"
TASK_STATUS_RUNNING = "running"
TASK_STATUS_SUCCEEDED = "succeeded"
TASK_STATUS_FAILED = "failed"
TASK_STATUS_CANCELED = "canceled"

TASK_STATUSES: frozenset[str] = frozenset(
    {
        TASK_STATUS_PENDING,
        TASK_STATUS_RUNNING,
        TASK_STATUS_SUCCEEDED,
        TASK_STATUS_FAILED,
        TASK_STATUS_CANCELED,
    }
)


class BackgroundTask(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """一条后台任务。

    状态机：``pending → running → succeeded / failed / canceled``。
    失败且仍有重试次数时回到 ``pending`` 并按指数退避推迟 ``next_attempt_at``；
    领取租约（``lease_owner`` / ``lease_expires_at``）超时未续会被回收流程放回队列。
    """

    __tablename__ = "background_tasks"
    __table_args__ = (
        # 约束名按仓库命名约定（ck_<table>_<name>）生成，与迁移 f2p000000001 严格一致。
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'canceled')",
            name="status_allowed",
        ),
        CheckConstraint("attempts >= 0", name="attempts_nonnegative"),
        CheckConstraint("max_attempts >= 1", name="max_attempts_positive"),
    )

    task_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        server_default=text("'pending'"),
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    # Requirement: D-110 — 只写受控错误码，禁止写入原始异常文本（可能含姓名、手机号）。
    error_code: Mapped[str | None] = mapped_column(String(200))
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
        server_default=text("5"),
    )
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=text("now()"),
    )
    lease_owner: Mapped[str | None] = mapped_column(String(120))
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("user_accounts.id"),
    )
    # 幂等键允许多个 NULL（PostgreSQL 唯一约束语义），因此未带幂等键的任务互不冲突。
    idempotency_key: Mapped[str | None] = mapped_column(String(120), unique=True)
    progress: Mapped[str | None] = mapped_column(String(200))
