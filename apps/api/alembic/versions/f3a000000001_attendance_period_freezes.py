"""add attendance period freezes

Revision ID: f3a000000001
Revises: f2a000000002
Create Date: 2026-08-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f3a000000001"
down_revision: str | Sequence[str] | None = "f2a000000002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attendance_period_freezes",
        sa.Column("freeze_type", sa.String(length=20), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("frozen_by", sa.Uuid(), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_by", sa.Uuid(), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_reason", sa.Text(), nullable=True),
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
            "freeze_type IN ('monthly', 'special')",
            name=op.f("ck_attendance_period_freezes_freeze_type_allowed"),
        ),
        sa.CheckConstraint(
            "date_to >= date_from",
            name=op.f("ck_attendance_period_freezes_period_order"),
        ),
        sa.CheckConstraint(
            "(status = 'active' AND released_at IS NULL AND released_by IS NULL "
            "AND release_reason IS NULL) OR "
            "(status = 'released' AND released_at IS NOT NULL "
            "AND released_by IS NOT NULL AND release_reason IS NOT NULL)",
            name=op.f("ck_attendance_period_freezes_release_state_consistent"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'released')",
            name=op.f("ck_attendance_period_freezes_status_allowed"),
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_attendance_period_freezes"),
        ),
    )
    op.create_index(
        op.f("ix_attendance_period_freezes_frozen_by"),
        "attendance_period_freezes",
        ["frozen_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_attendance_period_freezes_released_by"),
        "attendance_period_freezes",
        ["released_by"],
        unique=False,
    )
    op.create_index(
        "ix_attendance_period_freezes_status_range",
        "attendance_period_freezes",
        ["status", "date_from", "date_to"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("attendance_period_freezes")
