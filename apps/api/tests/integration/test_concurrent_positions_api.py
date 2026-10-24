# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""人员级兼岗（concurrent position）集成测试。

Requirement: D-104 — 兼岗以人员级组织关系（organization_person_relations）为唯一权威载体，
本文件覆盖：新建、查询、结束、唯一性校验、时点过滤、读写权限分级。
Requirement: D-026 — 同一时间只能有一个主组织，兼岗可以同时存在多个。
"""

from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.business_main import create_business_app
from hris.core.database import get_db
from hris.core.errors import ApiError
from hris.modules.workforce.concurrent_positions_api import router as concurrent_positions_router
from hris.modules.workforce.concurrent_positions_service import ConcurrentPositionService
from hris.modules.workforce.models import (
    Employment,
    EmploymentAssignment,
    JobCatalog,
    Organization,
    OrganizationPersonRelation,
    OrganizationType,
    OrganizationVersion,
    Person,
)


CONCURRENT_PATH = "/api/v1/workforce/concurrent-positions"
PERSON_CONCURRENT_PATH = "/api/v1/workforce/persons/{person_id}/concurrent-positions"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _business_date() -> date:
    return datetime.now(ZoneInfo("Asia/Shanghai")).date()


@pytest_asyncio.fixture
async def concurrent_client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """构造包含兼岗路由的测试客户端。

    路由已在业务路由总入口注册时直接使用；未注册时兜底挂载，避免依赖注册顺序。
    """
    app = create_business_app()
    if not any(
        getattr(route, "path", None) == CONCURRENT_PATH for route in app.routes
    ):
        app.include_router(concurrent_positions_router)

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


async def _seed_person(db_session: AsyncSession, label: str) -> Person:
    person = Person(
        legal_name=f"合成兼岗人员{label}",
        display_name=f"合成兼岗人员{label}",
        status="active",
    )
    db_session.add(person)
    await db_session.flush()
    return person


async def _seed_organization(
    db_session: AsyncSession,
    code: str,
    name: str,
) -> Organization:
    organization_type = await db_session.scalar(
        select(OrganizationType).where(OrganizationType.code == "SYNTHETIC_UNIT")
    )
    if organization_type is None:
        organization_type = OrganizationType(
            code="SYNTHETIC_UNIT",
            name="合成部门类型",
            sort_order=99,
            is_active=True,
        )
        db_session.add(organization_type)
        await db_session.flush()
    organization = Organization(code=code)
    db_session.add(organization)
    await db_session.flush()
    db_session.add(
        OrganizationVersion(
            organization_id=organization.id,
            version=1,
            name=name,
            organization_type_id=organization_type.id,
            country_code="CN",
            status="active",
            effective_from=date(2020, 1, 1),
            effective_to=None,
            is_current=True,
            change_reason="合成组织",
        )
    )
    await db_session.flush()
    return organization


async def _seed_job(db_session: AsyncSession, code: str, name: str) -> JobCatalog:
    job = JobCatalog(
        code=code,
        name=name,
        status="active",
        effective_from=date(2020, 1, 1),
        effective_to=None,
    )
    db_session.add(job)
    await db_session.flush()
    return job


async def _create_concurrent_position(
    client: AsyncClient,
    token: str,
    *,
    person_id: str,
    organization_id: str,
    job_id: str | None = None,
    effective_from: str,
    effective_to: str | None = None,
    change_reason: str = "合成兼岗",
) -> AsyncClient:
    payload: dict[str, object] = {
        "person_id": person_id,
        "organization_id": organization_id,
        "effective_from": effective_from,
        "change_reason": change_reason,
    }
    if job_id is not None:
        payload["job_id"] = job_id
    if effective_to is not None:
        payload["effective_to"] = effective_to
    return await client.post(CONCURRENT_PATH, headers=_auth(token), json=payload)


def _service(db_session: AsyncSession) -> ConcurrentPositionService:
    return ConcurrentPositionService(
        db_session,
        actor_id=uuid4(),
        trace_id="synthetic-trace",
    )


async def test_concurrent_position_is_written_to_person_level_relation(
    concurrent_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """Requirement: D-104 — 兼岗写人员级组织关系，不再写 employment 级任职。"""
    today = _business_date()
    person = await _seed_person(db_session, "A")
    organization = await _seed_organization(db_session, "SYN_ORG_A", "合成部门甲")
    job = await _seed_job(db_session, "SYN_JOB_A", "合成职务甲")

    created = await _create_concurrent_position(
        concurrent_client,
        admin_token,
        person_id=str(person.id),
        organization_id=str(organization.id),
        job_id=str(job.id),
        effective_from=today.isoformat(),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["person_id"] == str(person.id)
    assert body["person_name"] == person.display_name
    assert body["organization_id"] == str(organization.id)
    assert body["organization_name"] == "合成部门甲"
    assert body["job_id"] == str(job.id)
    assert body["job_name"] == "合成职务甲"
    assert body["relation_type"] == "concurrent"
    assert body["effective_from"] == today.isoformat()
    assert body["effective_to"] is None
    assert body["change_reason"] == "合成兼岗"

    relations = (
        await db_session.execute(
            select(OrganizationPersonRelation).where(
                OrganizationPersonRelation.person_id == person.id,
                OrganizationPersonRelation.relation_type == "concurrent",
            )
        )
    ).scalars().all()
    assert len(relations) == 1
    assert relations[0].organization_id == organization.id

    assignments = (
        await db_session.execute(
            select(EmploymentAssignment).where(
                EmploymentAssignment.organization_id == organization.id,
            )
        )
    ).scalars().all()
    assert assignments == [], "兼岗不得落到 employment 级任职表"


async def test_concurrent_position_can_be_queried_by_list_and_by_person(
    concurrent_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    today = _business_date()
    person = await _seed_person(db_session, "B")
    other = await _seed_person(db_session, "C")
    organization = await _seed_organization(db_session, "SYN_ORG_B", "合成部门乙")

    created = await _create_concurrent_position(
        concurrent_client,
        admin_token,
        person_id=str(person.id),
        organization_id=str(organization.id),
        effective_from=today.isoformat(),
    )
    assert created.status_code == 201, created.text
    body = created.json()

    listed = await concurrent_client.get(CONCURRENT_PATH, headers=_auth(admin_token))
    assert listed.status_code == 200, listed.text
    page = listed.json()
    assert page["total"] == 1
    assert [item["id"] for item in page["items"]] == [body["id"]]

    by_person = await concurrent_client.get(
        f"{CONCURRENT_PATH}?person_id={person.id}",
        headers=_auth(admin_token),
    )
    assert by_person.status_code == 200
    assert by_person.json()["total"] == 1

    unmatched = await concurrent_client.get(
        f"{CONCURRENT_PATH}?person_id={other.id}",
        headers=_auth(admin_token),
    )
    assert unmatched.json()["total"] == 0

    person_view = await concurrent_client.get(
        PERSON_CONCURRENT_PATH.format(person_id=person.id),
        headers=_auth(admin_token),
    )
    assert person_view.status_code == 200, person_view.text
    assert [item["id"] for item in person_view.json()] == [body["id"]]


async def test_ending_concurrent_position_closes_the_period(
    concurrent_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """Requirement: D-104 — 结束兼岗只关闭生效区间，历史记录保留。"""
    today = _business_date()
    person = await _seed_person(db_session, "D")
    organization = await _seed_organization(db_session, "SYN_ORG_C", "合成部门丙")

    created = await _create_concurrent_position(
        concurrent_client,
        admin_token,
        person_id=str(person.id),
        organization_id=str(organization.id),
        effective_from=today.isoformat(),
    )
    assert created.status_code == 201, created.text
    relation_id = created.json()["id"]

    ended = await concurrent_client.delete(
        f"{CONCURRENT_PATH}/{relation_id}",
        headers=_auth(admin_token),
    )
    assert ended.status_code == 204, ended.text

    relation = await db_session.get(OrganizationPersonRelation, relation_id)
    assert relation is not None
    assert relation.effective_to == today

    # 历史行仍在列表里，但按今日过滤已不再命中。
    listed = await concurrent_client.get(CONCURRENT_PATH, headers=_auth(admin_token))
    assert listed.json()["total"] == 1
    effective_today = await concurrent_client.get(
        f"{CONCURRENT_PATH}?effective_at={today.isoformat()}",
        headers=_auth(admin_token),
    )
    assert effective_today.json()["total"] == 0

    # 重复结束要报错，不能静默改写历史。
    again = await concurrent_client.delete(
        f"{CONCURRENT_PATH}/{relation_id}",
        headers=_auth(admin_token),
    )
    assert again.status_code == 409, again.text
    assert again.json()["code"] == "CONCURRENT_POSITION_ALREADY_ENDED"


async def test_duplicate_concurrent_position_in_same_organization_is_rejected(
    concurrent_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """Requirement: D-104 / D-026 — 同组织重复兼岗被挡住。"""
    today = _business_date()
    person = await _seed_person(db_session, "E")
    organization = await _seed_organization(db_session, "SYN_ORG_D", "合成部门丁")

    first = await _create_concurrent_position(
        concurrent_client,
        admin_token,
        person_id=str(person.id),
        organization_id=str(organization.id),
        effective_from=today.isoformat(),
    )
    assert first.status_code == 201, first.text

    duplicate = await _create_concurrent_position(
        concurrent_client,
        admin_token,
        person_id=str(person.id),
        organization_id=str(organization.id),
        effective_from=today.isoformat(),
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["code"] == "CONCURRENT_POSITION_DUPLICATE"
    assert duplicate.json()["message"] == "该人员在同一组织已存在生效区间重叠的兼岗"

    # 区间重叠（起点落在既有区间内）同样被挡住。
    overlapping = await _create_concurrent_position(
        concurrent_client,
        admin_token,
        person_id=str(person.id),
        organization_id=str(organization.id),
        effective_from=(today + timedelta(days=30)).isoformat(),
        effective_to=(today + timedelta(days=60)).isoformat(),
    )
    assert overlapping.status_code == 409, overlapping.text
    assert overlapping.json()["code"] == "CONCURRENT_POSITION_DUPLICATE"


async def test_person_can_hold_concurrent_positions_in_different_organizations(
    concurrent_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """Requirement: D-026 — 兼岗可以同时存在多个。"""
    today = _business_date()
    person = await _seed_person(db_session, "F")
    first_org = await _seed_organization(db_session, "SYN_ORG_E", "合成部门戊")
    second_org = await _seed_organization(db_session, "SYN_ORG_F", "合成部门己")

    for organization in (first_org, second_org):
        created = await _create_concurrent_position(
            concurrent_client,
            admin_token,
            person_id=str(person.id),
            organization_id=str(organization.id),
            effective_from=today.isoformat(),
        )
        assert created.status_code == 201, created.text

    listed = await concurrent_client.get(
        f"{CONCURRENT_PATH}?person_id={person.id}",
        headers=_auth(admin_token),
    )
    assert listed.json()["total"] == 2


async def test_second_primary_organization_is_rejected(
    concurrent_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """Requirement: D-026 — 同一时间只能有一个主组织。"""
    today = _business_date()
    person = await _seed_person(db_session, "G")
    organization = await _seed_organization(db_session, "SYN_ORG_G", "合成部门庚")
    other_organization = await _seed_organization(db_session, "SYN_ORG_H", "合成部门辛")

    service = _service(db_session)
    first = await service.create_person_organization_relation(
        person_id=person.id,
        organization_id=organization.id,
        relation_type="primary",
        job_id=None,
        effective_from=today,
        effective_to=None,
        change_reason="合成主组织",
    )
    assert first.relation_type == "primary"

    with pytest.raises(ApiError) as conflict:
        await service.create_person_organization_relation(
            person_id=person.id,
            organization_id=other_organization.id,
            relation_type="primary",
            job_id=None,
            effective_from=today,
            effective_to=None,
            change_reason="合成第二个主组织",
        )
    assert conflict.value.status_code == 409
    assert conflict.value.code == "PRIMARY_ORGANIZATION_CONFLICT"
    assert conflict.value.message == "同一时间只能有一个主组织"


async def test_primary_organization_on_employment_level_blocks_person_level_primary(
    concurrent_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """Requirement: D-026 — 跨载体也只允许一个主组织。

    D-104 之后 employment 级任职保留为历史记录，但主组织语义仍要成立，
    因此既有 employment 级主组织会挡住人员级主组织。
    """
    today = _business_date()
    person = await _seed_person(db_session, "H")
    organization = await _seed_organization(db_session, "SYN_ORG_I", "合成部门壬")
    other_organization = await _seed_organization(db_session, "SYN_ORG_J", "合成部门癸")

    employment = Employment(
        person_id=person.id,
        employee_type_code="FULL_TIME",
        status="active",
        planned_start_date=today - timedelta(days=30),
    )
    db_session.add(employment)
    await db_session.flush()
    db_session.add(
        EmploymentAssignment(
            employment_id=employment.id,
            organization_id=organization.id,
            job_id=None,
            relation_type="primary",
            effective_from=today - timedelta(days=30),
            effective_to=None,
            version=1,
        )
    )
    await db_session.flush()

    service = _service(db_session)
    with pytest.raises(ApiError) as conflict:
        await service.create_person_organization_relation(
            person_id=person.id,
            organization_id=other_organization.id,
            relation_type="primary",
            job_id=None,
            effective_from=today,
            effective_to=None,
            change_reason="合成人员级主组织",
        )
    assert conflict.value.status_code == 409
    assert conflict.value.code == "PRIMARY_ORGANIZATION_CONFLICT"


async def test_effective_at_filter_matches_the_effective_interval(
    concurrent_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """生效日期之前、之内、之后的查询结果必须正确。"""
    today = _business_date()
    person = await _seed_person(db_session, "I")
    organization = await _seed_organization(db_session, "SYN_ORG_K", "合成部门子")

    start = today + timedelta(days=10)
    end = today + timedelta(days=40)
    created = await _create_concurrent_position(
        concurrent_client,
        admin_token,
        person_id=str(person.id),
        organization_id=str(organization.id),
        effective_from=start.isoformat(),
        effective_to=end.isoformat(),
    )
    assert created.status_code == 201, created.text

    before = await concurrent_client.get(
        f"{CONCURRENT_PATH}?effective_at={(today - timedelta(days=1)).isoformat()}",
        headers=_auth(admin_token),
    )
    assert before.json()["total"] == 0

    inside = await concurrent_client.get(
        f"{CONCURRENT_PATH}?effective_at={start.isoformat()}",
        headers=_auth(admin_token),
    )
    assert inside.json()["total"] == 1

    after = await concurrent_client.get(
        f"{CONCURRENT_PATH}?effective_at={end.isoformat()}",
        headers=_auth(admin_token),
    )
    assert after.json()["total"] == 0, "失效日期当天已不再有效"


async def test_invalid_payloads_are_rejected(
    concurrent_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    today = _business_date()
    person = await _seed_person(db_session, "J")
    organization = await _seed_organization(db_session, "SYN_ORG_L", "合成部门丑")

    invalid_period = await _create_concurrent_position(
        concurrent_client,
        admin_token,
        person_id=str(person.id),
        organization_id=str(organization.id),
        effective_from=today.isoformat(),
        effective_to=(today - timedelta(days=1)).isoformat(),
    )
    assert invalid_period.status_code == 422, invalid_period.text
    assert invalid_period.json()["code"] == "CONCURRENT_POSITION_PERIOD_INVALID"

    missing_reason = await concurrent_client.post(
        CONCURRENT_PATH,
        headers=_auth(admin_token),
        json={
            "person_id": str(person.id),
            "organization_id": str(organization.id),
            "effective_from": today.isoformat(),
        },
    )
    assert missing_reason.status_code == 422, missing_reason.text

    unknown_person = await _create_concurrent_position(
        concurrent_client,
        admin_token,
        person_id=str(uuid4()),
        organization_id=str(organization.id),
        effective_from=today.isoformat(),
    )
    assert unknown_person.status_code == 422, unknown_person.text
    assert unknown_person.json()["code"] == "CONCURRENT_POSITION_PERSON_NOT_FOUND"


async def test_source_event_id_makes_writes_idempotent(
    concurrent_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """Requirement: D-104 — HR 事件重试不得重复写兼岗。"""
    today = _business_date()
    person = await _seed_person(db_session, "K")
    organization = await _seed_organization(db_session, "SYN_ORG_M", "合成部门寅")
    event_id = uuid4()

    service = _service(db_session)
    first = await service.create_concurrent_position(
        person_id=person.id,
        organization_id=organization.id,
        job_id=None,
        effective_from=today,
        effective_to=None,
        change_reason="合成兼岗",
        source_event_id=event_id,
    )
    second = await service.create_concurrent_position(
        person_id=person.id,
        organization_id=organization.id,
        job_id=None,
        effective_from=today,
        effective_to=None,
        change_reason="合成兼岗",
        source_event_id=event_id,
    )
    assert first.id == second.id

    rows = (
        await db_session.execute(
            select(OrganizationPersonRelation).where(
                OrganizationPersonRelation.person_id == person.id,
                OrganizationPersonRelation.relation_type == "concurrent",
            )
        )
    ).scalars().all()
    assert len(rows) == 1


async def test_read_is_open_to_viewers_while_write_requires_admin(
    concurrent_client: AsyncClient,
    admin_token: str,
    restricted_token: str,
    db_session: AsyncSession,
) -> None:
    """Requirement: P-14 — 读宽写窄：只读账号能查不能写。"""
    today = _business_date()
    person = await _seed_person(db_session, "L")
    organization = await _seed_organization(db_session, "SYN_ORG_N", "合成部门卯")

    created = await _create_concurrent_position(
        concurrent_client,
        admin_token,
        person_id=str(person.id),
        organization_id=str(organization.id),
        effective_from=today.isoformat(),
    )
    assert created.status_code == 201, created.text

    read = await concurrent_client.get(CONCURRENT_PATH, headers=_auth(restricted_token))
    assert read.status_code == 200, read.text
    assert read.json()["total"] == 1

    person_read = await concurrent_client.get(
        PERSON_CONCURRENT_PATH.format(person_id=person.id),
        headers=_auth(restricted_token),
    )
    assert person_read.status_code == 200, person_read.text

    write = await _create_concurrent_position(
        concurrent_client,
        restricted_token,
        person_id=str(person.id),
        organization_id=str(organization.id),
        effective_from=today.isoformat(),
    )
    assert write.status_code == 403, write.text

    end = await concurrent_client.delete(
        f"{CONCURRENT_PATH}/{created.json()['id']}",
        headers=_auth(restricted_token),
    )
    assert end.status_code == 403, end.text
