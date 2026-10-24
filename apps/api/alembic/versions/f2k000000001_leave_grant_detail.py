# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""leave grant rules, batches and items

发假明细（复刻 Moka「发假明细」）：额度规则、发放批次、发放明细行。

Requirement: D-107 —— 计提频率、工龄折算、封顶、清零、结转上限、有效期、离职处理
只建可配置字段容器，取值语义待企业输入，字段一律可空。

Revision ID: f2k000000001
Revises: f2j000000001
Create Date: 2026-10-24
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f2k000000001"
down_revision: str | Sequence[str] | None = "f2j000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "leave_grant_rules",
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("leave_type_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("entitlement_days", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("seniority_min_years", sa.Integer(), nullable=True),
        sa.Column("seniority_max_years", sa.Integer(), nullable=True),
        sa.Column("proration_method", sa.String(length=30), nullable=True),
        sa.Column("accrual_frequency", sa.String(length=30), nullable=True),
        sa.Column("cap_days", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("carryover_cap_days", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("reset_policy", sa.String(length=30), nullable=True),
        sa.Column("termination_policy", sa.String(length=30), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
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
            "cap_days IS NULL OR cap_days >= 0",
            name=op.f("ck_leave_grant_rules_leave_grant_rule_cap_non_negative"),
        ),
        sa.CheckConstraint(
            "carryover_cap_days IS NULL OR carryover_cap_days >= 0",
            name=op.f("ck_leave_grant_rules_leave_grant_rule_carryover_non_negative"),
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name=op.f("ck_leave_grant_rules_leave_grant_rule_period_order"),
        ),
        sa.CheckConstraint(
            "entitlement_days IS NULL OR entitlement_days > 0",
            name=op.f("ck_leave_grant_rules_leave_grant_rule_entitlement_positive"),
        ),
        sa.CheckConstraint(
            "seniority_min_years IS NULL OR seniority_max_years IS NULL "
            "OR seniority_max_years >= seniority_min_years",
            name=op.f("ck_leave_grant_rules_leave_grant_rule_seniority_order"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'expired')",
            name=op.f("ck_leave_grant_rules_leave_grant_rule_status_allowed"),
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name=op.f("ck_leave_grant_rules_leave_grant_rule_validity_order"),
        ),
        sa.ForeignKeyConstraint(
            ["leave_type_id"],
            ["leave_types.id"],
            name=op.f("fk_leave_grant_rules_leave_type_id_leave_types"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_leave_grant_rules")),
        sa.UniqueConstraint(
            "code",
            "version",
            name=op.f("uq_leave_grant_rules_code"),
        ),
    )
    op.create_index(
        op.f("ix_leave_grant_rules_leave_type_id"),
        "leave_grant_rules",
        ["leave_type_id"],
        unique=False,
    )

    op.create_table(
        "leave_grant_batches",
        sa.Column("batch_number", sa.String(length=50), nullable=False),
        sa.Column("period_code", sa.String(length=20), nullable=False),
        sa.Column("period_type", sa.String(length=10), nullable=False),
        sa.Column("grant_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_by", sa.Uuid(), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by", sa.Uuid(), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
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
            "(status = 'issued') = (issued_at IS NOT NULL)",
            name=op.f("ck_leave_grant_batches_leave_grant_batch_issued_state_consistent"),
        ),
        sa.CheckConstraint(
            "period_type IN ('month', 'year')",
            name=op.f("ck_leave_grant_batches_leave_grant_batch_period_type_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'issued', 'void')",
            name=op.f("ck_leave_grant_batches_leave_grant_batch_status_allowed"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_leave_grant_batches")),
        sa.UniqueConstraint(
            "batch_number",
            name=op.f("uq_leave_grant_batches_batch_number"),
        ),
    )
    op.create_index(
        op.f("ix_leave_grant_batches_created_by"),
        "leave_grant_batches",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_leave_grant_batches_issued_by"),
        "leave_grant_batches",
        ["issued_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_leave_grant_batches_period_code"),
        "leave_grant_batches",
        ["period_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_leave_grant_batches_voided_by"),
        "leave_grant_batches",
        ["voided_by"],
        unique=False,
    )

    op.create_table(
        "leave_grant_items",
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("employment_id", sa.Uuid(), nullable=False),
        sa.Column("leave_type_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("transaction_id", sa.Uuid(), nullable=True),
        sa.Column("rule_id", sa.Uuid(), nullable=True),
        sa.Column("grant_days", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
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
            "grant_days > 0",
            name=op.f("ck_leave_grant_items_leave_grant_item_days_positive"),
        ),
        sa.CheckConstraint(
            "source IN ('manual', 'rule_accrual')",
            name=op.f("ck_leave_grant_items_leave_grant_item_source_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'issued')",
            name=op.f("ck_leave_grant_items_leave_grant_item_status_allowed"),
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name=op.f("ck_leave_grant_items_leave_grant_item_validity_order"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["leave_balance_accounts.id"],
            name=op.f("fk_leave_grant_items_account_id_leave_balance_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["leave_grant_batches.id"],
            name=op.f("fk_leave_grant_items_batch_id_leave_grant_batches"),
        ),
        sa.ForeignKeyConstraint(
            ["employment_id"],
            ["employments.id"],
            name=op.f("fk_leave_grant_items_employment_id_employments"),
        ),
        sa.ForeignKeyConstraint(
            ["leave_type_id"],
            ["leave_types.id"],
            name=op.f("fk_leave_grant_items_leave_type_id_leave_types"),
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["leave_grant_rules.id"],
            name=op.f("fk_leave_grant_items_rule_id_leave_grant_rules"),
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["leave_balance_transactions.id"],
            name=op.f("fk_leave_grant_items_transaction_id_leave_balance_transactions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_leave_grant_items")),
        sa.UniqueConstraint(
            "batch_id",
            "employment_id",
            "leave_type_id",
            name=op.f("uq_leave_grant_items_batch_employment_leave_type"),
        ),
        sa.UniqueConstraint(
            "idempotency_key",
            name=op.f("uq_leave_grant_items_idempotency_key"),
        ),
    )
    op.create_index(
        op.f("ix_leave_grant_items_batch_id"),
        "leave_grant_items",
        ["batch_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_leave_grant_items_employment_id"),
        "leave_grant_items",
        ["employment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_leave_grant_items_leave_type_id"),
        "leave_grant_items",
        ["leave_type_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_leave_grant_items_leave_type_id"), table_name="leave_grant_items")
    op.drop_index(op.f("ix_leave_grant_items_employment_id"), table_name="leave_grant_items")
    op.drop_index(op.f("ix_leave_grant_items_batch_id"), table_name="leave_grant_items")
    op.drop_table("leave_grant_items")
    op.drop_index(op.f("ix_leave_grant_batches_voided_by"), table_name="leave_grant_batches")
    op.drop_index(op.f("ix_leave_grant_batches_period_code"), table_name="leave_grant_batches")
    op.drop_index(op.f("ix_leave_grant_batches_issued_by"), table_name="leave_grant_batches")
    op.drop_index(op.f("ix_leave_grant_batches_created_by"), table_name="leave_grant_batches")
    op.drop_table("leave_grant_batches")
    op.drop_index(op.f("ix_leave_grant_rules_leave_type_id"), table_name="leave_grant_rules")
    op.drop_table("leave_grant_rules")
