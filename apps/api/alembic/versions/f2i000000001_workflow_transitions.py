# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""add workflow transition history

Revision ID: f2i000000001
Revises: f2h000000001
Create Date: 2026-10-24
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f2i000000001"
down_revision: str | Sequence[str] | None = "f2h000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_APPEND_ONLY_FUNCTION = """
CREATE OR REPLACE FUNCTION corehr_workflow_transitions_append_only()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'workflow_transitions is append-only: % is not allowed', TG_OP
        USING ERRCODE = 'restrict_violation';
END;
$$
"""


def upgrade() -> None:
    op.create_table(
        "workflow_transitions",
        sa.Column("instance_id", sa.Uuid(), nullable=False),
        sa.Column("from_node_code", sa.String(length=80), nullable=True),
        sa.Column("to_node_code", sa.String(length=80), nullable=True),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=False),
        sa.Column("to_status", sa.String(length=30), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ('approve', 'reject', 'rollback', 'cancel', 'transfer', "
            "'add_sign', 'return', 'timeout_reminder')",
            name=op.f("ck_workflow_transitions_action_allowed"),
        ),
        sa.CheckConstraint(
            "from_status IN ('running', 'returned', 'completed', 'rejected', "
            "'withdrawn', 'cancelled')",
            name=op.f("ck_workflow_transitions_from_status_allowed"),
        ),
        sa.CheckConstraint(
            "to_status IN ('running', 'returned', 'completed', 'rejected', "
            "'withdrawn', 'cancelled')",
            name=op.f("ck_workflow_transitions_to_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["instance_id"],
            ["workflow_instances.id"],
            name=op.f("fk_workflow_transitions_instance_id_workflow_instances"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_transitions")),
    )
    op.create_index(
        op.f("ix_workflow_transitions_instance_id"),
        "workflow_transitions",
        ["instance_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_transitions_instance_created",
        "workflow_transitions",
        ["instance_id", "created_at"],
        unique=False,
    )
    # 调度器给超时任务发提醒后写这个标记，避免重复提醒；不代表任何审批结论。
    op.add_column(
        "workflow_tasks",
        sa.Column("overdue_reminded_at", sa.DateTime(timezone=True), nullable=True),
    )
    # 流转历史只追加：数据库层禁止 UPDATE / DELETE。
    op.execute(_APPEND_ONLY_FUNCTION)
    op.execute(
        """
CREATE TRIGGER trg_workflow_transitions_append_only
BEFORE UPDATE OR DELETE ON workflow_transitions
FOR EACH ROW
EXECUTE FUNCTION corehr_workflow_transitions_append_only()
"""
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_workflow_transitions_append_only ON workflow_transitions"
    )
    op.execute("DROP FUNCTION IF EXISTS corehr_workflow_transitions_append_only()")
    op.drop_index(
        "ix_workflow_transitions_instance_created",
        table_name="workflow_transitions",
    )
    op.drop_index(
        op.f("ix_workflow_transitions_instance_id"),
        table_name="workflow_transitions",
    )
    op.drop_table("workflow_transitions")
    op.drop_column("workflow_tasks", "overdue_reminded_at")
