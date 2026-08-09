"""add application hire conversion lineage

Revision ID: f3a000000003
Revises: f3a000000002
Create Date: 2026-08-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f3a000000003"
down_revision: str | Sequence[str] | None = "f3a000000002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "application_hire_conversions",
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("employment_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("request_checksum", sa.String(length=64), nullable=False),
        sa.Column("planned_start_date", sa.Date(), nullable=False),
        sa.Column("employee_type_code", sa.String(length=50), nullable=False),
        sa.Column("converted_by", sa.Uuid(), nullable=False),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=False),
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
            ["application_id"],
            ["job_applications.id"],
            name=op.f("fk_application_hire_conversions_application_id_job_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_application_hire_conversions_candidate_id_candidates"),
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["persons.id"],
            name=op.f("fk_application_hire_conversions_person_id_persons"),
        ),
        sa.ForeignKeyConstraint(
            ["employment_id"],
            ["employments.id"],
            name=op.f("fk_application_hire_conversions_employment_id_employments"),
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["employment_assignments.id"],
            name=op.f(
                "fk_application_hire_conversions_assignment_id_employment_assignments"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_hire_conversions")),
        sa.UniqueConstraint(
            "application_id",
            name=op.f("uq_application_hire_conversions_application_id"),
        ),
        sa.UniqueConstraint(
            "employment_id",
            name=op.f("uq_application_hire_conversions_employment_id"),
        ),
        sa.UniqueConstraint(
            "assignment_id",
            name=op.f("uq_application_hire_conversions_assignment_id"),
        ),
        sa.UniqueConstraint(
            "idempotency_key",
            name=op.f("uq_application_hire_conversions_idempotency_key"),
        ),
    )
    op.create_index(
        op.f("ix_application_hire_conversions_candidate_id"),
        "application_hire_conversions",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_application_hire_conversions_person_id"),
        "application_hire_conversions",
        ["person_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("application_hire_conversions")
