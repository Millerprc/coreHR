# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""grant attendance rights to the SSC role

把考勤域的权限授予既有的 ``SSC_ADMIN`` 角色。

Requirement: D-004 / D-111 — 第一批用户为系统管理员和 SSC。
审计依据：``docs/review/D-考勤-待确认-决策-文档规范.md`` §8「权限与审计」
（14.md:184 行，P0 判定「与 PRD 冲突」）——PRD 明写「首批优先支持系统管理员和 SSC」，
但 ``SSC_ADMIN`` 此前只持有 ``ONBOARDING_INITIATE`` 与人员档案相关的 6 个权限码，
**一个考勤权限都没有**，导致 SSC 实际进不了考勤模块。

本迁移的授予范围：**只授予考勤域 8 个权限码**。

取舍说明：

- **不新建角色**，只扩展既有 ``SSC_ADMIN`` 角色的权限集合；
- **不授予 ``LIFECYCLE_ADMIN``**：生命周期域有独立的、更窄的职责边界——
  SSC 只发起入职建档（``ONBOARDING_INITIATE``），发起终止等其它人事事件必须被拒绝
  （既有集成测试 ``test_ssc_can_initiate_only_onboarding_and_creation_is_audited``
  明确断言 SSC 创建 TERMINATION 返回 403）。授予域级 ``LIFECYCLE_ADMIN``
  会打破这条边界，因此**不纳入本迁移**。审计 14.md:184 提到的「生命周期模块」
  若要另行放开，需要单独拆出「发起某类人事事件」的细粒度权限码，不能用域级码。
- **不改超级管理员**的 ``*`` 通配；
- 7 个高风险动作码保持**独立可收窄**：若后续要把「余额调整」「期间冻结与解冻」
  从 SSC 手上收回，只需要再写一条迁移删除对应授权行，不必改代码；
- 审计同时指出「普通角色数据范围（行级范围）未实现」（14.md:189，P1），
  因此持码者当前可作用于**全部**劳动关系；这一点已在待确认清单里登记。

Revision ID: f2q000000001
Revises: f2p000000001
Create Date: 2026-10-24
"""

from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "f2q000000001"
down_revision: str | Sequence[str] | None = "f2p000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: Requirement: D-111 — 授予 SSC 的权限码集合（**仅考勤域**）。
#: 权限码本身由 f2n000000001（考勤 7 个动作码）与 f2f000000001（域级码）落库，
#: 本迁移**只建授权关系，不建权限码行**，因此不重复承担权限码的所有权。
#:
#: 刻意**不含** ``LIFECYCLE_ADMIN``：SSC 在生命周期域的职责是「发起入职建档」，
#: 由 ONBOARDING_INITIATE 单独授予；域级 LIFECYCLE_ADMIN 会让 SSC 越过
#: 「不得发起终止等其它人事事件」的边界。
SSC_GRANTED_PERMISSION_CODES: tuple[str, ...] = (
    "ATTENDANCE_ADMIN",
    "ATTENDANCE_RULE_PUBLISH",
    "ATTENDANCE_SCHEDULE_WRITE",
    "ATTENDANCE_PUNCH_BACKFILL",
    "ATTENDANCE_BALANCE_ADJUST",
    "ATTENDANCE_DAILY_RECALC",
    "ATTENDANCE_MONTHLY_RECALC",
    "ATTENDANCE_FREEZE_MANAGE",
)

#: Requirement: D-111 — 授予对象是既有角色，不新建角色。
SSC_ROLE_CODE = "SSC_ADMIN"


def _grant_to_role(
    connection,
    role_code: str,
    permission_codes: tuple[str, ...],
) -> None:
    """把权限码授予指定角色，重复执行不产生重复授权行。

    Requirement: D-111 — 幂等靠「授权前先看有没有」实现，
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


def upgrade() -> None:
    """给 SSC_ADMIN 授予考勤域与生命周期域权限。

    Requirement: D-111 — 权限码行已由上游迁移种好，本迁移只补授权关系。
    若某个权限码在目标库里不存在（上游迁移被回滚过），授权语句自然跳过，
    不会凭空造出没有 Permission 行的授权。
    """
    connection = op.get_bind()
    _grant_to_role(connection, SSC_ROLE_CODE, SSC_GRANTED_PERMISSION_CODES)


def downgrade() -> None:
    """只回收本迁移建立的授权行。

    Requirement: D-111 — **不删除 permissions 行**：权限码归属 f2n / f2f，
    这里只删 ``role_permissions`` 里 (SSC_ADMIN × 本迁移权限码) 的那一批，
    保证回滚后 SSC 回到本迁移之前的状态，且不破坏其它角色的授权。
    """
    connection = op.get_bind()
    quoted_codes = ", ".join(f"'{code}'" for code in SSC_GRANTED_PERMISSION_CODES)
    connection.execute(
        sa.text(
            f"""
            DELETE FROM role_permissions
            WHERE role_id IN (SELECT id FROM roles WHERE code = '{SSC_ROLE_CODE}')
              AND permission_id IN (
                  SELECT id FROM permissions WHERE code IN ({quoted_codes})
              )
            """
        )
    )
