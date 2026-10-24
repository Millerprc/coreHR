# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""seed attendance high-risk action permission codes

把考勤域 7 类高风险动作从粗粒度的 ``ATTENDANCE_ADMIN`` 拆成独立权限码，并补齐
``ATTENDANCE_ADMIN`` / ``LIFECYCLE_ADMIN`` 两个域级权限码的落库。

Requirement: C5 — 考勤高风险动作拆独立权限码。
审计依据：``docs/review/D-考勤-待确认-决策-文档规范.md`` §8「权限与审计」
（14.md:185 行，P0 判定「与 PRD 冲突」）——规则发布 / 批量排班 / 打卡补录 / 余额调整 /
日报重算 / 月报重算 / 冻结解冻 7 类动作此前共用一个 ``ATTENDANCE_ADMIN``，
本迁移把 7 类动作对应的权限码落库，授权链才真正可用。

权限码台账（码 → 管住的动作 → 端点）：

====================== ============================ ==========================================
权限码                  管住的动作                     端点
====================== ============================ ==========================================
ATTENDANCE_RULE_PUBLISH 考勤规则集发布（生效）          POST /api/v1/attendance/rule-sets/{id}/publish
ATTENDANCE_SCHEDULE_WRITE 排班写入（单条/草稿/发布/换班） POST /api/v1/attendance/schedules*、/schedule-publish-batches*、/schedule-swaps*
ATTENDANCE_PUNCH_BACKFILL 打卡证据写入（人工补录）       POST /api/v1/attendance/punches
ATTENDANCE_BALANCE_ADJUST 假期余额流水写入（调整/发放/作废） POST /api/v1/attendance/leave-balances/transactions、/leave-grant-batches/{id}/*
ATTENDANCE_DAILY_RECALC 考勤日报重算                    POST /api/v1/attendance/daily-results/calculate
ATTENDANCE_MONTHLY_RECALC 考勤月报重算                  POST /api/v1/attendance/monthly-results/calculate
ATTENDANCE_FREEZE_MANAGE 考勤期间冻结与解冻             POST /api/v1/attendance/period-freezes*
====================== ============================ ==========================================

授予口径：沿用 ``f2g000000001_seed_business_admin_roles.py`` 的既有角色目录，
只把 7 个动作码授予既有的「考勤管理员」角色（``roles.code = 'ATTENDANCE_ADMIN'``），
**不发明新角色**，``*`` 超级管理员通配放行不受影响。

Revision ID: f2n000000001
Revises: f2o000000001
Create Date: 2026-10-24
"""

from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "f2n000000001"
down_revision: str | Sequence[str] | None = "f2o000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Requirement: C5 — 考勤高风险动作拆独立权限码。
# 码名沿用审计报告 14.md:185 行给出的拆分建议（ATTENDANCE_ 前缀 + 动作语义）。
ATTENDANCE_ACTION_PERMISSION_SPECS: dict[str, tuple[str, str]] = {
    "ATTENDANCE_RULE_PUBLISH": ("发布考勤规则集", "ATTENDANCE"),
    "ATTENDANCE_SCHEDULE_WRITE": ("写入与发布排班", "ATTENDANCE"),
    "ATTENDANCE_PUNCH_BACKFILL": ("补录打卡证据", "ATTENDANCE"),
    "ATTENDANCE_BALANCE_ADJUST": ("调整假期余额", "ATTENDANCE"),
    "ATTENDANCE_DAILY_RECALC": ("重算考勤日报", "ATTENDANCE"),
    "ATTENDANCE_MONTHLY_RECALC": ("重算考勤月报", "ATTENDANCE"),
    "ATTENDANCE_FREEZE_MANAGE": ("冻结与解冻考勤期间", "ATTENDANCE"),
}

# Requirement: C5 — 一并兜底两个域级权限码的落库。
# 说明：这两个码由 f2f000000001 首次种入，本迁移以幂等方式兜底，
# 保证「任何一条链路先跑到 f2n」时 permissions 表里也一定有它们。
# 回滚时**不删除**它们（归属 f2f000000001），避免跨迁移互相破坏。
DOMAIN_PERMISSION_SPECS: dict[str, tuple[str, str]] = {
    "ATTENDANCE_ADMIN": ("管理考勤", "ATTENDANCE"),
    "LIFECYCLE_ADMIN": ("管理员工生命周期", "LIFECYCLE"),
}

# Requirement: C5 — 授予既有角色，不新建角色。
# 口径来源：f2g000000001_seed_business_admin_roles.py 的 ROLE_SPECS
# （HEADCOUNT_ADMIN / LIFECYCLE_ADMIN / ATTENDANCE_ADMIN）与 ROLE_PERMISSION_SPECS。
ATTENDANCE_ADMIN_ROLE_CODE = "ATTENDANCE_ADMIN"

# Requirement: C5 — 本迁移负责的权限码集合，回滚时按这个集合回收。
OWNED_PERMISSION_CODES: tuple[str, ...] = tuple(ATTENDANCE_ACTION_PERMISSION_SPECS)


def _insert_missing_permissions(connection, specs: dict[str, tuple[str, str]]) -> None:
    """幂等插入权限码：已存在的码不重复写。"""
    permission_table = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("module_code", sa.String()),
    )
    quoted_codes = ", ".join(f"'{code}'" for code in specs)
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
        for code, (name, module_code) in specs.items()
        if code not in existing
    ]
    if missing:
        op.bulk_insert(permission_table, missing)


def _grant_to_role(
    connection,
    role_code: str,
    permission_codes: tuple[str, ...],
) -> None:
    """把权限码授予指定角色，重复执行不产生重复授权行。

    Requirement: C5 — 幂等靠「授权前先看有没有」实现，
    不依赖唯一约束兜底（重复执行不应该炸，也不应该留下重复行）。
    """
    for permission_code in permission_codes:
        connection.execute(
            sa.text(
                """
                INSERT INTO role_permissions (id, role_id, permission_id)
                SELECT :id, role.id, permission.id
                FROM roles AS role
                CROSS JOIN permissions AS permission
                WHERE role.code = :role_code
                  AND permission.code = :permission_code
                  AND NOT EXISTS (
                      SELECT 1
                      FROM role_permissions
                      WHERE role_id = role.id AND permission_id = permission.id
                  )
                """
            ),
            {
                "id": uuid4(),
                "permission_code": permission_code,
                "role_code": role_code,
            },
        )


def _grant_to_attendance_admin(connection, permission_codes: tuple[str, ...]) -> None:
    """把动作权限码授予「考勤管理员」角色。"""
    _grant_to_role(connection, ATTENDANCE_ADMIN_ROLE_CODE, permission_codes)


def upgrade() -> None:
    connection = op.get_bind()
    _insert_missing_permissions(connection, ATTENDANCE_ACTION_PERMISSION_SPECS)
    _insert_missing_permissions(connection, DOMAIN_PERMISSION_SPECS)
    _grant_to_attendance_admin(connection, OWNED_PERMISSION_CODES)


def downgrade() -> None:
    """回收本迁移种下的 7 个动作权限码及其授权行。

    Requirement: C5 — 只回收本迁移自有的权限码：
    ATTENDANCE_ADMIN / LIFECYCLE_ADMIN 归属 f2f000000001，这里不动；
    被其它角色引用的权限码行跳过而不是报错，保证回滚不破坏既有授权关系。
    """
    connection = op.get_bind()
    quoted_codes = ", ".join(f"'{code}'" for code in OWNED_PERMISSION_CODES)
    connection.execute(
        sa.text(
            f"""
            DELETE FROM role_permissions
            WHERE permission_id IN (
                SELECT id FROM permissions WHERE code IN ({quoted_codes})
            )
            """
        )
    )
    connection.execute(
        sa.text(
            f"""
            DELETE FROM permissions AS permission
            WHERE permission.code IN ({quoted_codes})
            AND NOT EXISTS (
                SELECT 1 FROM role_permissions
                WHERE role_permissions.permission_id = permission.id
            )
            """
        )
    )
