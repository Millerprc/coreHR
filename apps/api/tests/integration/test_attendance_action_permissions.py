# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""C5 — 考勤高风险动作独立权限码的集成用例。

Requirement: C5 — 考勤高风险动作拆独立权限码。
依据：``docs/review/D-考勤-待确认-决策-文档规范.md`` §8「权限与审计」（14.md:185 行，P0 判定「与 PRD 冲突」）：
「规则发布 / 批量排班 / 打卡补录 / 余额调整 / 日报重算 / 月报重算 / 冻结解冻」7 类高风险动作
此前共用一个 ``ATTENDANCE_ADMIN``，本用例锁定拆分后的三条语义：

1. 持有对应独立权限码的账号**可以**执行该高风险动作；
2. 只持有 ``ATTENDANCE_ADMIN`` 的账号对该高风险动作**被拒**（403 PERMISSION_DENIED）；
3. ``ATTENDANCE_ADMIN`` 仍然可以执行**普通考勤操作**（查询、班次、假期类型、规则集草稿等）。
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.platform.models import (
    Permission,
    Role,
    RolePermission,
    UserAccount,
    UserRole,
    UserSession,
)
from hris.modules.platform.security import hash_password, token_digest
from hris.modules.workforce.models import Employment, Person


pytestmark = pytest.mark.asyncio


# Requirement: C5 — 7 类高风险动作对应的独立权限码（审计报告 14.md:185 行）。
ACTION_PERMISSION_CODES: tuple[str, ...] = (
    "ATTENDANCE_RULE_PUBLISH",
    "ATTENDANCE_SCHEDULE_WRITE",
    "ATTENDANCE_PUNCH_BACKFILL",
    "ATTENDANCE_BALANCE_ADJUST",
    "ATTENDANCE_DAILY_RECALC",
    "ATTENDANCE_MONTHLY_RECALC",
    "ATTENDANCE_FREEZE_MANAGE",
)

ATTENDANCE_ADMIN_ROLE_CODE = "ATTENDANCE_ADMIN"

# 迁移文件路径：用于直接验证迁移的授权语句（幂等性）。
_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "f2n000000001_seed_attendance_action_permissions.py"
)


def _load_migration_module() -> ModuleType:
    spec = spec_from_file_location(
        "f2n000000001_seed_attendance_action_permissions", _MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@dataclass(frozen=True)
class AttendanceCaseContext:
    """一次用例所需的合成业务数据。"""

    employment_id: str
    published_rule_set_id: str
    draft_rule_set_id: str
    shift_id: str
    leave_type_id: str


async def _token_with_permission(
    db_session: AsyncSession,
    permission_code: str,
    slug: str,
) -> str:
    """造一个「只持有单个权限码」的账号。

    Requirement: C5 — 权限粒度验证必须能表达「有 A 没有 B」，
    因此这里每个账号只挂一个权限码，不借用通配码 `*`。
    """
    now = datetime.now(UTC)
    permission = await db_session.scalar(
        select(Permission).where(Permission.code == permission_code)
    )
    assert permission is not None, f"权限码 {permission_code} 必须已经落库"
    role_code = f"SYNTHETIC_C5_{slug.upper().replace('-', '_')}"
    role = await db_session.scalar(select(Role).where(Role.code == role_code))
    if role is None:
        role = Role(
            code=role_code,
            name=f"合成角色 {role_code}",
            is_system=False,
            is_active=True,
        )
        db_session.add(role)
    user = UserAccount(
        username=f"synthetic-c5-{slug}",
        display_name=f"合成账号 {slug}",
        password_hash=hash_password("synthetic-test-password"),
        status="active",
        failed_attempts=0,
    )
    db_session.add(user)
    await db_session.flush()
    raw_token = f"synthetic-c5-{slug}-token"
    db_session.add_all(
        [
            UserRole(user_id=user.id, role_id=role.id),
            RolePermission(role_id=role.id, permission_id=permission.id),
            UserSession(
                user_id=user.id,
                token_hash=token_digest(raw_token),
                expires_at=now + timedelta(hours=1),
                last_seen_at=now,
            ),
        ]
    )
    await db_session.flush()
    return raw_token


@pytest_asyncio.fixture
async def attendance_context(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> AttendanceCaseContext:
    """准备合成数据：劳动关系、一个已发布规则集、一个草稿规则集、一个班次、一个可跟踪余额的假期类型。"""
    person = Person(
        employee_number="990050",
        legal_name="Synthetic attendance permission person",
        display_name="Synthetic attendance permission person",
        status="active",
    )
    db_session.add(person)
    await db_session.flush()
    employment = Employment(
        person_id=person.id,
        employee_type_code="REGULAR",
        status="active",
        planned_start_date=date(2026, 1, 1),
        actual_start_date=date(2026, 1, 1),
        version=1,
    )
    db_session.add(employment)
    await db_session.flush()

    published = await business_client.post(
        "/api/v1/attendance/rule-sets",
        headers=_auth(admin_token),
        json={
            "code": "C5_PUBLISHED",
            "name": "合成已发布规则集",
            "timezone": "Asia/Shanghai",
            "effective_from": "2026-01-01",
        },
    )
    assert published.status_code == 201, published.text
    published_rule_set_id = published.json()["id"]
    publish_published = await business_client.post(
        f"/api/v1/attendance/rule-sets/{published_rule_set_id}/publish",
        headers=_auth(admin_token),
    )
    assert publish_published.status_code == 200, publish_published.text

    draft = await business_client.post(
        "/api/v1/attendance/rule-sets",
        headers=_auth(admin_token),
        json={
            "code": "C5_DRAFT",
            "name": "合成草稿规则集",
            "timezone": "Asia/Shanghai",
            "effective_from": "2026-01-01",
        },
    )
    assert draft.status_code == 201, draft.text

    shift = await business_client.post(
        "/api/v1/attendance/shifts",
        headers=_auth(admin_token),
        json={
            "code": "C5_SHIFT",
            "name": "合成班次",
            "start_time": "09:00:00",
            "end_time": "18:00:00",
            "rule_set_id": published_rule_set_id,
        },
    )
    assert shift.status_code == 201, shift.text

    leave_type = await business_client.post(
        "/api/v1/attendance/leave-types",
        headers=_auth(admin_token),
        json={
            "code": "C5_LEAVE",
            "name": "合成假期类型",
            "unit": "day",
            "rules": {"balance_mode": "tracked"},
        },
    )
    assert leave_type.status_code == 201, leave_type.text

    return AttendanceCaseContext(
        employment_id=str(employment.id),
        published_rule_set_id=published_rule_set_id,
        draft_rule_set_id=draft.json()["id"],
        shift_id=shift.json()["id"],
        leave_type_id=leave_type.json()["id"],
    )


def _case_body(case_id: str, context: AttendanceCaseContext) -> dict[str, Any] | None:
    """按动作类型构造请求体（全部使用合法业务数据，确保 403 只可能来自权限）。"""
    if case_id == "rule-publish":
        return None
    if case_id == "schedule-write":
        return {
            "period_code": "2026-09",
            "lines": [
                {
                    "employment_id": context.employment_id,
                    "work_date": "2026-09-10",
                    "shift_id": context.shift_id,
                }
            ],
        }
    if case_id == "punch-backfill":
        return {
            "employment_id": context.employment_id,
            "punched_at": datetime(2026, 9, 10, 9, 0, tzinfo=UTC).isoformat(),
            "punch_type": "in",
            "source": "manual",
            "source_record_id": f"c5-punch-{uuid.uuid4()}",
        }
    if case_id == "balance-adjust":
        return {
            "employment_id": context.employment_id,
            "leave_type_id": context.leave_type_id,
            "period_year": 2026,
            "transaction_type": "adjustment",
            "amount": "1.00",
            "effective_date": "2026-09-01",
            "reason": "Synthetic balance adjustment",
            "idempotency_key": str(uuid.uuid4()),
        }
    if case_id == "daily-recalc":
        return {
            "employment_id": context.employment_id,
            "work_date": "2026-09-10",
            "reason": "Synthetic daily recalculation",
        }
    if case_id == "monthly-recalc":
        return {
            "employment_id": context.employment_id,
            "period_month": "2026-09-01",
            "reason": "Synthetic monthly recalculation",
        }
    if case_id == "freeze-manage":
        return {
            "freeze_type": "special",
            "date_from": "2026-09-20",
            "date_to": "2026-09-25",
            "reason": "Synthetic special freeze",
        }
    raise AssertionError(f"未登记的用例：{case_id}")


# Requirement: C5 — 7 类高风险动作 → 独立权限码 → 端点 的对照表。
HIGH_RISK_CASES: tuple[dict[str, Any], ...] = (
    {
        "id": "rule-publish",
        "permission_code": "ATTENDANCE_RULE_PUBLISH",
        "method": "POST",
        "path": "/api/v1/attendance/rule-sets/{rule_set_id}/publish",
        "expected_status": 200,
    },
    {
        "id": "schedule-write",
        "permission_code": "ATTENDANCE_SCHEDULE_WRITE",
        "method": "POST",
        "path": "/api/v1/attendance/schedules/draft",
        "expected_status": 201,
    },
    {
        "id": "punch-backfill",
        "permission_code": "ATTENDANCE_PUNCH_BACKFILL",
        "method": "POST",
        "path": "/api/v1/attendance/punches",
        "expected_status": 201,
    },
    {
        "id": "balance-adjust",
        "permission_code": "ATTENDANCE_BALANCE_ADJUST",
        "method": "POST",
        "path": "/api/v1/attendance/leave-balances/transactions",
        "expected_status": 201,
    },
    {
        "id": "daily-recalc",
        "permission_code": "ATTENDANCE_DAILY_RECALC",
        "method": "POST",
        "path": "/api/v1/attendance/daily-results/calculate",
        "expected_status": 201,
    },
    {
        "id": "monthly-recalc",
        "permission_code": "ATTENDANCE_MONTHLY_RECALC",
        "method": "POST",
        "path": "/api/v1/attendance/monthly-results/calculate",
        "expected_status": 201,
    },
    {
        "id": "freeze-manage",
        "permission_code": "ATTENDANCE_FREEZE_MANAGE",
        "method": "POST",
        "path": "/api/v1/attendance/period-freezes",
        "expected_status": 201,
    },
)

_CASE_IDS = [case["id"] for case in HIGH_RISK_CASES]


def _case_url(case: dict[str, Any], context: AttendanceCaseContext) -> str:
    """规则发布作用草稿规则集；其余动作使用固定路径。"""
    rule_set_id = (
        context.draft_rule_set_id if case["id"] == "rule-publish" else context.published_rule_set_id
    )
    return case["path"].format(rule_set_id=rule_set_id)


async def test_action_permission_codes_are_seeded(db_session: AsyncSession) -> None:
    """7 个新码 + 两个域级码都必须落库（权限码不落库就永远无法被角色持有）。"""
    codes = (*ACTION_PERMISSION_CODES, "ATTENDANCE_ADMIN", "LIFECYCLE_ADMIN")
    rows = (
        await db_session.execute(
            select(Permission.code, Permission.module_code).where(Permission.code.in_(codes))
        )
    ).all()
    stored = {row.code: row.module_code for row in rows}
    assert set(stored) == set(codes), f"权限码缺失：{sorted(set(codes) - set(stored))}"
    for code in ACTION_PERMISSION_CODES:
        assert stored[code] == "ATTENDANCE"
    assert stored["ATTENDANCE_ADMIN"] == "ATTENDANCE"
    assert stored["LIFECYCLE_ADMIN"] == "LIFECYCLE"


async def test_attendance_admin_role_holds_all_action_permission_codes(
    db_session: AsyncSession,
) -> None:
    """既有「考勤管理员」角色持有 7 个动作码（不新建角色）。"""
    role = await db_session.scalar(
        select(Role).where(Role.code == ATTENDANCE_ADMIN_ROLE_CODE)
    )
    assert role is not None, "考勤管理员角色必须已落库（f2g000000001）"
    granted = set(
        (
            await db_session.scalars(
                select(Permission.code)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id == role.id)
            )
        ).all()
    )
    assert set(ACTION_PERMISSION_CODES).issubset(granted)


@pytest.mark.parametrize("case", HIGH_RISK_CASES, ids=_CASE_IDS)
async def test_attendance_admin_only_is_rejected_for_high_risk_action(
    business_client: AsyncClient,
    db_session: AsyncSession,
    attendance_context: AttendanceCaseContext,
    case: dict[str, Any],
) -> None:
    """只持有 ATTENDANCE_ADMIN 的账号不能执行 7 类高风险动作。"""
    token = await _token_with_permission(
        db_session, "ATTENDANCE_ADMIN", f"admin-{case['id']}"
    )
    response = await business_client.request(
        case["method"],
        _case_url(case, attendance_context),
        headers=_auth(token),
        json=_case_body(case["id"], attendance_context),
    )
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "PERMISSION_DENIED"


@pytest.mark.parametrize("case", HIGH_RISK_CASES, ids=_CASE_IDS)
async def test_action_permission_code_unlocks_matching_high_risk_action(
    business_client: AsyncClient,
    db_session: AsyncSession,
    attendance_context: AttendanceCaseContext,
    case: dict[str, Any],
) -> None:
    """只持有对应独立权限码的账号可以执行该高风险动作。"""
    token = await _token_with_permission(
        db_session, case["permission_code"], f"action-{case['id']}"
    )
    response = await business_client.request(
        case["method"],
        _case_url(case, attendance_context),
        headers=_auth(token),
        json=_case_body(case["id"], attendance_context),
    )
    assert response.status_code == case["expected_status"], response.text
    if case["id"] == "rule-publish":
        assert response.json()["status"] == "active"


async def test_attendance_admin_can_still_perform_ordinary_attendance_operations(
    business_client: AsyncClient,
    db_session: AsyncSession,
    attendance_context: AttendanceCaseContext,
) -> None:
    """普通考勤操作仍然只要求 ATTENDANCE_ADMIN，不被新码收窄。"""
    token = await _token_with_permission(db_session, "ATTENDANCE_ADMIN", "ordinary")
    for path in (
        "/api/v1/attendance/shifts",
        "/api/v1/attendance/punches",
        "/api/v1/attendance/leave-types",
        "/api/v1/attendance/rule-sets",
        "/api/v1/attendance/period-freezes",
        "/api/v1/attendance/schedules",
    ):
        response = await business_client.get(path, headers=_auth(token))
        assert response.status_code == 200, f"{path} -> {response.text}"
    created = await business_client.post(
        "/api/v1/attendance/leave-types",
        headers=_auth(token),
        json={
            "code": "C5_ORDINARY",
            "name": "合成普通假期类型",
            "unit": "day",
            "rules": {"balance_mode": "tracked"},
        },
    )
    assert created.status_code == 201, created.text


async def test_action_permission_code_can_be_granted_to_a_custom_role(
    db_session: AsyncSession,
) -> None:
    """新码可以授予自定义角色；迁移的授权语句重复执行保持幂等。"""
    permission = await db_session.scalar(
        select(Permission).where(Permission.code == "ATTENDANCE_DAILY_RECALC")
    )
    assert permission is not None
    role = Role(
        code="SYNTHETIC_C5_GRANT_TARGET",
        name="合成授权目标角色",
        is_system=False,
        is_active=True,
    )
    db_session.add(role)
    await db_session.flush()

    migration = _load_migration_module()
    connection = await db_session.connection()

    def _grant_twice(sync_connection) -> None:
        migration._grant_to_role(
            sync_connection,
            "SYNTHETIC_C5_GRANT_TARGET",
            ("ATTENDANCE_DAILY_RECALC",),
        )
        migration._grant_to_role(
            sync_connection,
            "SYNTHETIC_C5_GRANT_TARGET",
            ("ATTENDANCE_DAILY_RECALC",),
        )

    await connection.run_sync(_grant_twice)
    await db_session.flush()

    granted = set(
        (
            await db_session.scalars(
                select(Permission.code)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id == role.id)
            )
        ).all()
    )
    assert granted == {"ATTENDANCE_DAILY_RECALC"}
    rows = list(
        await db_session.scalars(
            select(RolePermission.id).where(
                RolePermission.role_id == role.id,
                RolePermission.permission_id == permission.id,
            )
        )
    )
    assert len(rows) == 1, "重复授权不应产生重复授权行"
