"""add personnel record foundation and effective-dated legal entities

Revision ID: f1c000000001
Revises: f1b000000001
Create Date: 2026-08-12
"""

from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "f1c000000001"
down_revision: str | Sequence[str] | None = "f1b000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("persons", sa.Column("legal_name", sa.String(length=200), nullable=True))
    op.add_column("persons", sa.Column("ethnicity_code", sa.String(length=50), nullable=True))
    op.add_column("persons", sa.Column("marital_status_code", sa.String(length=50), nullable=True))
    op.add_column("persons", sa.Column("political_status_code", sa.String(length=50), nullable=True))
    op.execute("UPDATE persons SET legal_name = display_name WHERE legal_name IS NULL")
    op.alter_column("persons", "legal_name", nullable=False)
    op.create_index(op.f("ix_persons_legal_name"), "persons", ["legal_name"], unique=False)

    op.create_table(
        "employment_legal_entity_relations",
        sa.Column("employment_id", sa.Uuid(), nullable=False),
        sa.Column("relation_kind", sa.String(length=30), nullable=False),
        sa.Column("legal_entity_id", sa.Uuid(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("source_event_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("change_reason", sa.String(length=500), nullable=False),
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
            "relation_kind IN ('contract', 'payroll', 'social_insurance', 'tax')",
            name=op.f("ck_employment_legal_entity_relations_supported_relation_kind"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_employment_legal_entity_relations_version_positive"),
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name=op.f("ck_employment_legal_entity_relations_effective_period_order"),
        ),
        sa.ForeignKeyConstraint(
            ["employment_id"],
            ["employments.id"],
            name=op.f("fk_employment_legal_entity_relations_employment_id_employments"),
        ),
        sa.ForeignKeyConstraint(
            ["legal_entity_id"],
            ["legal_entities.id"],
            name=op.f("fk_employment_legal_entity_relations_legal_entity_id_legal_entities"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_employment_legal_entity_relations")),
        sa.UniqueConstraint(
            "employment_id",
            "relation_kind",
            "effective_from",
            name="uq_employment_legal_entity_relations_employment_kind_effective",
        ),
        sa.UniqueConstraint(
            "employment_id",
            "relation_kind",
            "version",
            name="uq_employment_legal_entity_relations_employment_kind_version",
        ),
    )
    for column in ("employment_id", "relation_kind", "legal_entity_id"):
        op.create_index(
            op.f(f"ix_employment_legal_entity_relations_{column}"),
            "employment_legal_entity_relations",
            [column],
            unique=False,
        )

    connection = op.get_bind()
    employments = list(
        connection.execute(
            sa.text(
                """
                SELECT id, planned_start_date, contract_legal_entity_id,
                       payroll_legal_entity_id, social_insurance_legal_entity_id,
                       tax_legal_entity_id
                FROM employments
                """
            )
        ).mappings()
    )
    field_kinds = {
        "contract_legal_entity_id": "contract",
        "payroll_legal_entity_id": "payroll",
        "social_insurance_legal_entity_id": "social_insurance",
        "tax_legal_entity_id": "tax",
    }
    rows = [
        {
            "id": uuid4(),
            "employment_id": employment["id"],
            "relation_kind": relation_kind,
            "legal_entity_id": employment[field],
            "effective_from": employment["planned_start_date"],
            "version": 1,
            "change_reason": "Backfill effective-dated legal entity baseline",
        }
        for employment in employments
        for field, relation_kind in field_kinds.items()
        if employment[field] is not None
    ]
    if rows:
        relation_table = sa.table(
            "employment_legal_entity_relations",
            sa.column("id", sa.Uuid()),
            sa.column("employment_id", sa.Uuid()),
            sa.column("relation_kind", sa.String()),
            sa.column("legal_entity_id", sa.Uuid()),
            sa.column("effective_from", sa.Date()),
            sa.column("version", sa.Integer()),
            sa.column("change_reason", sa.String()),
        )
        op.bulk_insert(relation_table, rows)

    permission_specs = {
        "PERSON_VIEW": "View personnel records",
        "PERSON_EDIT_BASIC": "Edit basic personnel records",
        "PERSON_SENSITIVE_VIEW": "View masked sensitive personnel fields",
        "PERSON_SENSITIVE_REVEAL": "Reveal sensitive personnel fields",
        "PERSON_IMPORT": "Import personnel records",
        "PERSON_EXPORT": "Export personnel records",
    }
    existing = set(
        connection.execute(
            sa.text("SELECT code FROM permissions WHERE code LIKE 'PERSON_%'")
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
        {"id": uuid4(), "code": code, "name": name, "module_code": "PERSONNEL"}
        for code, name in permission_specs.items()
        if code not in existing
    ]
    if missing:
        op.bulk_insert(permission_table, missing)

    connection.execute(
        sa.text(
            """
            INSERT INTO role_permissions (id, role_id, permission_id)
            SELECT gen_random_uuid(), workforce_roles.role_id, person_permissions.id
            FROM (
                SELECT DISTINCT role_permissions.role_id
                FROM role_permissions
                JOIN permissions ON permissions.id = role_permissions.permission_id
                WHERE permissions.code = 'WORKFORCE_ADMIN'
            ) AS workforce_roles
            CROSS JOIN permissions AS person_permissions
            WHERE person_permissions.code IN (
                'PERSON_VIEW', 'PERSON_EDIT_BASIC', 'PERSON_SENSITIVE_VIEW',
                'PERSON_IMPORT', 'PERSON_EXPORT'
            )
            ON CONFLICT (role_id, permission_id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_table("employment_legal_entity_relations")
    op.drop_index(op.f("ix_persons_legal_name"), table_name="persons")
    op.drop_column("persons", "political_status_code")
    op.drop_column("persons", "marital_status_code")
    op.drop_column("persons", "ethnicity_code")
    op.drop_column("persons", "legal_name")
    op.execute(
        """
        DELETE FROM permissions AS permission
        WHERE permission.code IN (
            'PERSON_VIEW', 'PERSON_EDIT_BASIC', 'PERSON_SENSITIVE_VIEW',
            'PERSON_SENSITIVE_REVEAL', 'PERSON_IMPORT', 'PERSON_EXPORT'
        )
        AND NOT EXISTS (
            SELECT 1 FROM role_permissions
            WHERE role_permissions.permission_id = permission.id
        )
        """
    )
