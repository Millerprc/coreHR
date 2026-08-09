"""seed data governance permissions

Revision ID: f2a000000002
Revises: f2a000000001
Create Date: 2026-08-09
"""

from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "f2a000000002"
down_revision: str | Sequence[str] | None = "f2a000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    specs = {
        "DATA_GOVERNANCE_VIEW": ("查看数据治理", "DATA_GOVERNANCE"),
        "DATA_GOVERNANCE_ADMIN": ("管理数据治理", "DATA_GOVERNANCE"),
    }
    existing = set(
        connection.execute(
            sa.text(
                """
                SELECT code FROM permissions
                WHERE code IN ('DATA_GOVERNANCE_VIEW', 'DATA_GOVERNANCE_ADMIN')
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
        for code, (name, module_code) in specs.items()
        if code not in existing
    ]
    if missing:
        op.bulk_insert(permission_table, missing)


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM permissions AS permission
        WHERE permission.code IN (
            'DATA_GOVERNANCE_VIEW',
            'DATA_GOVERNANCE_ADMIN'
        )
        AND NOT EXISTS (
            SELECT 1 FROM role_permissions
            WHERE role_permissions.permission_id = permission.id
        )
        """
    )
