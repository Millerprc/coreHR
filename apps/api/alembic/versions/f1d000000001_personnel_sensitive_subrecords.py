"""add encrypted personnel sensitive subrecords

Revision ID: f1d000000001
Revises: f1c000000001
Create Date: 2026-08-12
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f1d000000001"
down_revision: str | Sequence[str] | None = "f1c000000001"
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


def upgrade() -> None:
    op.create_table(
        "person_documents",
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("document_type_code", sa.String(length=50), nullable=False),
        sa.Column("issuing_country_code", sa.String(length=3), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("verification_status", sa.String(length=30), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("document_number_key_version", sa.String(length=50), nullable=False),
        sa.Column("document_number_nonce", sa.LargeBinary(), nullable=False),
        sa.Column("document_number_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("masked_document_number", sa.String(length=255), nullable=False),
        sa.Column("document_number_digest", sa.String(length=64), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "expiry_date IS NULL OR issue_date IS NULL OR expiry_date >= issue_date",
            name=op.f("ck_person_documents_document_date_order"),
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name=op.f("ck_person_documents_effective_period_order"),
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["persons.id"],
            name=op.f("fk_person_documents_person_id_persons"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_person_documents")),
        sa.UniqueConstraint(
            "person_id",
            "document_type_code",
            "issuing_country_code",
            "document_number_digest",
            name="uq_person_documents_identity_digest",
        ),
    )
    op.create_index(op.f("ix_person_documents_person_id"), "person_documents", ["person_id"])
    op.create_index(
        op.f("ix_person_documents_document_number_digest"),
        "person_documents",
        ["document_number_digest"],
    )

    op.create_table(
        "person_contacts",
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("contact_type", sa.String(length=30), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("contact_value_key_version", sa.String(length=50), nullable=False),
        sa.Column("contact_value_nonce", sa.LargeBinary(), nullable=False),
        sa.Column("contact_value_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("masked_contact_value", sa.String(length=320), nullable=False),
        sa.Column("contact_value_digest", sa.String(length=64), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name=op.f("ck_person_contacts_effective_period_order"),
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["persons.id"],
            name=op.f("fk_person_contacts_person_id_persons"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_person_contacts")),
        sa.UniqueConstraint(
            "person_id",
            "contact_type",
            "contact_value_digest",
            "effective_from",
            name="uq_person_contacts_value_effective",
        ),
    )
    op.create_index(op.f("ix_person_contacts_person_id"), "person_contacts", ["person_id"])
    op.create_index(
        op.f("ix_person_contacts_contact_value_digest"),
        "person_contacts",
        ["contact_value_digest"],
    )

    op.create_table(
        "person_addresses",
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("address_type", sa.String(length=30), nullable=False),
        sa.Column("country_code", sa.String(length=3), nullable=False),
        sa.Column("region_code", sa.String(length=50), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("address_detail_key_version", sa.String(length=50), nullable=False),
        sa.Column("address_detail_nonce", sa.LargeBinary(), nullable=False),
        sa.Column("address_detail_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("masked_address_detail", sa.String(length=500), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name=op.f("ck_person_addresses_effective_period_order"),
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["persons.id"],
            name=op.f("fk_person_addresses_person_id_persons"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_person_addresses")),
    )
    op.create_index(op.f("ix_person_addresses_person_id"), "person_addresses", ["person_id"])

    op.create_table(
        "emergency_contacts",
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("relationship_code", sa.String(length=50), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("name_key_version", sa.String(length=50), nullable=False),
        sa.Column("name_nonce", sa.LargeBinary(), nullable=False),
        sa.Column("name_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("masked_name", sa.String(length=200), nullable=False),
        sa.Column("phone_key_version", sa.String(length=50), nullable=False),
        sa.Column("phone_nonce", sa.LargeBinary(), nullable=False),
        sa.Column("phone_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("masked_phone", sa.String(length=50), nullable=False),
        sa.Column("phone_digest", sa.String(length=64), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name=op.f("ck_emergency_contacts_effective_period_order"),
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["persons.id"],
            name=op.f("fk_emergency_contacts_person_id_persons"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_emergency_contacts")),
    )
    op.create_index(op.f("ix_emergency_contacts_person_id"), "emergency_contacts", ["person_id"])
    op.create_index(op.f("ix_emergency_contacts_phone_digest"), "emergency_contacts", ["phone_digest"])


def downgrade() -> None:
    op.drop_table("emergency_contacts")
    op.drop_table("person_addresses")
    op.drop_table("person_contacts")
    op.drop_table("person_documents")
