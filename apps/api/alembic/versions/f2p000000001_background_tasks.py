# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""background tasks table

平台内核后台任务表（可重试长任务执行框架）。

Requirement: D-110 — 长任务（导入、报表、未来生效）从请求链路搬进可重试后台任务框架。
任务表承载任务类型、载荷、状态机、尝试次数、退避时间与领取租约；领取用
``FOR UPDATE SKIP LOCKED``，多 Worker 实例并行运行不会重复消费同一条任务。
错误码列只允许写受控值，任务载荷不得携带姓名、手机号等个人信息。

Revision ID: f2p000000001
Revises: f2n000000001
Create Date: 2026-10-24
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f2p000000001"
down_revision: str | Sequence[str] | None = "f2n000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Requirement: D-110 — 建立后台任务表。

    状态机：``pending → running → succeeded / failed / canceled``。
    ``attempts`` 与 ``max_attempts`` 约束重试上限，
    ``next_attempt_at`` 承载指数退避，``lease_owner`` / ``lease_expires_at``
    承载领取租约（Worker 崩溃后由回收流程把任务放回 ``pending``）。
    """

    op.create_table(
        "background_tasks",
        sa.Column("task_type", sa.String(length=80), nullable=False),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "payload",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=200), nullable=True),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "max_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("5"),
        ),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("lease_owner", sa.String(length=120), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=120), nullable=True),
        sa.Column("progress", sa.String(length=200), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["user_accounts.id"],
            name=op.f("fk_background_tasks_created_by_user_accounts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_background_tasks")),
        sa.UniqueConstraint(
            "idempotency_key",
            name=op.f("uq_background_tasks_idempotency_key"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'canceled')",
            name=op.f("ck_background_tasks_status_allowed"),
        ),
        sa.CheckConstraint(
            "attempts >= 0",
            name=op.f("ck_background_tasks_attempts_nonnegative"),
        ),
        sa.CheckConstraint(
            "max_attempts >= 1",
            name=op.f("ck_background_tasks_max_attempts_positive"),
        ),
    )
    op.create_index(
        op.f("ix_background_tasks_task_type"),
        "background_tasks",
        ["task_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_background_tasks_status"),
        "background_tasks",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_background_tasks_next_attempt_at"),
        "background_tasks",
        ["next_attempt_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_background_tasks_lease_expires_at"),
        "background_tasks",
        ["lease_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    """回滚后台任务表。"""

    op.drop_index(
        op.f("ix_background_tasks_lease_expires_at"),
        table_name="background_tasks",
    )
    op.drop_index(
        op.f("ix_background_tasks_next_attempt_at"),
        table_name="background_tasks",
    )
    op.drop_index(op.f("ix_background_tasks_status"), table_name="background_tasks")
    op.drop_index(
        op.f("ix_background_tasks_task_type"),
        table_name="background_tasks",
    )
    op.drop_table("background_tasks")
