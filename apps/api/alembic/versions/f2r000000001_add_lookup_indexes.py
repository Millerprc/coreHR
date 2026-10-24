# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""add indexes for todo, audit and punch lookup paths

补齐三处「有真实查询、但没索引」的读路径。

Requirement: D-115 — 审计报告指出：待办查询、审计日志过滤、打卡明细取数
在数据量上来后都是全表扫。本迁移按**实际查询条件**建索引，不是按「哪些列看着像该有索引」。

取舍说明：

- **只建索引，不改任何查询、不改任何业务语义**。索引是纯读路径优化，
  对写路径只增加索引维护成本，不改变结果。
- **复合索引的列序 = 查询条件的顺序**：
  ``workflow_tasks`` 用 ``(assignee_ref, status, created_at)`` ——
  前两列是待办查询的过滤条件（``workflow/queries.py::list_tasks``），
  第三列是它的排序（``created_at DESC``），这样「我的待办」是一次有序索引扫描，
  连 ORDER BY 的排序都省了，列表与 count 两条语句共用它。
- **不删既有单列索引**（``attendance_punches.employment_id`` / ``punched_at``）：
  单独按时间取数（如全量导出某段打卡）用不上复合索引的前导列，
  留着更稳妥。复合索引与单列索引的重复维护成本记在待确认清单里，
  等有了真实慢查询数据再决定收敛。
- **审计日志两个索引分开建**而不是合成 ``(action, object_type)``：
  两者是**互斥的独立过滤维度**（用户要么按动作查、要么按对象类型查），
  合成复合索引会让「只按对象类型查」用不上前导列。

Revision ID: f2r000000001
Revises: f2q000000001
Create Date: 2026-10-24
"""

from collections.abc import Sequence

from alembic import op


revision: str = "f2r000000001"
down_revision: str | Sequence[str] | None = "f2q000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """建立四个索引。"""
    # 待办查询：过滤 (assignee_ref, status) + 排序 (created_at DESC)
    op.create_index(
        "ix_workflow_tasks_assignee_status_created",
        "workflow_tasks",
        ["assignee_ref", "status", "created_at"],
    )
    # 审计过滤：动作 / 对象类型（两个独立维度）
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_object_type", "audit_logs", ["object_type"])
    # 打卡明细：某人 + 时间区间
    op.create_index(
        "ix_attendance_punches_employment_punched_at",
        "attendance_punches",
        ["employment_id", "punched_at"],
    )


def downgrade() -> None:
    """按相反顺序删掉本迁移建的索引。"""
    op.drop_index(
        "ix_attendance_punches_employment_punched_at",
        table_name="attendance_punches",
    )
    op.drop_index("ix_audit_logs_object_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index(
        "ix_workflow_tasks_assignee_status_created",
        table_name="workflow_tasks",
    )
