"""seed onboarding initiator permission and SSC role

Revision ID: f2b000000001
Revises: f1e000000001
Create Date: 2026-08-12
"""

from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "f2b000000001"
down_revision: str | Sequence[str] | None = "f1e000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    permission_id = connection.execute(
        sa.text("SELECT id FROM permissions WHERE code = 'ONBOARDING_INITIATE'")
    ).scalar_one_or_none()
    if permission_id is None:
        permission_id = uuid4()
        connection.execute(
            sa.text(
                """
                INSERT INTO permissions (id, code, name, module_code)
                VALUES (:id, 'ONBOARDING_INITIATE', '发起入职流程', 'LIFECYCLE')
                """
            ),
            {"id": permission_id},
        )

    role_id = connection.execute(
        sa.text("SELECT id FROM roles WHERE code = 'SSC_ADMIN'")
    ).scalar_one_or_none()
    if role_id is None:
        role_id = uuid4()
        connection.execute(
            sa.text(
                """
                INSERT INTO roles (
                    id, code, name, description, is_system, is_active
                )
                VALUES (
                    :id,
                    'SSC_ADMIN',
                    'SSC管理员',
                    '共享服务中心业务管理角色',
                    true,
                    true
                )
                """
            ),
            {"id": role_id},
        )

    connection.execute(
        sa.text(
            """
            INSERT INTO role_permissions (id, role_id, permission_id)
            SELECT :id, :role_id, :permission_id
            WHERE NOT EXISTS (
                SELECT 1
                FROM role_permissions
                WHERE role_id = :role_id AND permission_id = :permission_id
            )
            """
        ),
        {
            "id": uuid4(),
            "role_id": role_id,
            "permission_id": permission_id,
        },
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE role_id = (SELECT id FROM roles WHERE code = 'SSC_ADMIN')
              AND permission_id = (
                  SELECT id FROM permissions WHERE code = 'ONBOARDING_INITIATE'
              )
            """
        )
    )
    connection.execute(
        sa.text(
            """
            DELETE FROM permissions AS permission
            WHERE permission.code = 'ONBOARDING_INITIATE'
              AND NOT EXISTS (
                  SELECT 1 FROM role_permissions
                  WHERE role_permissions.permission_id = permission.id
              )
            """
        )
    )
