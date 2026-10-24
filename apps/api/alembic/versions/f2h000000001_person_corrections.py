# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""person field versions (人员基础信息修正记录)

Revision ID: f2h000000001
Revises: f2g000000001
Create Date: 2026-10-24

Requirement: D-095 — 基础信息的「编辑」与「修正」拆成两个语义不同的操作：
「编辑」直接覆盖主档（立即生效）；「修正」不覆盖主档，而是把
「从某一天起正确的值」登记成一条带生效日期的字段级版本记录。
生效日期切片按「人 + 字段」维度维护，形态对齐 employment_legal_entity_relations：
同一字段的相邻版本首尾相接（上一条的 effective_to 等于下一条
effective_from 的前一天），当前结果 = 主档登记值 + 生效日期 ≤ 查询日期的
最后一条修正。
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f2h000000001"
down_revision: str | Sequence[str] | None = "f2g000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "person_field_versions",
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("field_code", sa.String(length=50), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("new_value", sa.String(length=200), nullable=True),
        sa.Column("change_reason", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
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
            "version > 0",
            name=op.f("ck_person_field_versions_version_positive"),
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name=op.f("ck_person_field_versions_effective_period_order"),
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["persons.id"],
            name=op.f("fk_person_field_versions_person_id_persons"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_person_field_versions")),
        sa.UniqueConstraint(
            "person_id",
            "field_code",
            "version",
            name="uq_person_field_versions_person_field_version",
        ),
        sa.UniqueConstraint(
            "person_id",
            "field_code",
            "effective_from",
            name="uq_person_field_versions_person_field_effective_from",
        ),
    )
    op.create_index(
        op.f("ix_person_field_versions_person_id"),
        "person_field_versions",
        ["person_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_person_field_versions_field_code"),
        "person_field_versions",
        ["field_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_person_field_versions_created_by"),
        "person_field_versions",
        ["created_by"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_person_field_versions_created_by"),
        table_name="person_field_versions",
    )
    op.drop_index(
        op.f("ix_person_field_versions_field_code"),
        table_name="person_field_versions",
    )
    op.drop_index(
        op.f("ix_person_field_versions_person_id"),
        table_name="person_field_versions",
    )
    op.drop_table("person_field_versions")
