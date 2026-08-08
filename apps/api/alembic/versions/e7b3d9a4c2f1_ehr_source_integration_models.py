"""add normalized EHR source integration models

Revision ID: e7b3d9a4c2f1
Revises: c91a7d225b60
Create Date: 2026-08-08 12:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7b3d9a4c2f1"
down_revision: Union[str, None] = "c91a7d225b60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "data_dictionaries",
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("english_name", sa.String(length=200), nullable=True),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_dictionaries")),
        sa.UniqueConstraint("code", name=op.f("uq_data_dictionaries_code")),
    )

    op.create_table(
        "data_dictionary_items",
        sa.Column("dictionary_id", sa.Uuid(), nullable=False),
        sa.Column("parent_item_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("english_name", sa.String(length=200), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
            ["dictionary_id"],
            ["data_dictionaries.id"],
            name=op.f("fk_data_dictionary_items_dictionary_id_data_dictionaries"),
        ),
        sa.ForeignKeyConstraint(
            ["parent_item_id"],
            ["data_dictionary_items.id"],
            name=op.f("fk_data_dictionary_items_parent_item_id_data_dictionary_items"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_dictionary_items")),
        sa.UniqueConstraint(
            "dictionary_id",
            "code",
            name=op.f("uq_data_dictionary_items_dictionary_id"),
        ),
    )
    op.create_index(
        op.f("ix_data_dictionary_items_dictionary_id"),
        "data_dictionary_items",
        ["dictionary_id"],
        unique=False,
    )

    op.create_table(
        "external_record_links",
        sa.Column("source_system", sa.String(length=80), nullable=False),
        sa.Column("source_table", sa.String(length=128), nullable=False),
        sa.Column("source_record_id", sa.String(length=255), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_checksum", sa.String(length=64), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_external_record_links")),
        sa.UniqueConstraint(
            "source_system",
            "source_table",
            "source_record_id",
            "target_type",
            name=op.f("uq_external_record_links_source_system"),
        ),
    )
    op.create_index(
        op.f("ix_external_record_links_target_id"),
        "external_record_links",
        ["target_id"],
        unique=False,
    )

    op.create_table(
        "person_labels",
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("label_name", sa.String(length=255), nullable=False),
        sa.Column("label_type", sa.String(length=100), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("is_ai_generated", sa.Boolean(), nullable=False),
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
            "effective_to IS NULL OR effective_to >= effective_from",
            name=op.f("ck_person_labels_effective_period_order"),
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["persons.id"],
            name=op.f("fk_person_labels_person_id_persons"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_person_labels")),
        sa.UniqueConstraint(
            "person_id",
            "label_type",
            "label_name",
            "effective_from",
            "source",
            name=op.f("uq_person_labels_person_id"),
        ),
    )
    op.create_index(
        op.f("ix_person_labels_person_id"),
        "person_labels",
        ["person_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_person_labels_person_id"), table_name="person_labels")
    op.drop_table("person_labels")
    op.drop_index(op.f("ix_external_record_links_target_id"), table_name="external_record_links")
    op.drop_table("external_record_links")
    op.drop_index(
        op.f("ix_data_dictionary_items_dictionary_id"),
        table_name="data_dictionary_items",
    )
    op.drop_table("data_dictionary_items")
    op.drop_table("data_dictionaries")
