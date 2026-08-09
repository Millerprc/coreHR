"""add contract lifecycle lineage and event idempotency

Revision ID: f3a000000004
Revises: f3a000000003
Create Date: 2026-08-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f3a000000004"
down_revision: str | Sequence[str] | None = "f3a000000003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "contract_records",
        sa.Column("agreement_relationship_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "contract_records",
        sa.Column("predecessor_contract_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "contract_records",
        sa.Column("signed_on", sa.Date(), nullable=True),
    )
    op.add_column(
        "contract_records",
        sa.Column(
            "expiry_notice_days",
            sa.Integer(),
            server_default=sa.text("30"),
            nullable=False,
        ),
    )
    op.add_column(
        "contract_records",
        sa.Column(
            "version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        op.f("fk_contract_records_agreement_relationship_id_agreement_relationships"),
        "contract_records",
        "agreement_relationships",
        ["agreement_relationship_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_contract_records_predecessor_contract_id_contract_records"),
        "contract_records",
        "contract_records",
        ["predecessor_contract_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_contract_records_predecessor_contract_id"),
        "contract_records",
        ["predecessor_contract_id"],
        unique=False,
    )
    op.create_check_constraint(
        op.f("ck_contract_records_single_relation_type"),
        "contract_records",
        "employment_id IS NULL OR agreement_relationship_id IS NULL",
    )
    op.create_check_constraint(
        op.f("ck_contract_records_expiry_notice_days_nonnegative"),
        "contract_records",
        "expiry_notice_days >= 0",
    )
    op.create_check_constraint(
        op.f("ck_contract_records_version_positive"),
        "contract_records",
        "version > 0",
    )

    op.add_column("hr_events", sa.Column("idempotency_key", sa.Uuid(), nullable=True))
    op.add_column(
        "hr_events",
        sa.Column("request_checksum", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        op.f("uq_hr_events_idempotency_key"),
        "hr_events",
        ["idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("uq_hr_events_idempotency_key"),
        "hr_events",
        type_="unique",
    )
    op.drop_column("hr_events", "request_checksum")
    op.drop_column("hr_events", "idempotency_key")

    op.drop_constraint(
        op.f("ck_contract_records_version_positive"),
        "contract_records",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_contract_records_expiry_notice_days_nonnegative"),
        "contract_records",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_contract_records_single_relation_type"),
        "contract_records",
        type_="check",
    )
    op.drop_index(
        op.f("ix_contract_records_predecessor_contract_id"),
        table_name="contract_records",
    )
    op.drop_constraint(
        op.f("fk_contract_records_predecessor_contract_id_contract_records"),
        "contract_records",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_contract_records_agreement_relationship_id_agreement_relationships"),
        "contract_records",
        type_="foreignkey",
    )
    op.drop_column("contract_records", "version")
    op.drop_column("contract_records", "expiry_notice_days")
    op.drop_column("contract_records", "signed_on")
    op.drop_column("contract_records", "predecessor_contract_id")
    op.drop_column("contract_records", "agreement_relationship_id")
