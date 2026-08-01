"""seed long-running business sequences within PostgreSQL integer bounds

Revision ID: c91a7d225b60
Revises: b6dd0b3d15da
Create Date: 2026-08-01 05:00:00
"""
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "c91a7d225b60"
down_revision: Union[str, None] = "b6dd0b3d15da"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
                "code": code,
                "current_value": 0,
                "width": 10,
                "max_value": 2_000_000_000,
            }
            for code in (
                "WORKFLOW_INSTANCE_NUMBER",
                "HR_EVENT_NUMBER",
                "LEAVE_REQUEST_NUMBER",
            )
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM number_sequences "
            "WHERE code IN ('WORKFLOW_INSTANCE_NUMBER', 'HR_EVENT_NUMBER', 'LEAVE_REQUEST_NUMBER')"
        )
    )
