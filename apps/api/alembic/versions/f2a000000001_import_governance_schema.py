"""add import governance schema

Revision ID: f2a000000001
Revises: f1a000000001
Create Date: 2026-08-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f2a000000001"
down_revision: str | Sequence[str] | None = "f1a000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_batches",
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("source_system", sa.String(length=80), nullable=False),
        sa.Column("source_table", sa.String(length=128), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("request_checksum", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("valid_rows", sa.Integer(), nullable=False),
        sa.Column("rejected_rows", sa.Integer(), nullable=False),
        sa.Column("imported_rows", sa.Integer(), nullable=False),
        sa.Column("skipped_rows", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
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
            ["created_by"],
            ["user_accounts.id"],
            name=op.f("fk_import_batches_created_by_user_accounts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_batches")),
        sa.UniqueConstraint(
            "idempotency_key",
            name=op.f("uq_import_batches_idempotency_key"),
        ),
    )
    op.create_index(
        op.f("ix_import_batches_created_by"),
        "import_batches",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_import_batches_entity_type"),
        "import_batches",
        ["entity_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_import_batches_source_system"),
        "import_batches",
        ["source_system"],
        unique=False,
    )
    op.create_index(
        op.f("ix_import_batches_status"),
        "import_batches",
        ["status"],
        unique=False,
    )

    op.create_table(
        "import_batch_rows",
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("source_record_id", sa.String(length=255), nullable=False),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=True),
        sa.Column("target_id", sa.Uuid(), nullable=True),
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
            ["batch_id"],
            ["import_batches.id"],
            name=op.f("fk_import_batch_rows_batch_id_import_batches"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_batch_rows")),
        sa.UniqueConstraint(
            "batch_id",
            "row_number",
            name="uq_import_batch_rows_batch_row_number",
        ),
        sa.UniqueConstraint(
            "batch_id",
            "source_record_id",
            name="uq_import_batch_rows_batch_source_record",
        ),
    )
    op.create_index(
        op.f("ix_import_batch_rows_batch_id"),
        "import_batch_rows",
        ["batch_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_import_batch_rows_status"),
        "import_batch_rows",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_import_batch_rows_target_id"),
        "import_batch_rows",
        ["target_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_import_batch_rows_target_id"),
        table_name="import_batch_rows",
    )
    op.drop_index(
        op.f("ix_import_batch_rows_status"),
        table_name="import_batch_rows",
    )
    op.drop_index(
        op.f("ix_import_batch_rows_batch_id"),
        table_name="import_batch_rows",
    )
    op.drop_table("import_batch_rows")
    op.drop_index(
        op.f("ix_import_batches_status"),
        table_name="import_batches",
    )
    op.drop_index(
        op.f("ix_import_batches_source_system"),
        table_name="import_batches",
    )
    op.drop_index(
        op.f("ix_import_batches_entity_type"),
        table_name="import_batches",
    )
    op.drop_index(
        op.f("ix_import_batches_created_by"),
        table_name="import_batches",
    )
    op.drop_table("import_batches")
