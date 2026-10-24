# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""batch change plans

Revision ID: f2d000000001
Revises: f2c000000001
Create Date: 2026-10-24
"""

from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "f2d000000001"
down_revision: str | Sequence[str] | None = "f2c000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS hr_event_batches (
                id UUID NOT NULL,
                batch_number VARCHAR(50) NOT NULL,
                title VARCHAR(200) NOT NULL,
                status VARCHAR(30) NOT NULL,
                line_count INTEGER NOT NULL,
                reason TEXT,
                workflow_instance_id UUID,
                submitted_at TIMESTAMP WITH TIME ZONE,
                approved_at TIMESTAMP WITH TIME ZONE,
                created_by UUID NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                CONSTRAINT pk_hr_event_batches PRIMARY KEY (id),
                CONSTRAINT uq_hr_event_batches_batch_number UNIQUE (batch_number),
                CONSTRAINT ck_hr_event_batches_line_count_nonnegative
                    CHECK (line_count >= 0)
            )
            """
        )
    )
    connection.execute(
        sa.text("ALTER TABLE hr_events ADD COLUMN IF NOT EXISTS batch_id UUID")
    )
    connection.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'fk_hr_events_batch_id_hr_event_batches'
                ) THEN
                    ALTER TABLE hr_events
                    ADD CONSTRAINT fk_hr_events_batch_id_hr_event_batches
                    FOREIGN KEY (batch_id) REFERENCES hr_event_batches (id);
                END IF;
            END $$
            """
        )
    )
    connection.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_hr_events_batch_id ON hr_events (batch_id)"
        )
    )
    # Requirement: HR-BATCH-010 — 批量异动方案号使用独立的长流水号序列，
    # 上限与既有长流水号序列一致，取 PostgreSQL 整数边界内的值。
    connection.execute(
        sa.text(
            """
            INSERT INTO number_sequences (id, code, current_value, width, max_value)
            SELECT :id, 'HR_EVENT_BATCH_NUMBER', 0, 10, 2000000000
            WHERE NOT EXISTS (
                SELECT 1 FROM number_sequences WHERE code = 'HR_EVENT_BATCH_NUMBER'
            )
            """
        ),
        {"id": uuid4()},
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text("DROP INDEX IF EXISTS ix_hr_events_batch_id"))
    connection.execute(
        sa.text(
            """
            ALTER TABLE hr_events
            DROP CONSTRAINT IF EXISTS fk_hr_events_batch_id_hr_event_batches
            """
        )
    )
    connection.execute(sa.text("ALTER TABLE hr_events DROP COLUMN IF EXISTS batch_id"))
    connection.execute(sa.text("DROP TABLE IF EXISTS hr_event_batches"))
    connection.execute(
        sa.text(
            "DELETE FROM number_sequences WHERE code = 'HR_EVENT_BATCH_NUMBER'"
        )
    )
