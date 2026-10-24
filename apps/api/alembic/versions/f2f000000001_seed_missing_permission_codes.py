# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""seed missing workforce, lifecycle and attendance permission codes

Revision ID: f2f000000001
Revises: f2e000000001
Create Date: 2026-10-24
"""

from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision: str = "f2f000000001"
down_revision: str | Sequence[str] | None = "f2e000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Requirement: D-004 — 第一批用户为系统管理员和 SSC，两类角色的模块入口分别由
# WORKFORCE_ADMIN / LIFECYCLE_ADMIN / ATTENDANCE_ADMIN 三个权限码把守。
# 权限解析链是 permissions → role_permissions → roles → user_roles，
# permissions 表里没有的行永远无法被任何角色持有，因此这三个权限码必须先落库，
# 否则除持 `*` 的主管理员外，任何人访问对应接口都会得到 403。
SEEDED_PERMISSION_SPECS: dict[str, tuple[str, str]] = {
    "WORKFORCE_ADMIN": ("管理人力编制", "WORKFORCE"),
    "LIFECYCLE_ADMIN": ("管理员工生命周期", "LIFECYCLE"),
    "ATTENDANCE_ADMIN": ("管理考勤", "ATTENDANCE"),
}

# Requirement: D-053 — 权限需要支持可配置角色与动作，
# 持有 WORKFORCE_ADMIN 的角色必须同时持有下列人员档案权限，
# 与 f1c000000001 原本的授权意图保持一致。
PERSON_PERMISSION_CODES_GRANTED_TO_WORKFORCE_ADMIN: tuple[str, ...] = (
    "PERSON_VIEW",
    "PERSON_EDIT_BASIC",
    "PERSON_SENSITIVE_VIEW",
    "PERSON_IMPORT",
    "PERSON_EXPORT",
)


def person_permission_grant_sql() -> str:
    """返回人员档案权限的授权语句。

    Requirement: D-053 — 授权语义与 f1c000000001 的原始意图一致：
    持有 WORKFORCE_ADMIN 的角色自动获得 PERSON_* 权限，
    重复执行依靠 ON CONFLICT (role_id, permission_id) DO NOTHING 保持幂等。
    """

    codes = ", ".join(
        f"'{code}'" for code in PERSON_PERMISSION_CODES_GRANTED_TO_WORKFORCE_ADMIN
    )
    return f"""
        INSERT INTO role_permissions (id, role_id, permission_id)
        SELECT gen_random_uuid(), workforce_roles.role_id, person_permissions.id
        FROM (
            SELECT DISTINCT role_permissions.role_id
            FROM role_permissions
            JOIN permissions ON permissions.id = role_permissions.permission_id
            WHERE permissions.code = 'WORKFORCE_ADMIN'
        ) AS workforce_roles
        CROSS JOIN permissions AS person_permissions
        WHERE person_permissions.code IN ({codes})
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """


def grant_person_permissions_to_workforce_roles(connection: Connection) -> None:
    """把人员档案权限授予当前持有 WORKFORCE_ADMIN 的角色。

    Requirement: D-062 — 第一阶段不预置只读审计员，SSC 仍是首批业务管理角色。
    本迁移只负责让权限码可被授予，不预设立任何角色与权限的绑定；
    当前没有角色持有 WORKFORCE_ADMIN，这一步是空操作，
    将来一旦有人授予 WORKFORCE_ADMIN，人员档案权限会自动跟上。
    """

    connection.execute(sa.text(person_permission_grant_sql()))


def upgrade() -> None:
    connection = op.get_bind()
    permission_table = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("module_code", sa.String()),
    )
    quoted_codes = ", ".join(f"'{code}'" for code in SEEDED_PERMISSION_SPECS)
    existing = set(
        connection.execute(
            sa.text(f"SELECT code FROM permissions WHERE code IN ({quoted_codes})")
        ).scalars()
    )
    missing = [
        {
            "id": uuid4(),
            "code": code,
            "name": name,
            "module_code": module_code,
        }
        for code, (name, module_code) in SEEDED_PERMISSION_SPECS.items()
        if code not in existing
    ]
    if missing:
        op.bulk_insert(permission_table, missing)

    grant_person_permissions_to_workforce_roles(connection)


def downgrade() -> None:
    # Requirement: D-067 — 回滚只删除本迁移种下的三个权限码，
    # 且必须以「没有任何 role_permissions 引用它」为前提，
    # 被角色引用的行跳过而不是报错，保证回滚不会连带破坏授权关系。
    op.execute(
        """
        DELETE FROM permissions AS permission
        WHERE permission.code IN (
            'WORKFORCE_ADMIN', 'LIFECYCLE_ADMIN', 'ATTENDANCE_ADMIN'
        )
        AND NOT EXISTS (
            SELECT 1 FROM role_permissions
            WHERE role_permissions.permission_id = permission.id
        )
        """
    )
