"""phase 1A effective-dated organization domain

Revision ID: f1a000000001
Revises: e7b3d9a4c2f1
Create Date: 2026-08-08 18:00:00
"""

from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "f1a000000001"
down_revision: Union[str, None] = "e7b3d9a4c2f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamp_columns() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "organization_events",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("expected_version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("change_reason", sa.String(length=500), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "expected_version >= 1",
            name=op.f("ck_organization_events_expected_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_organization_events_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organization_events")),
        sa.UniqueConstraint(
            "idempotency_key",
            name=op.f("uq_organization_events_idempotency_key"),
        ),
    )
    op.create_index(
        op.f("ix_organization_events_organization_id"),
        "organization_events",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_organization_events_effective_date"),
        "organization_events",
        ["effective_date"],
        unique=False,
    )

    op.create_table(
        "organization_leaders",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name=op.f("ck_organization_leaders_effective_period_order"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_organization_leaders_organization_id_organizations"),
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["persons.id"],
            name=op.f("fk_organization_leaders_person_id_persons"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organization_leaders")),
        sa.UniqueConstraint(
            "organization_id",
            "person_id",
            "effective_from",
            "version",
            name=op.f("uq_organization_leaders_organization_id"),
        ),
    )
    op.create_index(
        op.f("ix_organization_leaders_organization_id"),
        "organization_leaders",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_organization_leaders_person_id"),
        "organization_leaders",
        ["person_id"],
        unique=False,
    )

    op.create_table(
        "person_bp_memberships",
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("bp_type", sa.String(length=10), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "bp_type IN ('HRBP', 'EBP', 'TBP', 'FBP')",
            name=op.f("ck_person_bp_memberships_bp_type_allowed"),
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name=op.f("ck_person_bp_memberships_effective_period_order"),
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["persons.id"],
            name=op.f("fk_person_bp_memberships_person_id_persons"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_person_bp_memberships")),
        sa.UniqueConstraint(
            "person_id",
            "effective_from",
            "version",
            name=op.f("uq_person_bp_memberships_person_id"),
        ),
    )
    op.create_index(
        op.f("ix_person_bp_memberships_person_id"),
        "person_bp_memberships",
        ["person_id"],
        unique=False,
    )

    op.create_table(
        "bp_service_scopes",
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name=op.f("ck_bp_service_scopes_effective_period_order"),
        ),
        sa.ForeignKeyConstraint(
            ["membership_id"],
            ["person_bp_memberships.id"],
            name=op.f("fk_bp_service_scopes_membership_id_person_bp_memberships"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_bp_service_scopes_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bp_service_scopes")),
        sa.UniqueConstraint(
            "membership_id",
            "organization_id",
            "effective_from",
            name=op.f("uq_bp_service_scopes_membership_id"),
        ),
    )
    op.create_index(
        op.f("ix_bp_service_scopes_membership_id"),
        "bp_service_scopes",
        ["membership_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bp_service_scopes_organization_id"),
        "bp_service_scopes",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "revenue_target_months",
        sa.Column("revenue_target_id", sa.Uuid(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "month BETWEEN 1 AND 12",
            name=op.f("ck_revenue_target_months_month_range"),
        ),
        sa.CheckConstraint(
            "amount >= 0",
            name=op.f("ck_revenue_target_months_amount_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["revenue_target_id"],
            ["revenue_targets.id"],
            name=op.f("fk_revenue_target_months_revenue_target_id_revenue_targets"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_revenue_target_months")),
        sa.UniqueConstraint(
            "revenue_target_id",
            "month",
            name=op.f("uq_revenue_target_months_revenue_target_id"),
        ),
    )
    op.create_index(
        op.f("ix_revenue_target_months_revenue_target_id"),
        "revenue_target_months",
        ["revenue_target_id"],
        unique=False,
    )

    op.create_table(
        "outbox_events",
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_type", sa.String(length=80), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox_events")),
    )
    for column in ("event_type", "aggregate_type", "aggregate_id", "occurred_at"):
        op.create_index(
            op.f(f"ix_outbox_events_{column}"),
            "outbox_events",
            [column],
            unique=False,
        )

    op.add_column(
        "organization_legal_entities",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "organization_legal_entities",
        sa.Column("is_current", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.alter_column("organization_legal_entities", "version", server_default=None)
    op.alter_column("organization_legal_entities", "is_current", server_default=None)

    op.add_column("cost_centers", sa.Column("effective_from", sa.Date(), nullable=True))
    op.add_column("cost_centers", sa.Column("effective_to", sa.Date(), nullable=True))
    op.add_column(
        "cost_centers",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.execute(
        "UPDATE cost_centers SET effective_from = COALESCE(created_at::date, CURRENT_DATE) "
        "WHERE effective_from IS NULL"
    )
    op.alter_column("cost_centers", "effective_from", nullable=False)
    op.alter_column("cost_centers", "version", server_default=None)
    op.create_check_constraint(
        op.f("ck_cost_centers_effective_period_order"),
        "cost_centers",
        "effective_to IS NULL OR effective_to >= effective_from",
    )

    op.execute(
        """
        INSERT INTO revenue_target_months
            (id, revenue_target_id, month, amount, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            target.id,
            month_value.month::integer,
            month_value.amount::numeric(20, 4),
            now(),
            now()
        FROM revenue_targets AS target
        CROSS JOIN LATERAL jsonb_array_elements_text(
            target.monthly_amounts::jsonb
        ) WITH ORDINALITY AS month_value(amount, month)
        """
    )
    op.drop_column("revenue_targets", "monthly_amounts")

    _create_exclusion_constraints()
    _seed_phase_1a_permissions_and_sequence()


def _create_exclusion_constraints() -> None:
    statements = (
        """
        ALTER TABLE organization_versions
        ADD CONSTRAINT ex_organization_versions_effective_period
        EXCLUDE USING gist (
            organization_id WITH =,
            daterange(effective_from, COALESCE(effective_to + 1, 'infinity'::date), '[)') WITH &&
        )
        """,
        """
        ALTER TABLE organization_leaders
        ADD CONSTRAINT ex_organization_leaders_person_period
        EXCLUDE USING gist (
            organization_id WITH =,
            person_id WITH =,
            daterange(effective_from, COALESCE(effective_to + 1, 'infinity'::date), '[)') WITH &&
        )
        """,
        """
        ALTER TABLE person_bp_memberships
        ADD CONSTRAINT ex_person_bp_memberships_person_period
        EXCLUDE USING gist (
            person_id WITH =,
            daterange(effective_from, COALESCE(effective_to + 1, 'infinity'::date), '[)') WITH &&
        )
        """,
        """
        ALTER TABLE bp_service_scopes
        ADD CONSTRAINT ex_bp_service_scopes_membership_org_period
        EXCLUDE USING gist (
            membership_id WITH =,
            organization_id WITH =,
            daterange(effective_from, COALESCE(effective_to + 1, 'infinity'::date), '[)') WITH &&
        )
        """,
        """
        ALTER TABLE organization_legal_entities
        ADD CONSTRAINT ex_organization_legal_entities_period
        EXCLUDE USING gist (
            organization_id WITH =,
            legal_entity_id WITH =,
            daterange(effective_from, COALESCE(effective_to + 1, 'infinity'::date), '[)') WITH &&
        )
        """,
        """
        ALTER TABLE organization_cost_allocations
        ADD CONSTRAINT ex_organization_cost_allocations_period
        EXCLUDE USING gist (
            organization_id WITH =,
            cost_center_id WITH =,
            daterange(effective_from, COALESCE(effective_to + 1, 'infinity'::date), '[)') WITH &&
        )
        """,
    )
    for statement in statements:
        op.execute(statement)


def _seed_phase_1a_permissions_and_sequence() -> None:
    connection = op.get_bind()
    existing_sequences = set(
        connection.execute(
            sa.text("SELECT code FROM number_sequences WHERE code = 'ORG_NUMBER'")
        ).scalars()
    )
    if "ORG_NUMBER" not in existing_sequences:
        sequence_table = sa.table(
            "number_sequences",
            sa.column("id", sa.Uuid()),
            sa.column("code", sa.String()),
            sa.column("current_value", sa.Integer()),
            sa.column("width", sa.Integer()),
            sa.column("max_value", sa.Integer()),
        )
        op.bulk_insert(
            sequence_table,
            [
                {
                    "id": uuid4(),
                    "code": "ORG_NUMBER",
                    "current_value": 0,
                    "width": 6,
                    "max_value": 999_999,
                }
            ],
        )

    permission_specs = {
        "CONFIGURATION_VIEW": ("查看配置", "CONFIGURATION"),
        "CONFIGURATION_ADMIN": ("管理配置", "CONFIGURATION"),
        "ORGANIZATION_VIEW": ("查看组织", "ORGANIZATION"),
        "ORGANIZATION_ADMIN": ("管理组织", "ORGANIZATION"),
        "ORGANIZATION_EVENT_APPLY": ("执行组织生效事件", "ORGANIZATION"),
    }
    existing_permissions = set(
        connection.execute(
            sa.text(
                """
                SELECT code FROM permissions
                WHERE code IN (
                    'CONFIGURATION_VIEW',
                    'CONFIGURATION_ADMIN',
                    'ORGANIZATION_VIEW',
                    'ORGANIZATION_ADMIN',
                    'ORGANIZATION_EVENT_APPLY'
                )
                """
            )
        ).scalars()
    )
    permission_table = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("module_code", sa.String()),
    )
    missing = [
        {
            "id": uuid4(),
            "code": code,
            "name": name,
            "module_code": module_code,
        }
        for code, (name, module_code) in permission_specs.items()
        if code not in existing_permissions
    ]
    if missing:
        op.bulk_insert(permission_table, missing)


def downgrade() -> None:
    op.add_column("revenue_targets", sa.Column("monthly_amounts", sa.JSON(), nullable=True))
    op.execute(
        """
        UPDATE revenue_targets AS target
        SET monthly_amounts = months.values
        FROM (
            SELECT
                revenue_target_id,
                json_agg(amount::text ORDER BY month) AS values
            FROM revenue_target_months
            GROUP BY revenue_target_id
        ) AS months
        WHERE target.id = months.revenue_target_id
        """
    )
    op.execute(
        "UPDATE revenue_targets SET monthly_amounts = '[]'::json "
        "WHERE monthly_amounts IS NULL"
    )
    op.alter_column("revenue_targets", "monthly_amounts", nullable=False)

    for table_name, constraint_name in (
        ("organization_cost_allocations", "ex_organization_cost_allocations_period"),
        ("organization_legal_entities", "ex_organization_legal_entities_period"),
        ("bp_service_scopes", "ex_bp_service_scopes_membership_org_period"),
        ("person_bp_memberships", "ex_person_bp_memberships_person_period"),
        ("organization_leaders", "ex_organization_leaders_person_period"),
        ("organization_versions", "ex_organization_versions_effective_period"),
    ):
        op.execute(
            f'ALTER TABLE "{table_name}" DROP CONSTRAINT "{constraint_name}"'
        )

    op.execute(
        "DELETE FROM number_sequences WHERE code = 'ORG_NUMBER'"
    )
    op.execute(
        """
        DELETE FROM permissions AS permission
        WHERE permission.code IN (
            'CONFIGURATION_VIEW',
            'CONFIGURATION_ADMIN',
            'ORGANIZATION_VIEW',
            'ORGANIZATION_ADMIN',
            'ORGANIZATION_EVENT_APPLY'
        )
        AND NOT EXISTS (
            SELECT 1 FROM role_permissions
            WHERE role_permissions.permission_id = permission.id
        )
        """
    )

    op.drop_constraint(
        op.f("ck_cost_centers_effective_period_order"),
        "cost_centers",
        type_="check",
    )
    op.drop_column("cost_centers", "version")
    op.drop_column("cost_centers", "effective_to")
    op.drop_column("cost_centers", "effective_from")
    op.drop_column("organization_legal_entities", "is_current")
    op.drop_column("organization_legal_entities", "version")

    for column in ("occurred_at", "aggregate_id", "aggregate_type", "event_type"):
        op.drop_index(op.f(f"ix_outbox_events_{column}"), table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_index(
        op.f("ix_revenue_target_months_revenue_target_id"),
        table_name="revenue_target_months",
    )
    op.drop_table("revenue_target_months")
    op.drop_index(
        op.f("ix_bp_service_scopes_organization_id"),
        table_name="bp_service_scopes",
    )
    op.drop_index(
        op.f("ix_bp_service_scopes_membership_id"),
        table_name="bp_service_scopes",
    )
    op.drop_table("bp_service_scopes")
    op.drop_index(
        op.f("ix_person_bp_memberships_person_id"),
        table_name="person_bp_memberships",
    )
    op.drop_table("person_bp_memberships")
    op.drop_index(
        op.f("ix_organization_leaders_person_id"),
        table_name="organization_leaders",
    )
    op.drop_index(
        op.f("ix_organization_leaders_organization_id"),
        table_name="organization_leaders",
    )
    op.drop_table("organization_leaders")
    op.drop_index(
        op.f("ix_organization_events_effective_date"),
        table_name="organization_events",
    )
    op.drop_index(
        op.f("ix_organization_events_organization_id"),
        table_name="organization_events",
    )
    op.drop_table("organization_events")
