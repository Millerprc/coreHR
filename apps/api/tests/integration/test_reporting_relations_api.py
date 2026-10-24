# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.business_main import create_business_app
from hris.core.database import get_db
from hris.modules.platform.models import (
    Permission,
    Role,
    RolePermission,
    UserAccount,
    UserRole,
    UserSession,
)
from hris.modules.platform.security import hash_password, token_digest
from hris.modules.workforce.models import Person, ReportingRelation
from hris.modules.workforce.reporting_api import router as reporting_router


REPORTING_PATH = "/api/v1/workforce/reporting-relations"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _business_date() -> date:
    return datetime.now(ZoneInfo("Asia/Shanghai")).date()


async def _seed_permission_token(
    db_session: AsyncSession,
    *,
    username: str,
    role_code: str,
    permission_code: str,
    raw_token: str,
) -> str:
    """按指定权限码造一个可登录账号，用于验证读写权限分级。

    与 tests/integration/conftest.py 的 _seed_access_token 同一形状，
    区别是这里可以任意指定权限码与角色编码。
    """
    now = datetime.now(ZoneInfo("UTC"))
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


@pytest_asyncio.fixture
async def reporting_client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """构造包含汇报关系路由的测试客户端。

    路由尚未在业务路由总入口注册时，测试直接挂载，避免依赖路由注册顺序。
    """
    app = create_business_app()
    if not any(
        getattr(route, "path", None) == REPORTING_PATH for route in app.routes
    ):
        app.include_router(reporting_router)

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


async def _seed_people(db_session: AsyncSession, count: int) -> list[Person]:
    people = [
        Person(
            legal_name=f"合成汇报人员{index}",
            display_name=f"合成汇报人员{index}",
            status="active",
        )
        for index in range(1, count + 1)
    ]
    db_session.add_all(people)
    await db_session.flush()
    return people


async def _create_relation(
    client: AsyncClient,
    token: str,
    *,
    manager_id: str,
    subordinate_id: str,
    relation_type: str = "direct",
    effective_from: str,
    effective_to: str | None = None,
) -> AsyncClient:
    payload: dict[str, object] = {
        "manager_person_id": manager_id,
        "subordinate_person_id": subordinate_id,
        "relation_type": relation_type,
        "effective_from": effective_from,
    }
    if effective_to is not None:
        payload["effective_to"] = effective_to
    return await client.post(
        REPORTING_PATH,
        headers=_auth(token),
        json=payload,
    )


async def test_reporting_relation_can_be_created_listed_and_filtered(
    reporting_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    today = _business_date()
    people = await _seed_people(db_session, 4)

    created = await _create_relation(
        reporting_client,
        admin_token,
        manager_id=str(people[0].id),
        subordinate_id=str(people[1].id),
        effective_from=today.isoformat(),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["manager_person_id"] == str(people[0].id)
    assert body["manager_name"] == people[0].display_name
    assert body["subordinate_person_id"] == str(people[1].id)
    assert body["subordinate_name"] == people[1].display_name
    assert body["relation_type"] == "direct"
    assert body["effective_from"] == today.isoformat()
    assert body["effective_to"] is None

    listed = await reporting_client.get(REPORTING_PATH, headers=_auth(admin_token))
    assert listed.status_code == 200, listed.text
    page = listed.json()
    assert page["total"] == 1
    assert page["page"] == 1
    assert page["page_size"] == 20
    assert [item["id"] for item in page["items"]] == [body["id"]]

    by_manager = await reporting_client.get(
        f"{REPORTING_PATH}?manager_person_id={people[0].id}",
        headers=_auth(admin_token),
    )
    assert by_manager.status_code == 200
    assert by_manager.json()["total"] == 1

    by_subordinate = await reporting_client.get(
        f"{REPORTING_PATH}?subordinate_person_id={people[1].id}",
        headers=_auth(admin_token),
    )
    assert by_subordinate.json()["total"] == 1

    unmatched = await reporting_client.get(
        f"{REPORTING_PATH}?manager_person_id={people[3].id}",
        headers=_auth(admin_token),
    )
    assert unmatched.json()["total"] == 0
    assert unmatched.json()["items"] == []


async def test_reporting_relation_pagination_is_applied(
    reporting_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    today = _business_date()
    people = await _seed_people(db_session, 3)

    for subordinate in people[1:]:
        response = await _create_relation(
            reporting_client,
            admin_token,
            manager_id=str(people[0].id),
            subordinate_id=str(subordinate.id),
            effective_from=today.isoformat(),
        )
        assert response.status_code == 201, response.text

    first_page = await reporting_client.get(
        f"{REPORTING_PATH}?page=1&page_size=2",
        headers=_auth(admin_token),
    )
    assert first_page.status_code == 200
    payload = first_page.json()
    assert payload["total"] == 2
    assert payload["page"] == 1
    assert payload["page_size"] == 2
    assert len(payload["items"]) == 2

    second_page = await reporting_client.get(
        f"{REPORTING_PATH}?page=2&page_size=2",
        headers=_auth(admin_token),
    )
    assert second_page.json()["total"] == 2
    assert len(second_page.json()["items"]) == 0


async def test_direct_reporting_cycle_is_rejected(
    reporting_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    today = _business_date()
    people = await _seed_people(db_session, 3)

    first = await _create_relation(
        reporting_client,
        admin_token,
        manager_id=str(people[0].id),
        subordinate_id=str(people[1].id),
        effective_from=today.isoformat(),
    )
    assert first.status_code == 201, first.text

    cycle = await _create_relation(
        reporting_client,
        admin_token,
        manager_id=str(people[1].id),
        subordinate_id=str(people[0].id),
        effective_from=today.isoformat(),
    )
    assert cycle.status_code == 422, cycle.text
    assert cycle.json()["code"] == "REPORTING_CYCLE_DETECTED"

    # 实线：people[2] 是 people[0] 的实线上级。
    solid_chain = await _create_relation(
        reporting_client,
        admin_token,
        manager_id=str(people[2].id),
        subordinate_id=str(people[0].id),
        effective_from=today.isoformat(),
    )
    assert solid_chain.status_code == 201, solid_chain.text

    # 虚线指向自己的实线上级是矩阵汇报（虚线实线并存）的合法场景，不是环，必须放行。
    dotted_to_solid_manager = await _create_relation(
        reporting_client,
        admin_token,
        manager_id=str(people[0].id),
        subordinate_id=str(people[2].id),
        relation_type="dotted",
        effective_from=today.isoformat(),
    )
    assert dotted_to_solid_manager.status_code == 201, dotted_to_solid_manager.text

    # 虚线自身成环仍然必须拒绝。
    dotted_cycle = await _create_relation(
        reporting_client,
        admin_token,
        manager_id=str(people[2].id),
        subordinate_id=str(people[0].id),
        relation_type="dotted",
        effective_from=today.isoformat(),
    )
    assert dotted_cycle.status_code == 422, dotted_cycle.text
    assert dotted_cycle.json()["code"] == "REPORTING_CYCLE_DETECTED"


async def test_duplicate_reporting_relation_is_conflict(
    reporting_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    today = _business_date()
    people = await _seed_people(db_session, 2)

    first = await _create_relation(
        reporting_client,
        admin_token,
        manager_id=str(people[0].id),
        subordinate_id=str(people[1].id),
        effective_from=today.isoformat(),
    )
    assert first.status_code == 201, first.text

    duplicated = await _create_relation(
        reporting_client,
        admin_token,
        manager_id=str(people[0].id),
        subordinate_id=str(people[1].id),
        effective_from=today.isoformat(),
    )
    assert duplicated.status_code == 409, duplicated.text
    assert duplicated.json()["code"] == "REPORTING_RELATION_DUPLICATE"


async def test_reporting_relation_can_be_soft_ended(
    reporting_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    today = _business_date()
    people = await _seed_people(db_session, 2)

    created = await _create_relation(
        reporting_client,
        admin_token,
        manager_id=str(people[0].id),
        subordinate_id=str(people[1].id),
        effective_from=today.isoformat(),
    )
    assert created.status_code == 201, created.text
    relation_id = created.json()["id"]

    ended = await reporting_client.delete(
        f"{REPORTING_PATH}/{relation_id}",
        headers=_auth(admin_token),
    )
    assert ended.status_code == 204, ended.text
    assert ended.content == b""

    stored = await db_session.scalar(
        select(ReportingRelation).where(ReportingRelation.id == relation_id)
    )
    assert stored is not None
    assert stored.effective_to == today

    repeated = await reporting_client.delete(
        f"{REPORTING_PATH}/{relation_id}",
        headers=_auth(admin_token),
    )
    assert repeated.status_code == 409, repeated.text
    assert repeated.json()["code"] == "REPORTING_RELATION_ALREADY_ENDED"

    missing = await reporting_client.delete(
        f"{REPORTING_PATH}/00000000-0000-0000-0000-000000000000",
        headers=_auth(admin_token),
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "REPORTING_RELATION_NOT_FOUND"


async def test_future_reporting_relation_can_be_soft_ended(
    reporting_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    tomorrow = _business_date() + timedelta(days=1)
    people = await _seed_people(db_session, 2)

    created = await _create_relation(
        reporting_client,
        admin_token,
        manager_id=str(people[0].id),
        subordinate_id=str(people[1].id),
        effective_from=tomorrow.isoformat(),
    )
    assert created.status_code == 201, created.text

    ended = await reporting_client.delete(
        f"{REPORTING_PATH}/{created.json()['id']}",
        headers=_auth(admin_token),
    )
    assert ended.status_code == 204, ended.text

    stored = await db_session.scalar(
        select(ReportingRelation).where(
            ReportingRelation.id == created.json()["id"]
        )
    )
    assert stored is not None
    # 尚未生效的关系以生效开始日作为结束日期，保证结束日期不早于开始日期。
    assert stored.effective_to == tomorrow


async def test_reporting_relation_effective_at_filter(
    reporting_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    today = _business_date()
    tomorrow = today + timedelta(days=1)
    people = await _seed_people(db_session, 3)

    current = await _create_relation(
        reporting_client,
        admin_token,
        manager_id=str(people[0].id),
        subordinate_id=str(people[1].id),
        effective_from=today.isoformat(),
        effective_to=tomorrow.isoformat(),
    )
    assert current.status_code == 201, current.text

    future = await _create_relation(
        reporting_client,
        admin_token,
        manager_id=str(people[0].id),
        subordinate_id=str(people[2].id),
        effective_from=tomorrow.isoformat(),
    )
    assert future.status_code == 201, future.text

    at_today = await reporting_client.get(
        f"{REPORTING_PATH}?effective_at={today.isoformat()}",
        headers=_auth(admin_token),
    )
    assert at_today.status_code == 200
    assert [item["id"] for item in at_today.json()["items"]] == [current.json()["id"]]

    # 生效区间为左闭右开，结束日当天不再生效。
    at_tomorrow = await reporting_client.get(
        f"{REPORTING_PATH}?effective_at={tomorrow.isoformat()}",
        headers=_auth(admin_token),
    )
    assert [item["id"] for item in at_tomorrow.json()["items"]] == [future.json()["id"]]

    without_filter = await reporting_client.get(REPORTING_PATH, headers=_auth(admin_token))
    assert without_filter.json()["total"] == 2


async def test_reporting_relation_validation_errors(
    reporting_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    today = _business_date()
    people = await _seed_people(db_session, 2)

    invalid_type = await _create_relation(
        reporting_client,
        admin_token,
        manager_id=str(people[0].id),
        subordinate_id=str(people[1].id),
        relation_type="indirect",
        effective_from=today.isoformat(),
    )
    assert invalid_type.status_code == 422
    assert invalid_type.json()["code"] == "REPORTING_RELATION_TYPE_INVALID"

    self_reference = await _create_relation(
        reporting_client,
        admin_token,
        manager_id=str(people[0].id),
        subordinate_id=str(people[0].id),
        effective_from=today.isoformat(),
    )
    assert self_reference.status_code == 422
    assert self_reference.json()["code"] == "REPORTING_SELF_REFERENCE_INVALID"

    unknown_person = await _create_relation(
        reporting_client,
        admin_token,
        manager_id="00000000-0000-0000-0000-000000000000",
        subordinate_id=str(people[1].id),
        effective_from=today.isoformat(),
    )
    assert unknown_person.status_code == 422
    assert unknown_person.json()["code"] == "REPORTING_PERSON_NOT_FOUND"

    invalid_period = await _create_relation(
        reporting_client,
        admin_token,
        manager_id=str(people[0].id),
        subordinate_id=str(people[1].id),
        effective_from=today.isoformat(),
        effective_to=(today - timedelta(days=1)).isoformat(),
    )
    assert invalid_period.status_code == 422
    assert invalid_period.json()["code"] == "REPORTING_PERIOD_INVALID"


async def test_reporting_relation_read_is_open_to_organization_viewers(
    reporting_client: AsyncClient,
    admin_token: str,
    restricted_token: str,
    db_session: AsyncSession,
) -> None:
    # Requirement: P-14 — 读端点放宽到 ORGANIZATION_VIEW：
    # 只读账号可以查询汇报关系列表。
    today = _business_date()
    people = await _seed_people(db_session, 2)
    created = await _create_relation(
        reporting_client,
        admin_token,
        manager_id=str(people[0].id),
        subordinate_id=str(people[1].id),
        effective_from=today.isoformat(),
    )
    assert created.status_code == 201, created.text

    listed = await reporting_client.get(REPORTING_PATH, headers=_auth(restricted_token))
    assert listed.status_code == 200, listed.text
    page = listed.json()
    assert page["total"] == 1
    assert [item["id"] for item in page["items"]] == [created.json()["id"]]

    by_manager = await reporting_client.get(
        f"{REPORTING_PATH}?manager_person_id={people[0].id}",
        headers=_auth(restricted_token),
    )
    assert by_manager.status_code == 200
    assert by_manager.json()["total"] == 1


async def test_reporting_relation_write_still_requires_workforce_admin(
    reporting_client: AsyncClient,
    restricted_token: str,
    db_session: AsyncSession,
) -> None:
    # Requirement: P-14 — 写端点权限不放宽：
    # 只读账号新增汇报关系与结束汇报关系都必须是 403。
    today = _business_date()
    people = await _seed_people(db_session, 2)

    created = await _create_relation(
        reporting_client,
        restricted_token,
        manager_id=str(people[0].id),
        subordinate_id=str(people[1].id),
        effective_from=today.isoformat(),
    )
    assert created.status_code == 403
    assert created.json()["code"] == "PERMISSION_DENIED"

    ended = await reporting_client.delete(
        f"{REPORTING_PATH}/00000000-0000-0000-0000-000000000000",
        headers=_auth(restricted_token),
    )
    assert ended.status_code == 403
    assert ended.json()["code"] == "PERMISSION_DENIED"


async def test_reporting_relation_workforce_admin_keeps_read_and_write(
    reporting_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # Requirement: P-14 — 读权限放宽是并集语义：
    # 只持 WORKFORCE_ADMIN 的角色（编制管理员、SSC 管理员）不能因为放宽而失去读取能力。
    token = await _seed_permission_token(
        db_session,
        username="synthetic-workforce-admin",
        role_code="SYNTHETIC_WORKFORCE_ADMIN",
        permission_code="WORKFORCE_ADMIN",
        raw_token="synthetic-workforce-admin-token",
    )
    today = _business_date()
    people = await _seed_people(db_session, 2)

    created = await _create_relation(
        reporting_client,
        token,
        manager_id=str(people[0].id),
        subordinate_id=str(people[1].id),
        effective_from=today.isoformat(),
    )
    assert created.status_code == 201, created.text

    listed = await reporting_client.get(REPORTING_PATH, headers=_auth(token))
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1

    ended = await reporting_client.delete(
        f"{REPORTING_PATH}/{created.json()['id']}",
        headers=_auth(token),
    )
    assert ended.status_code == 204, ended.text
