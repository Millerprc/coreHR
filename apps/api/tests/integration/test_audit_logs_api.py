# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

import csv
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from io import StringIO
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.business_main import create_business_app
from hris.core.database import get_db
from hris.modules.platform.audit_api import router as audit_router
from hris.modules.platform.models import (
    Permission,
    Role,
    RolePermission,
    UserAccount,
    UserRole,
    UserSession,
)
from hris.modules.platform.security import hash_password, token_digest
from hris.modules.workforce.models import AuditLog


pytestmark = pytest.mark.asyncio

_AUDIT_LIST_PATH = "/api/v1/platform/audit-logs"
_AUDIT_ACTORS_PATH = "/api/v1/platform/audit/actors"
_CSV_COLUMNS = [
    "occurred_at",
    "actor_name",
    "action",
    "object_type",
    "object_id",
    "trace_id",
    "reason",
    "source",
]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def audit_client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    app = create_business_app()
    # 审计路由由主 agent 统一注册到 business_router.py；尚未注册时在此临时挂载，保证用例可独立运行。
    if not any(getattr(route, "path", "") == _AUDIT_LIST_PATH for route in app.routes):
        app.include_router(audit_router)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def _audit_log(
    *,
    occurred_at: datetime,
    actor_id: UUID | None = None,
    action: str = "person.update",
    object_type: str = "person",
    object_id: UUID | None = None,
    trace_id: str = "synthetic-trace",
    reason: str | None = "synthetic reason",
    source: str = "api",
    before_payload: dict | None = None,
    after_payload: dict | None = None,
) -> AuditLog:
    return AuditLog(
        occurred_at=occurred_at,
        actor_id=actor_id,
        trace_id=trace_id,
        action=action,
        object_type=object_type,
        object_id=object_id if object_id is not None else uuid4(),
        reason=reason,
        before_payload=before_payload if before_payload is not None else {},
        after_payload=after_payload if after_payload is not None else {},
        source=source,
    )


def _csv_rows(response_content: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(StringIO(response_content.decode("utf-8-sig"))))


async def _seed_permission_token(
    db_session: AsyncSession,
    *,
    username: str,
    role_code: str,
    permission_code: str,
    raw_token: str,
) -> str:
    """按指定权限码造一个可登录账号，用于验证按权限码分级的访问控制。

    与 tests/integration/conftest.py 的 _seed_access_token 同一形状，
    区别是这里可以任意指定权限码与角色编码。
    """
    now = datetime.now(UTC)
    permission = await db_session.scalar(
        select(Permission).where(Permission.code == permission_code)
    )
    if permission is None:
        permission = Permission(
            code=permission_code,
            name=f"Synthetic {permission_code}",
            module_code="TEST",
        )
        db_session.add(permission)
    role = await db_session.scalar(select(Role).where(Role.code == role_code))
    if role is None:
        role = Role(
            code=role_code,
            name=f"Synthetic {role_code}",
            is_system=False,
            is_active=True,
        )
    user = UserAccount(
        username=username,
        display_name=f"Synthetic {username}",
        password_hash=hash_password("synthetic-test-password"),
        status="active",
        failed_attempts=0,
    )
    db_session.add_all([role, user])
    await db_session.flush()
    db_session.add_all(
        [
            UserRole(user_id=user.id, role_id=role.id),
            UserSession(
                user_id=user.id,
                token_hash=token_digest(raw_token),
                expires_at=now + timedelta(hours=1),
                last_seen_at=now,
            ),
            RolePermission(role_id=role.id, permission_id=permission.id),
        ]
    )
    await db_session.flush()
    return raw_token


async def test_audit_logs_are_paginated_and_ordered_newest_first(
    audit_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    base = datetime(2026, 1, 10, 8, 0, tzinfo=UTC)
    db_session.add_all(
        [
            _audit_log(occurred_at=base),
            _audit_log(occurred_at=base + timedelta(minutes=1)),
            _audit_log(occurred_at=base + timedelta(minutes=2)),
        ]
    )
    await db_session.flush()

    response = await audit_client.get(
        _AUDIT_LIST_PATH,
        headers=_headers(admin_token),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 20
    occurred = [datetime.fromisoformat(item["occurred_at"]) for item in body["items"]]
    assert occurred == sorted(occurred, reverse=True)

    first_page = await audit_client.get(
        f"{_AUDIT_LIST_PATH}?page=1&page_size=2",
        headers=_headers(admin_token),
    )
    assert first_page.status_code == 200, first_page.text
    assert first_page.json()["total"] == 3
    assert len(first_page.json()["items"]) == 2

    second_page = await audit_client.get(
        f"{_AUDIT_LIST_PATH}?page=2&page_size=2",
        headers=_headers(admin_token),
    )
    assert second_page.status_code == 200, second_page.text
    assert len(second_page.json()["items"]) == 1


async def test_audit_logs_page_size_over_limit_is_rejected(
    audit_client: AsyncClient,
    admin_token: str,
) -> None:
    response = await audit_client.get(
        f"{_AUDIT_LIST_PATH}?page_size=201",
        headers=_headers(admin_token),
    )
    assert response.status_code == 422, response.text


async def test_audit_logs_time_range_filter_is_closed_interval(
    audit_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    base = datetime(2026, 2, 1, 0, 0, tzinfo=UTC)
    db_session.add_all(
        [
            _audit_log(occurred_at=base),
            _audit_log(occurred_at=base + timedelta(hours=1)),
            _audit_log(occurred_at=base + timedelta(hours=2)),
        ]
    )
    await db_session.flush()

    response = await audit_client.get(
        _AUDIT_LIST_PATH,
        params={
            "occurred_from": base.isoformat(),
            "occurred_to": (base + timedelta(hours=1)).isoformat(),
        },
        headers=_headers(admin_token),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2
    occurred = {datetime.fromisoformat(item["occurred_at"]) for item in body["items"]}
    assert occurred == {base, base + timedelta(hours=1)}


async def test_audit_logs_reject_reversed_time_range(
    audit_client: AsyncClient,
    admin_token: str,
) -> None:
    base = datetime(2026, 2, 1, 0, 0, tzinfo=UTC)
    response = await audit_client.get(
        _AUDIT_LIST_PATH,
        params={
            "occurred_from": (base + timedelta(hours=2)).isoformat(),
            "occurred_to": base.isoformat(),
        },
        headers=_headers(admin_token),
    )

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "AUDIT_TIME_RANGE_INVALID"


async def test_audit_logs_filter_by_action_and_object_type(
    audit_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    base = datetime(2026, 3, 1, 0, 0, tzinfo=UTC)
    db_session.add_all(
        [
            _audit_log(occurred_at=base, action="person.update", object_type="person"),
            _audit_log(
                occurred_at=base + timedelta(minutes=1),
                action="organization.update",
                object_type="organization",
            ),
        ]
    )
    await db_session.flush()

    response = await audit_client.get(
        _AUDIT_LIST_PATH,
        params={"action": "person.update", "object_type": "person"},
        headers=_headers(admin_token),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["action"] == "person.update"
    assert body["items"][0]["object_type"] == "person"


async def test_audit_log_actions_are_aggregated_by_count(
    audit_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    base = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
    db_session.add_all(
        [
            _audit_log(occurred_at=base, action="person.update"),
            _audit_log(occurred_at=base + timedelta(minutes=1), action="person.update"),
            _audit_log(occurred_at=base + timedelta(minutes=2), action="person.create"),
            _audit_log(occurred_at=base + timedelta(minutes=3), action="governance.export"),
        ]
    )
    await db_session.flush()

    response = await audit_client.get(
        f"{_AUDIT_LIST_PATH}/actions",
        headers=_headers(admin_token),
    )

    assert response.status_code == 200, response.text
    assert response.json()["items"] == [
        {"code": "person.update", "count": 2},
        {"code": "governance.export", "count": 1},
        {"code": "person.create", "count": 1},
    ]


async def test_audit_logs_export_csv_has_fixed_columns_and_hides_payloads(
    audit_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    base = datetime(2026, 5, 1, 9, 30, tzinfo=UTC)
    db_session.add_all(
        [
            _audit_log(
                occurred_at=base,
                action="person.update",
                object_type="person",
                trace_id="trace-export-1",
                reason="synthetic export reason",
                source="api",
                before_payload={"salary": "sensitive-marker"},
                after_payload={"salary": "sensitive-marker"},
            ),
            _audit_log(
                occurred_at=base + timedelta(minutes=5),
                action="person.create",
                object_type="person",
                trace_id="trace-export-2",
            ),
        ]
    )
    await db_session.flush()

    response = await audit_client.get(
        f"{_AUDIT_LIST_PATH}/export",
        headers=_headers(admin_token),
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    assert "audit-logs.csv" in response.headers["content-disposition"]

    text = response.content.decode("utf-8-sig")
    reader = csv.reader(StringIO(text))
    assert next(reader) == _CSV_COLUMNS
    rows = _csv_rows(response.content)
    assert len(rows) == 2
    assert rows[0]["action"] == "person.create"
    assert rows[0]["trace_id"] == "trace-export-2"
    assert rows[1]["action"] == "person.update"
    assert rows[1]["trace_id"] == "trace-export-1"
    assert rows[1]["reason"] == "synthetic export reason"
    assert rows[1]["actor_name"] == ""
    assert rows[1]["occurred_at"].startswith("2026-05-01T09:30:00")

    # Requirement: AUDIT-007 — 导出内容不包含 payload，也不包含其字段名。
    assert "before_payload" not in text
    assert "after_payload" not in text
    assert "sensitive-marker" not in text


async def test_audit_logs_export_is_audited(
    audit_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    db_session.add(
        _audit_log(occurred_at=datetime(2026, 5, 2, 9, 30, tzinfo=UTC))
    )
    await db_session.flush()

    response = await audit_client.get(
        f"{_AUDIT_LIST_PATH}/export",
        headers=_headers(admin_token),
    )
    assert response.status_code == 200, response.text

    audit = await db_session.scalar(
        select(AuditLog).where(AuditLog.action == "platform.audit_logs.export")
    )
    assert audit is not None
    assert audit.before_payload == {}
    assert audit.after_payload["row_count"] == 1


async def test_audit_log_list_does_not_expose_payloads(
    audit_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    db_session.add(
        _audit_log(
            occurred_at=datetime(2026, 6, 1, 0, 0, tzinfo=UTC),
            before_payload={"salary": "sensitive-marker"},
            after_payload={"salary": "sensitive-marker"},
        )
    )
    await db_session.flush()

    response = await audit_client.get(
        _AUDIT_LIST_PATH,
        headers=_headers(admin_token),
    )

    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert "before_payload" not in item
    assert "after_payload" not in item
    assert "sensitive-marker" not in response.text


async def test_audit_log_detail_returns_payloads_for_admin(
    audit_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    record = _audit_log(
        occurred_at=datetime(2026, 7, 1, 0, 0, tzinfo=UTC),
        before_payload={"salary": "100"},
        after_payload={"salary": "200"},
    )
    db_session.add(record)
    await db_session.flush()

    response = await audit_client.get(
        f"{_AUDIT_LIST_PATH}/{record.id}",
        headers=_headers(admin_token),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["before_payload"] == {"salary": "100"}
    assert body["after_payload"] == {"salary": "200"}


async def test_audit_log_detail_returns_not_found_for_unknown_id(
    audit_client: AsyncClient,
    admin_token: str,
) -> None:
    response = await audit_client.get(
        f"{_AUDIT_LIST_PATH}/{uuid4()}",
        headers=_headers(admin_token),
    )
    assert response.status_code == 404, response.text
    assert response.json()["code"] == "AUDIT_LOG_NOT_FOUND"


async def test_audit_log_actor_name_comes_from_user_account(
    audit_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    actor = await db_session.scalar(
        select(UserAccount).where(UserAccount.username == "synthetic-admin")
    )
    assert actor is not None
    base = datetime(2026, 8, 1, 0, 0, tzinfo=UTC)
    db_session.add_all(
        [
            _audit_log(occurred_at=base, actor_id=actor.id),
            _audit_log(occurred_at=base + timedelta(minutes=1), actor_id=uuid4()),
        ]
    )
    await db_session.flush()

    response = await audit_client.get(
        _AUDIT_LIST_PATH,
        headers=_headers(admin_token),
    )

    assert response.status_code == 200, response.text
    items = response.json()["items"]
    named = next(item for item in items if item["actor_id"] == str(actor.id))
    anonymous = next(item for item in items if item["actor_id"] != str(actor.id))
    assert named["actor_name"] == actor.display_name
    assert anonymous["actor_name"] is None


async def test_audit_log_endpoints_require_data_governance_admin(
    audit_client: AsyncClient,
    restricted_token: str,
) -> None:
    paths = [
        _AUDIT_LIST_PATH,
        f"{_AUDIT_LIST_PATH}/actions",
        f"{_AUDIT_LIST_PATH}/export",
        f"{_AUDIT_LIST_PATH}/{uuid4()}",
    ]
    for path in paths:
        response = await audit_client.get(
            path,
            headers=_headers(restricted_token),
        )
        assert response.status_code == 403, f"{path} -> {response.text}"
        assert response.json()["code"] == "PERMISSION_DENIED"


async def test_audit_actors_are_available_to_data_governance_admin(
    audit_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # Requirement: P-13 — 治理管理员用 DATA_GOVERNANCE_ADMIN 就能取到操作人下拉，
    # 不再依赖权限码为 `*` 的 /api/v1/platform/users。
    token = await _seed_permission_token(
        db_session,
        username="synthetic-governance-admin",
        role_code="SYNTHETIC_GOVERNANCE_ADMIN",
        permission_code="DATA_GOVERNANCE_ADMIN",
        raw_token="synthetic-governance-admin-token",
    )

    response = await audit_client.get(
        _AUDIT_ACTORS_PATH,
        headers=_headers(token),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == len(body["items"])
    assert body["items"], "至少要返回当前会话管理员自己"


async def test_audit_actors_are_available_to_read_only_governance_role(
    audit_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # Requirement: P-13 — 只读治理角色持有 DATA_GOVERNANCE_VIEW 即可读取下拉数据源。
    token = await _seed_permission_token(
        db_session,
        username="synthetic-governance-viewer",
        role_code="SYNTHETIC_GOVERNANCE_VIEWER",
        permission_code="DATA_GOVERNANCE_VIEW",
        raw_token="synthetic-governance-viewer-token",
    )

    response = await audit_client.get(
        _AUDIT_ACTORS_PATH,
        headers=_headers(token),
    )

    assert response.status_code == 200, response.text
    assert "items" in response.json()


async def test_audit_actors_require_a_governance_permission(
    audit_client: AsyncClient,
    restricted_token: str,
) -> None:
    # Requirement: P-13 — 没有任何治理权限的账号一律 403，不返回任何账号信息。
    response = await audit_client.get(
        _AUDIT_ACTORS_PATH,
        headers=_headers(restricted_token),
    )

    assert response.status_code == 403, response.text
    assert response.json()["code"] == "PERMISSION_DENIED"


async def test_audit_actors_expose_only_minimal_fields_and_sort_by_display_name(
    audit_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    # Requirement: P-13 — 响应只含 id、display_name、username；
    # 不返回邮箱、手机号等个人联系方式，也不返回账号状态与角色。
    db_session.add_all(
        [
            UserAccount(
                username="actor-zeta",
                display_name="丙",
                password_hash=hash_password("synthetic-test-password"),
                status="active",
                failed_attempts=0,
            ),
            UserAccount(
                username="actor-alpha",
                display_name="甲",
                password_hash=hash_password("synthetic-test-password"),
                status="active",
                failed_attempts=0,
            ),
        ]
    )
    await db_session.flush()

    response = await audit_client.get(
        _AUDIT_ACTORS_PATH,
        headers=_headers(admin_token),
    )

    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert items, "账号清单不能为空"
    for item in items:
        assert set(item.keys()) == {"id", "display_name", "username"}
    display_names = [item["display_name"] for item in items]
    assert display_names == sorted(display_names), "必须按 display_name 升序"
