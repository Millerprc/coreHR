"""add leave balance accounts and immutable ledger

Revision ID: f3a000000002
Revises: f3a000000001
Create Date: 2026-08-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f3a000000002"
down_revision: str | Sequence[str] | None = "f3a000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "leave_balance_accounts",
        sa.Column("employment_id", sa.Uuid(), nullable=False),
        sa.Column("leave_type_id", sa.Uuid(), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column(
            "current_balance",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
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
            "period_year BETWEEN 2000 AND 2200",
            name=op.f("ck_leave_balance_accounts_period_year_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'closed')",
            name=op.f("ck_leave_balance_accounts_status_allowed"),
        ),
        sa.CheckConstraint(
            "unit IN ('day', 'hour')",
            name=op.f("ck_leave_balance_accounts_unit_allowed"),
        ),
        sa.CheckConstraint(
            "version >= 0",
            name=op.f("ck_leave_balance_accounts_version_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["employment_id"],
            ["employments.id"],
            name=op.f("fk_leave_balance_accounts_employment_id_employments"),
        ),
        sa.ForeignKeyConstraint(
            ["leave_type_id"],
            ["leave_types.id"],
            name=op.f("fk_leave_balance_accounts_leave_type_id_leave_types"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_leave_balance_accounts")),
        sa.UniqueConstraint(
            "employment_id",
            "leave_type_id",
            "period_year",
            name=op.f("uq_leave_balance_accounts_employment_id"),
        ),
    )
    op.create_index(
        op.f("ix_leave_balance_accounts_employment_id"),
        "leave_balance_accounts",
        ["employment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_leave_balance_accounts_leave_type_id"),
        "leave_balance_accounts",
        ["leave_type_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_leave_balance_accounts_period_year"),
        "leave_balance_accounts",
        ["period_year"],
        unique=False,
    )

    op.create_table(
        "leave_balance_transactions",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_type", sa.String(length=30), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("balance_before", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("balance_after", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("account_version", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("request_checksum", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
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
            "amount <> 0",
            name=op.f("ck_leave_balance_transactions_amount_non_zero"),
        ),
        sa.CheckConstraint(
            "account_version > 0",
            name=op.f("ck_leave_balance_transactions_account_version_positive"),
        ),
        sa.CheckConstraint(
            "balance_after = balance_before + amount",
            name=op.f("ck_leave_balance_transactions_balance_math_consistent"),
        ),
        sa.CheckConstraint(
            "transaction_type IN "
            "('grant', 'adjustment', 'carryover', 'accrual', 'usage', 'reversal')",
            name=op.f("ck_leave_balance_transactions_transaction_type_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["leave_balance_accounts.id"],
            name=op.f("fk_leave_balance_transactions_account_id_leave_balance_accounts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_leave_balance_transactions")),
        sa.UniqueConstraint(
            "idempotency_key",
            name=op.f("uq_leave_balance_transactions_idempotency_key"),
        ),
    )
    op.create_index(
        "ix_leave_balance_transactions_account_version",
        "leave_balance_transactions",
        ["account_id", "account_version"],
        unique=False,
    )
    op.create_index(
        op.f("ix_leave_balance_transactions_actor_id"),
        "leave_balance_transactions",
        ["actor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_leave_balance_transactions_effective_date"),
        "leave_balance_transactions",
        ["effective_date"],
        unique=False,
    )
    op.create_index(
        "ix_leave_balance_transactions_source",
        "leave_balance_transactions",
        ["source_type", "source_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("leave_balance_transactions")
    op.drop_table("leave_balance_accounts")
