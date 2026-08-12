"""add encrypted education work and family records

Revision ID: f1e000000001
Revises: f1d000000001
Create Date: 2026-08-12
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f1e000000001"
down_revision: str | Sequence[str] | None = "f1d000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column, sa.Column, sa.Column]:
    return (
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
    )


def _person_constraints(table_name: str) -> tuple[sa.ForeignKeyConstraint, sa.PrimaryKeyConstraint]:
    return (
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["persons.id"],
            name=op.f(f"fk_{table_name}_person_id_persons"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table_name}")),
    )


def upgrade() -> None:
    op.create_table(
        "education_records",
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("education_level_code", sa.String(length=50), nullable=False),
        sa.Column("study_start_date", sa.Date(), nullable=False),
        sa.Column("study_end_date", sa.Date(), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("institution_name_key_version", sa.String(length=50), nullable=False),
        sa.Column("institution_name_nonce", sa.LargeBinary(), nullable=False),
        sa.Column("institution_name_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("masked_institution_name", sa.String(length=300), nullable=False),
        sa.Column("major_name_key_version", sa.String(length=50), nullable=True),
        sa.Column("major_name_nonce", sa.LargeBinary(), nullable=True),
        sa.Column("major_name_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("masked_major_name", sa.String(length=200), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "study_end_date IS NULL OR study_end_date >= study_start_date",
            name=op.f("ck_education_records_study_period_order"),
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name=op.f("ck_education_records_effective_period_order"),
        ),
        *_person_constraints("education_records"),
    )
    op.create_index(op.f("ix_education_records_person_id"), "education_records", ["person_id"])

    op.create_table(
        "work_experiences",
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("work_start_date", sa.Date(), nullable=False),
        sa.Column("work_end_date", sa.Date(), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("employer_name_key_version", sa.String(length=50), nullable=False),
        sa.Column("employer_name_nonce", sa.LargeBinary(), nullable=False),
        sa.Column("employer_name_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("masked_employer_name", sa.String(length=300), nullable=False),
        sa.Column("job_title_key_version", sa.String(length=50), nullable=True),
        sa.Column("job_title_nonce", sa.LargeBinary(), nullable=True),
        sa.Column("job_title_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("masked_job_title", sa.String(length=200), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "work_end_date IS NULL OR work_end_date >= work_start_date",
            name=op.f("ck_work_experiences_work_period_order"),
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name=op.f("ck_work_experiences_effective_period_order"),
        ),
        *_person_constraints("work_experiences"),
    )
    op.create_index(op.f("ix_work_experiences_person_id"), "work_experiences", ["person_id"])

    op.create_table(
        "family_members",
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("relationship_code", sa.String(length=50), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("name_key_version", sa.String(length=50), nullable=False),
        sa.Column("name_nonce", sa.LargeBinary(), nullable=False),
        sa.Column("name_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("masked_name", sa.String(length=200), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name=op.f("ck_family_members_effective_period_order"),
        ),
        *_person_constraints("family_members"),
    )
    op.create_index(op.f("ix_family_members_person_id"), "family_members", ["person_id"])


def downgrade() -> None:
    op.drop_table("family_members")
    op.drop_table("work_experiences")
    op.drop_table("education_records")
