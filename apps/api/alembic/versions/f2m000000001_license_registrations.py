# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""license registrations table

授权注册表（Open Core 授权 SDK · Wave 1）。

Requirement: D-108 — 只存 Token 摘要（sha256），不存明文；
`license_id` 唯一保证同一份授权不会双活；过期不删记录，保留审计链。

Revision ID: f2m000000001
Revises: f2l000000001
Create Date: 2026-10-24
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f2m000000001"
down_revision: str | Sequence[str] | None = "f2l000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "license_registrations",
        sa.Column("license_id", sa.String(length=120), nullable=False),
        sa.Column("licensee", sa.String(length=200), nullable=False),
        sa.Column("licensee_short", sa.String(length=120), nullable=False),
        sa.Column("tier", sa.String(length=30), nullable=False),
        sa.Column("entitlements", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("not_before", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seat_limit", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_by", sa.String(length=120), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
            "seat_limit IS NULL OR seat_limit >= 0",
            name=op.f("ck_license_registrations_seat_limit_nonnegative"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'expired', 'revoked', 'superseded', 'not_yet_valid')",
            name=op.f("ck_license_registrations_status_allowed"),
        ),
        sa.CheckConstraint(
            "tier IN ('community', 'developer', 'commercial')",
            name=op.f("ck_license_registrations_tier_allowed"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_license_registrations")),
        sa.UniqueConstraint(
            "license_id", name=op.f("uq_license_registrations_license_id")
        ),
    )
    op.create_index(
        op.f("ix_license_registrations_activated_at"),
        "license_registrations",
        ["activated_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_license_registrations_status"),
        "license_registrations",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_license_registrations_status"),
        table_name="license_registrations",
    )
    op.drop_index(
        op.f("ix_license_registrations_activated_at"),
        table_name="license_registrations",
    )
    op.drop_table("license_registrations")
