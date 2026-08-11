"""add effective-dated job architecture

Revision ID: f1b000000001
Revises: f3a000000004
Create Date: 2026-08-12
"""

from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "f1b000000001"
down_revision: str | Sequence[str] | None = "f3a000000004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_dimensions",
        sa.Column("dimension_type", sa.String(length=20), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_dimensions")),
        sa.UniqueConstraint(
            "dimension_type",
            "code",
            name=op.f("uq_job_dimensions_dimension_type"),
        ),
    )
    op.create_index(
        op.f("ix_job_dimensions_dimension_type"),
        "job_dimensions",
        ["dimension_type"],
        unique=False,
    )
    op.create_table(
        "job_dimension_versions",
        sa.Column("dimension_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("parent_dimension_id", sa.Uuid(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=True),
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
        sa.CheckConstraint("version > 0", name=op.f("ck_job_dimension_versions_version_positive")),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name=op.f("ck_job_dimension_versions_effective_period_order"),
        ),
        sa.ForeignKeyConstraint(
            ["dimension_id"],
            ["job_dimensions.id"],
            name=op.f("fk_job_dimension_versions_dimension_id_job_dimensions"),
        ),
        sa.ForeignKeyConstraint(
            ["parent_dimension_id"],
            ["job_dimensions.id"],
            name=op.f("fk_job_dimension_versions_parent_dimension_id_job_dimensions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_dimension_versions")),
        sa.UniqueConstraint(
            "dimension_id",
            "version",
            name=op.f("uq_job_dimension_versions_dimension_id"),
        ),
    )
    op.create_index(
        op.f("ix_job_dimension_versions_dimension_id"),
        "job_dimension_versions",
        ["dimension_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_job_dimension_versions_parent_dimension_id"),
        "job_dimension_versions",
        ["parent_dimension_id"],
        unique=False,
    )
    op.create_table(
        "job_catalog_versions",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("level_dimension_id", sa.Uuid(), nullable=True),
        sa.Column("grade_dimension_id", sa.Uuid(), nullable=True),
        sa.Column("class_dimension_id", sa.Uuid(), nullable=True),
        sa.Column("sequence_dimension_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("source_job_id", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("attributes", sa.JSON(), nullable=False),
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
        sa.CheckConstraint("version > 0", name=op.f("ck_job_catalog_versions_version_positive")),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name=op.f("ck_job_catalog_versions_effective_period_order"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["job_catalog.id"],
            name=op.f("fk_job_catalog_versions_job_id_job_catalog"),
        ),
        sa.ForeignKeyConstraint(
            ["level_dimension_id"],
            ["job_dimensions.id"],
            name=op.f("fk_job_catalog_versions_level_dimension_id_job_dimensions"),
        ),
        sa.ForeignKeyConstraint(
            ["grade_dimension_id"],
            ["job_dimensions.id"],
            name=op.f("fk_job_catalog_versions_grade_dimension_id_job_dimensions"),
        ),
        sa.ForeignKeyConstraint(
            ["class_dimension_id"],
            ["job_dimensions.id"],
            name=op.f("fk_job_catalog_versions_class_dimension_id_job_dimensions"),
        ),
        sa.ForeignKeyConstraint(
            ["sequence_dimension_id"],
            ["job_dimensions.id"],
            name=op.f("fk_job_catalog_versions_sequence_dimension_id_job_dimensions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_catalog_versions")),
        sa.UniqueConstraint(
            "job_id",
            "version",
            name=op.f("uq_job_catalog_versions_job_id"),
        ),
    )
    for column in (
        "job_id",
        "level_dimension_id",
        "grade_dimension_id",
        "class_dimension_id",
        "sequence_dimension_id",
    ):
        op.create_index(
            op.f(f"ix_job_catalog_versions_{column}"),
            "job_catalog_versions",
            [column],
            unique=False,
        )

    connection = op.get_bind()
    jobs = list(
        connection.execute(
            sa.text(
                """
                SELECT id, name, level_code, grade_code, class_code, sequence_code,
                       status, effective_from, effective_to, attributes
                FROM job_catalog
                """
            )
        ).mappings()
    )
    dimension_ids: dict[tuple[str, str], object] = {}
    earliest_dates: dict[tuple[str, str], object] = {}
    field_types = {
        "level_code": "LEVEL",
        "grade_code": "GRADE",
        "class_code": "CLASS",
        "sequence_code": "SEQUENCE",
    }
    for job in jobs:
        for field, dimension_type in field_types.items():
            code = job[field]
            if not code:
                continue
            key = (dimension_type, str(code))
            dimension_ids.setdefault(key, uuid4())
            current_date = earliest_dates.get(key)
            if current_date is None or job["effective_from"] < current_date:
                earliest_dates[key] = job["effective_from"]

    if dimension_ids:
        connection.execute(
            sa.text(
                """
                INSERT INTO job_dimensions (id, dimension_type, code)
                VALUES (:id, :dimension_type, :code)
                """
            ),
            [
                {"id": dimension_id, "dimension_type": key[0], "code": key[1]}
                for key, dimension_id in dimension_ids.items()
            ],
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO job_dimension_versions
                    (id, dimension_id, version, name, parent_dimension_id, sort_order,
                     status, effective_from, effective_to, is_current, notes, change_reason)
                VALUES
                    (:id, :dimension_id, 1, :name, NULL, 0,
                     'active', :effective_from, NULL, true, :notes, :change_reason)
                """
            ),
            [
                {
                    "id": uuid4(),
                    "dimension_id": dimension_id,
                    "name": key[1],
                    "effective_from": earliest_dates[key],
                    "notes": "由旧职务投影迁移，正式名称待企业码表确认",
                    "change_reason": "升级到生效日期职务体系",
                }
                for key, dimension_id in dimension_ids.items()
            ],
        )

    if jobs:
        insert_job_versions = sa.text(
            """
            INSERT INTO job_catalog_versions
                (id, job_id, version, name, level_dimension_id, grade_dimension_id,
                 class_dimension_id, sequence_dimension_id, status, effective_from,
                 effective_to, is_current, source_job_id, notes, attributes, change_reason)
            VALUES
                (:id, :job_id, 1, :name, :level_dimension_id, :grade_dimension_id,
                 :class_dimension_id, :sequence_dimension_id, :status, :effective_from,
                 :effective_to, true, NULL, :notes, :attributes, :change_reason)
            """
        ).bindparams(sa.bindparam("attributes", type_=sa.JSON()))
        connection.execute(
            insert_job_versions,
            [
                {
                    "id": uuid4(),
                    "job_id": job["id"],
                    "name": job["name"],
                    "level_dimension_id": dimension_ids.get(("LEVEL", str(job["level_code"]))) if job["level_code"] else None,
                    "grade_dimension_id": dimension_ids.get(("GRADE", str(job["grade_code"]))) if job["grade_code"] else None,
                    "class_dimension_id": dimension_ids.get(("CLASS", str(job["class_code"]))) if job["class_code"] else None,
                    "sequence_dimension_id": dimension_ids.get(("SEQUENCE", str(job["sequence_code"]))) if job["sequence_code"] else None,
                    "status": job["status"],
                    "effective_from": job["effective_from"],
                    "effective_to": job["effective_to"],
                    "notes": "由旧 job_catalog 当前投影迁移",
                    "attributes": job["attributes"] or {},
                    "change_reason": "升级到生效日期职务体系",
                }
                for job in jobs
            ],
        )


def downgrade() -> None:
    for column in (
        "sequence_dimension_id",
        "class_dimension_id",
        "grade_dimension_id",
        "level_dimension_id",
        "job_id",
    ):
        op.drop_index(
            op.f(f"ix_job_catalog_versions_{column}"),
            table_name="job_catalog_versions",
        )
    op.drop_table("job_catalog_versions")
    op.drop_index(
        op.f("ix_job_dimension_versions_parent_dimension_id"),
        table_name="job_dimension_versions",
    )
    op.drop_index(
        op.f("ix_job_dimension_versions_dimension_id"),
        table_name="job_dimension_versions",
    )
    op.drop_table("job_dimension_versions")
    op.drop_index(
        op.f("ix_job_dimensions_dimension_type"),
        table_name="job_dimensions",
    )
    op.drop_table("job_dimensions")
