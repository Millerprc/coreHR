# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""seed business administrator roles and bind workforce scope to SSC

Revision ID: f2g000000001
Revises: f2f000000001
Create Date: 2026-10-24
"""

from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "f2g000000001"
down_revision: str | Sequence[str] | None = "f2f000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Requirement: D-062 — 第一阶段不预置只读审计员，SSC 仍是首批业务管理角色。
# Requirement: D-053 — 持有 WORKFORCE_ADMIN 的角色必须同时持有人员档案权限。
# Requirement: D-004 — 权限码必须先落库才能被角色持有；本迁移只解决「角色目录」，
# 不新增权限码（3 个权限码已在 f2f000000001 种入）。
ROLE_SPECS: dict[str, tuple[str, str]] = {
    "HEADCOUNT_ADMIN": ("编制管理员", "负责编制、职务维度、汇报关系与人员档案维护"),
    "LIFECYCLE_ADMIN": ("员工生命周期管理员", "负责入职、转正、异动、离职与合同流程"),
    "ATTENDANCE_ADMIN": ("考勤管理员", "负责考勤规则、班次、排班、打卡与假勤"),
}

ROLE_PERMISSION_SPECS: dict[str, tuple[str, ...]] = {
    "HEADCOUNT_ADMIN": (
        "WORKFORCE_ADMIN",
        "PERSON_VIEW",
        "PERSON_EDIT_BASIC",
        "PERSON_SENSITIVE_VIEW",
        "PERSON_IMPORT",
        "PERSON_EXPORT",
    ),
    "LIFECYCLE_ADMIN": ("LIFECYCLE_ADMIN",),
    "ATTENDANCE_ADMIN": ("ATTENDANCE_ADMIN",),
}

# SSC 首批业务管理角色：授予人力编制入口后，其人员档案权限与 WORKFORCE_ADMIN
# 持有者保持一致（与 f2f000000001 的授权意图相同）。
SSC_EXTRA_PERMISSION_CODES: tuple[str, ...] = (
    "WORKFORCE_ADMIN",
    "PERSON_VIEW",
    "PERSON_EDIT_BASIC",
    "PERSON_SENSITIVE_VIEW",
    "PERSON_IMPORT",
    "PERSON_EXPORT",
)


def _role_id(connection, code: str):
    return connection.execute(
        sa.text("SELECT id FROM roles WHERE code = :code"), {"code": code}
    ).scalar_one_or_none()


def _ensure_role(connection, code: str, name: str, description: str) -> None:
    if _role_id(connection, code) is not None:
        return
    connection.execute(
        sa.text(
            """
            INSERT INTO roles (id, code, name, description, is_system, is_active)
            VALUES (:id, :code, :name, :description, true, true)
            """
        ),
        {"id": uuid4(), "code": code, "name": name, "description": description},
    )


def _grant(connection, role_code: str, permission_code: str) -> None:
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
            "role_id": _role_id(connection, role_code),
            "permission_id": connection.execute(
                sa.text("SELECT id FROM permissions WHERE code = :code"),
                {"code": permission_code},
            ).scalar_one(),
        },
    )


def upgrade() -> None:
    connection = op.get_bind()

    for code, (name, description) in ROLE_SPECS.items():
        _ensure_role(connection, code, name, description)

    for role_code, permission_codes in ROLE_PERMISSION_SPECS.items():
        for permission_code in permission_codes:
            _grant(connection, role_code, permission_code)

    for permission_code in SSC_EXTRA_PERMISSION_CODES:
        _grant(connection, "SSC_ADMIN", permission_code)


def downgrade() -> None:
    connection = op.get_bind()

    for role_code, permission_codes in ROLE_PERMISSION_SPECS.items():
        for permission_code in permission_codes:
            connection.execute(
                sa.text(
                    """
                    DELETE FROM role_permissions
                    WHERE role_id = (SELECT id FROM roles WHERE code = :role_code)
                      AND permission_id = (
                          SELECT id FROM permissions WHERE code = :permission_code
                      )
                    """
                ),
                {"role_code": role_code, "permission_code": permission_code},
            )

    for permission_code in SSC_EXTRA_PERMISSION_CODES:
        connection.execute(
            sa.text(
                """
                DELETE FROM role_permissions
                WHERE role_id = (SELECT id FROM roles WHERE code = 'SSC_ADMIN')
                  AND permission_id = (
                      SELECT id FROM permissions WHERE code = :permission_code
                  )
                """
            ),
            {"permission_code": permission_code},
        )

    for code in ROLE_SPECS:
        connection.execute(
            sa.text("DELETE FROM roles WHERE code = :code"), {"code": code}
        )
