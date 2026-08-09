from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from hris.shared.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class ImportBatch(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_batches"

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_system: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_table: Mapped[str] = mapped_column(String(128), nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(255))
    idempotency_key: Mapped[UUID] = mapped_column(Uuid, nullable=False, unique=True)
    request_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("user_accounts.id"),
        nullable=False,
        index=True,
    )
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ImportBatchRow(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_batch_rows"
    __table_args__ = (
        UniqueConstraint(
            "batch_id",
            "row_number",
            name="uq_import_batch_rows_batch_row_number",
        ),
        UniqueConstraint(
            "batch_id",
            "source_record_id",
            name="uq_import_batch_rows_batch_source_record",
        ),
    )

    batch_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("import_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    target_type: Mapped[str | None] = mapped_column(String(80))
    target_id: Mapped[UUID | None] = mapped_column(Uuid, index=True)
