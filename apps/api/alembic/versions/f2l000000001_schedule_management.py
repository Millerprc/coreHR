# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""schedule types, draft/publish batches, swaps and immutable shift rule binding

排班管理（复刻 Moka「排班管理 / 换班记录」）：排班类型、轮班周期、弹性窗口、
排班草稿与发布批次、换班记录；同时把班次改为绑定不可变的规则集版本行。

Requirement: D-107 —— 轮班周期、弹性窗口、同日多班次只建规则容器与占位约束，
取值语义待企业输入。

Revision ID: f2l000000001
Revises: f2k000000001
Create Date: 2026-10-24
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f2l000000001"
down_revision: str | Sequence[str] | None = "f2k000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schedule_types",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("requires_shift_cycle", sa.Boolean(), nullable=False),
        sa.Column("requires_flexible_window", sa.Boolean(), nullable=False),
        sa.Column("allows_multiple_shifts_per_day", sa.Boolean(), nullable=False),
        sa.Column("requires_publish", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
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
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name=op.f("ck_schedule_types_schedule_type_status_allowed"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schedule_types")),
        sa.UniqueConstraint("code", name=op.f("uq_schedule_types_code")),
    )

    op.create_table(
        "shift_cycles",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("schedule_type_id", sa.Uuid(), nullable=False),
        sa.Column("cycle_start_date", sa.Date(), nullable=False),
        sa.Column("cycle_days", sa.Integer(), nullable=False),
        sa.Column("shift_sequence", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
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
        sa.CheckConstraint(
            "cycle_days > 0",
            name=op.f("ck_shift_cycles_shift_cycle_days_positive"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'expired')",
            name=op.f("ck_shift_cycles_shift_cycle_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["schedule_type_id"],
            ["schedule_types.id"],
            name=op.f("fk_shift_cycles_schedule_type_id_schedule_types"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shift_cycles")),
        sa.UniqueConstraint("code", name=op.f("uq_shift_cycles_code")),
    )
    op.create_index(
        op.f("ix_shift_cycles_schedule_type_id"),
        "shift_cycles",
        ["schedule_type_id"],
        unique=False,
    )

    op.create_table(
        "flexible_windows",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("schedule_type_id", sa.Uuid(), nullable=False),
        sa.Column("arrival_window_start", sa.Time(), nullable=True),
        sa.Column("arrival_window_end", sa.Time(), nullable=True),
        sa.Column("departure_window_start", sa.Time(), nullable=True),
        sa.Column("departure_window_end", sa.Time(), nullable=True),
        sa.Column("standard_daily_minutes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
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
        sa.CheckConstraint(
            "standard_daily_minutes IS NULL OR standard_daily_minutes > 0",
            name=op.f("ck_flexible_windows_flexible_window_standard_minutes_positive"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'expired')",
            name=op.f("ck_flexible_windows_flexible_window_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["schedule_type_id"],
            ["schedule_types.id"],
            name=op.f("fk_flexible_windows_schedule_type_id_schedule_types"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_flexible_windows")),
        sa.UniqueConstraint("code", name=op.f("uq_flexible_windows_code")),
    )
    op.create_index(
        op.f("ix_flexible_windows_schedule_type_id"),
        "flexible_windows",
        ["schedule_type_id"],
        unique=False,
    )

    op.create_table(
        "schedule_publish_batches",
        sa.Column("batch_number", sa.String(length=50), nullable=False),
        sa.Column("period_code", sa.String(length=20), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("schedule_type_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("published_count", sa.Integer(), nullable=False),
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
        sa.CheckConstraint(
            "period_end >= period_start",
            name=op.f("ck_schedule_publish_batches_schedule_publish_batch_period_order"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'void')",
            name=op.f("ck_schedule_publish_batches_schedule_publish_batch_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["schedule_type_id"],
            ["schedule_types.id"],
            name=op.f("fk_schedule_publish_batches_schedule_type_id_schedule_types"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schedule_publish_batches")),
        sa.UniqueConstraint(
            "batch_number",
            name=op.f("uq_schedule_publish_batches_batch_number"),
        ),
    )
    op.create_index(
        op.f("ix_schedule_publish_batches_created_by"),
        "schedule_publish_batches",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_schedule_publish_batches_period_code"),
        "schedule_publish_batches",
        ["period_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_schedule_publish_batches_published_by"),
        "schedule_publish_batches",
        ["published_by"],
        unique=False,
    )

    op.create_table(
        "schedule_swaps",
        sa.Column("request_number", sa.String(length=50), nullable=False),
        sa.Column("employment_id_a", sa.Uuid(), nullable=False),
        sa.Column("employment_id_b", sa.Uuid(), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("original_shift_id", sa.Uuid(), nullable=True),
        sa.Column("new_shift_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "employment_id_a <> employment_id_b",
            name=op.f("ck_schedule_swaps_schedule_swap_distinct_employments"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'rejected', 'cancelled')",
            name=op.f("ck_schedule_swaps_schedule_swap_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["employment_id_a"],
            ["employments.id"],
            name=op.f("fk_schedule_swaps_employment_id_a_employments"),
        ),
        sa.ForeignKeyConstraint(
            ["employment_id_b"],
            ["employments.id"],
            name=op.f("fk_schedule_swaps_employment_id_b_employments"),
        ),
        sa.ForeignKeyConstraint(
            ["new_shift_id"],
            ["shifts.id"],
            name=op.f("fk_schedule_swaps_new_shift_id_shifts"),
        ),
        sa.ForeignKeyConstraint(
            ["original_shift_id"],
            ["shifts.id"],
            name=op.f("fk_schedule_swaps_original_shift_id_shifts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schedule_swaps")),
        sa.UniqueConstraint(
            "request_number",
            name=op.f("uq_schedule_swaps_request_number"),
        ),
    )
    op.create_index(
        op.f("ix_schedule_swaps_decided_by"),
        "schedule_swaps",
        ["decided_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_schedule_swaps_employment_id_a"),
        "schedule_swaps",
        ["employment_id_a"],
        unique=False,
    )
    op.create_index(
        op.f("ix_schedule_swaps_employment_id_b"),
        "schedule_swaps",
        ["employment_id_b"],
        unique=False,
    )
    op.create_index(
        op.f("ix_schedule_swaps_requested_by"),
        "schedule_swaps",
        ["requested_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_schedule_swaps_work_date"),
        "schedule_swaps",
        ["work_date"],
        unique=False,
    )

    # —— 排班结果：区分草稿与已发布，并承载发布批次 ——
    op.add_column(
        "schedule_assignments",
        sa.Column("batch_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "schedule_assignments",
        sa.Column("publish_status", sa.String(length=20), server_default="published", nullable=False),
    )
    op.add_column(
        "schedule_assignments",
        sa.Column("sequence_no", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "schedule_assignments",
        sa.Column("schedule_type_id", sa.Uuid(), nullable=True),
    )
    op.alter_column("schedule_assignments", "publish_status", server_default=None)
    op.alter_column("schedule_assignments", "sequence_no", server_default=None)
    op.drop_constraint(
        op.f("uq_schedule_assignments_employment_id"),
        "schedule_assignments",
        type_="unique",
    )
    op.create_unique_constraint(
        op.f("uq_schedule_assignments_employment_date_sequence"),
        "schedule_assignments",
        ["employment_id", "work_date", "sequence_no"],
    )
    op.create_foreign_key(
        op.f("fk_schedule_assignments_batch_id_schedule_publish_batches"),
        "schedule_assignments",
        "schedule_publish_batches",
        ["batch_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_schedule_assignments_schedule_type_id_schedule_types"),
        "schedule_assignments",
        "schedule_types",
        ["schedule_type_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_schedule_assignments_batch_id"),
        "schedule_assignments",
        ["batch_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_schedule_assignments_schedule_type_id"),
        "schedule_assignments",
        ["schedule_type_id"],
        unique=False,
    )

    # —— 班次绑定不可变的规则集版本 ——
    op.add_column("shifts", sa.Column("rule_set_version", sa.Integer(), nullable=True))
    op.add_column(
        "shifts",
        sa.Column("rule_snapshot", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
    )
    op.alter_column("shifts", "rule_snapshot", server_default=None)
    # 既有班次回填规则集版本快照，避免旧班次在规则集发布新版本后静默跟随新规则。
    op.execute(
        sa.text(
            """
            UPDATE shifts s
            SET rule_set_version = rs.version,
                rule_snapshot = json_build_object(
                    'code', rs.code,
                    'version', rs.version,
                    'timezone', rs.timezone,
                    'rules', rs.rules,
                    'effective_from', rs.effective_from,
                    'effective_to', rs.effective_to
                )::json
            FROM attendance_rule_sets rs
            WHERE s.rule_set_id = rs.id
              AND (s.rule_snapshot IS NULL OR s.rule_snapshot::text = '{}')
            """
        )
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_schedule_assignments_schedule_type_id"), table_name="schedule_assignments")
    op.drop_index(op.f("ix_schedule_assignments_batch_id"), table_name="schedule_assignments")
    op.drop_constraint(
        op.f("fk_schedule_assignments_schedule_type_id_schedule_types"),
        "schedule_assignments",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_schedule_assignments_batch_id_schedule_publish_batches"),
        "schedule_assignments",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("uq_schedule_assignments_employment_date_sequence"),
        "schedule_assignments",
        type_="unique",
    )
    op.create_unique_constraint(
        op.f("uq_schedule_assignments_employment_id"),
        "schedule_assignments",
        ["employment_id", "work_date"],
    )
    op.drop_column("schedule_assignments", "schedule_type_id")
    op.drop_column("schedule_assignments", "sequence_no")
    op.drop_column("schedule_assignments", "publish_status")
    op.drop_column("schedule_assignments", "batch_id")

    op.drop_column("shifts", "rule_snapshot")
    op.drop_column("shifts", "rule_set_version")

    op.drop_index(op.f("ix_schedule_swaps_work_date"), table_name="schedule_swaps")
    op.drop_index(op.f("ix_schedule_swaps_requested_by"), table_name="schedule_swaps")
    op.drop_index(op.f("ix_schedule_swaps_employment_id_b"), table_name="schedule_swaps")
    op.drop_index(op.f("ix_schedule_swaps_employment_id_a"), table_name="schedule_swaps")
    op.drop_index(op.f("ix_schedule_swaps_decided_by"), table_name="schedule_swaps")
    op.drop_table("schedule_swaps")

    op.drop_index(
        op.f("ix_schedule_publish_batches_published_by"),
        table_name="schedule_publish_batches",
    )
    op.drop_index(
        op.f("ix_schedule_publish_batches_period_code"),
        table_name="schedule_publish_batches",
    )
    op.drop_index(
        op.f("ix_schedule_publish_batches_created_by"),
        table_name="schedule_publish_batches",
    )
    op.drop_table("schedule_publish_batches")

    op.drop_index(
        op.f("ix_flexible_windows_schedule_type_id"),
        table_name="flexible_windows",
    )
    op.drop_table("flexible_windows")

    op.drop_index(op.f("ix_shift_cycles_schedule_type_id"), table_name="shift_cycles")
    op.drop_table("shift_cycles")

    op.drop_table("schedule_types")
