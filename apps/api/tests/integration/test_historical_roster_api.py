# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""历史花名册的集成测试。

Requirement: D-102 — 按任意历史时点回看当时的员工名册与当时的信息：
时点组织/任职取区间化表的生效切片，人员字段取「主档登记值 + 生效日期 ≤ 时点的最后一条修正」。
"""

from datetime import date, timedelta
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.workforce.models import (
    Employment,
    EmploymentAssignment,
    JobCatalog,
    JobCatalogVersion,
    Organization,
    OrganizationType,
    OrganizationVersion,
    Person,
    PersonFieldVersion,
)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _organization(
    db_session: AsyncSession,
    *,
    code: str,
    name: str,
    effective_from: date,
    organization_type_id: str,
) -> Organization:
    organization = Organization(code=code)
    db_session.add(organization)
    await db_session.flush()
    db_session.add(
        OrganizationVersion(
            organization_id=organization.id,
            version=1,
            name=name,
            organization_type_id=organization_type_id,
            parent_organization_id=None,
            country_code="CN",
            status="active",
            effective_from=effective_from,
            effective_to=None,
            is_current=True,
            change_reason="合成历史花名册组织",
        )
    )
    await db_session.flush()
    return organization


async def _organization_type(db_session: AsyncSession, code: str) -> OrganizationType:
    organization_type = OrganizationType(code=code, name=f"合成{code}", sort_order=0)
    db_session.add(organization_type)
    await db_session.flush()
    return organization_type


async def _job(
    db_session: AsyncSession,
    *,
    code: str,
    name: str,
    effective_from: date,
) -> JobCatalog:
    job = JobCatalog(
        code=code,
        name=name,
        status="active",
        effective_from=effective_from,
        effective_to=None,
        attributes={},
    )
    db_session.add(job)
    await db_session.flush()
    db_session.add(
        JobCatalogVersion(
            job_id=job.id,
            version=1,
            name=name,
            status="active",
            effective_from=effective_from,
            effective_to=None,
            is_current=True,
            change_reason="合成历史花名册职务",
        )
    )
    await db_session.flush()
    return job


async def _person(
    db_session: AsyncSession,
    *,
    employee_number: str,
    display_name: str,
) -> Person:
    person = Person(
        employee_number=employee_number,
        legal_name=display_name,
        display_name=display_name,
        status="active",
    )
    db_session.add(person)
    await db_session.flush()
    return person


async def _employment(
    db_session: AsyncSession,
    *,
    person: Person,
    start_date: date,
    status: str = "active",
) -> Employment:
    employment = Employment(
        person_id=person.id,
        employee_type_code="REGULAR",
        status=status,
        planned_start_date=start_date,
        actual_start_date=start_date if status == "active" else None,
        version=1,
    )
    db_session.add(employment)
    await db_session.flush()
    return employment


async def _assignment(
    db_session: AsyncSession,
    *,
    employment: Employment,
    organization_id: str,
    job_id: str | None,
    effective_from: date,
    effective_to: date | None = None,
) -> EmploymentAssignment:
    assignment = EmploymentAssignment(
        employment_id=employment.id,
        organization_id=organization_id,
        job_id=job_id,
        relation_type="primary",
        effective_from=effective_from,
        effective_to=effective_to,
        version=1,
    )
    db_session.add(assignment)
    await db_session.flush()
    return assignment


async def _correction(
    db_session: AsyncSession,
    *,
    person: Person,
    field_code: str,
    new_value: str,
    effective_from: date,
) -> PersonFieldVersion:
    record = PersonFieldVersion(
        person_id=person.id,
        field_code=field_code,
        effective_from=effective_from,
        effective_to=None,
        version=1,
        new_value=new_value,
        change_reason="合成历史花名册修正",
        created_by=uuid4(),
    )
    db_session.add(record)
    await db_session.flush()
    return record


async def test_historical_roster_requires_as_of(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    """Requirement: D-102 — as_of 必填；格式非法同样 422。"""
    missing = await business_client.get(
        "/api/v1/workforce/people/roster-history",
        headers=_auth(admin_token),
    )
    assert missing.status_code == 422, missing.text
    assert missing.json()["code"] == "REQUEST_VALIDATION_FAILED"

    invalid = await business_client.get(
        "/api/v1/workforce/people/roster-history?as_of=2026-13-45",
        headers=_auth(admin_token),
    )
    assert invalid.status_code == 422, invalid.text
    assert invalid.json()["code"] == "REQUEST_VALIDATION_FAILED"

    not_a_date = await business_client.get(
        "/api/v1/workforce/people/roster-history?as_of=not-a-date",
        headers=_auth(admin_token),
    )
    assert not_a_date.status_code == 422, not_a_date.text
    assert not_a_date.json()["code"] == "REQUEST_VALIDATION_FAILED"


async def test_historical_roster_returns_organization_and_assignment_of_that_time(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """Requirement: D-102 — 过去时点返回当时的组织、职务与入职信息。"""
    organization_type = await _organization_type(db_session, "ROSTER-DEPT")
    first_org = await _organization(
        db_session,
        code="ROSTER-A",
        name="合成原部门",
        effective_from=date(2026, 1, 1),
        organization_type_id=str(organization_type.id),
    )
    second_org = await _organization(
        db_session,
        code="ROSTER-B",
        name="合成新部门",
        effective_from=date(2026, 1, 1),
        organization_type_id=str(organization_type.id),
    )
    job = await _job(db_session, code="ROSTER-JOB", name="合成职位", effective_from=date(2026, 1, 1))

    person = await _person(db_session, employee_number="990301", display_name="合成花名册人员")
    employment = await _employment(db_session, person=person, start_date=date(2026, 1, 1))
    await _assignment(
        db_session,
        employment=employment,
        organization_id=str(first_org.id),
        job_id=str(job.id),
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 6, 30),
    )
    await _assignment(
        db_session,
        employment=employment,
        organization_id=str(second_org.id),
        job_id=str(job.id),
        effective_from=date(2026, 7, 1),
        effective_to=None,
    )

    historical = await business_client.get(
        "/api/v1/workforce/people/roster-history?as_of=2026-05-01",
        headers=_auth(admin_token),
    )
    assert historical.status_code == 200, historical.text
    body = historical.json()
    assert body["as_of"] == "2026-05-01"
    assert body["total"] == 1
    row = body["items"][0]
    assert row["employee_number"] == "990301"
    assert row["display_name"] == "合成花名册人员"
    # 时点主组织与职务来自区间化表的生效切片。
    assert row["organization_id"] == str(first_org.id)
    assert row["organization_code"] == "ROSTER-A"
    assert row["organization_name"] == "合成原部门"
    assert row["job_code"] == "ROSTER-JOB"
    assert row["job_name"] == "合成职位"
    assert row["employment_status"] == "active"
    assert row["hire_date"] == "2026-01-01"

    later = await business_client.get(
        "/api/v1/workforce/people/roster-history?as_of=2026-08-01",
        headers=_auth(admin_token),
    )
    assert later.status_code == 200, later.text
    later_row = later.json()["items"][0]
    assert later_row["organization_code"] == "ROSTER-B"
    assert later_row["organization_name"] == "合成新部门"


async def test_historical_roster_uses_field_corrections_but_falls_back_to_master(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """Requirement: D-102 — 有修正记录的人取修正后的字段值，没有修正记录的人等于主档登记值。"""
    organization_type = await _organization_type(db_session, "ROSTER-DEPT-2")
    organization = await _organization(
        db_session,
        code="ROSTER-C",
        name="合成花名册部门",
        effective_from=date(2026, 1, 1),
        organization_type_id=str(organization_type.id),
    )
    job = await _job(db_session, code="ROSTER-JOB-2", name="合成花名册职位", effective_from=date(2026, 1, 1))

    corrected = await _person(
        db_session, employee_number="990302", display_name="合成修正前姓名"
    )
    untouched = await _person(
        db_session, employee_number="990303", display_name="合成无修正人员"
    )
    for person in (corrected, untouched):
        employment = await _employment(db_session, person=person, start_date=date(2026, 1, 1))
        await _assignment(
            db_session,
            employment=employment,
            organization_id=str(organization.id),
            job_id=str(job.id),
            effective_from=date(2026, 1, 1),
            effective_to=None,
        )
    await _correction(
        db_session,
        person=corrected,
        field_code="display_name",
        new_value="合成修正后姓名",
        effective_from=date(2026, 3, 1),
    )

    before = await business_client.get(
        "/api/v1/workforce/people/roster-history?as_of=2026-02-01",
        headers=_auth(admin_token),
    )
    assert before.status_code == 200, before.text
    before_rows = {row["employee_number"]: row for row in before.json()["items"]}
    # 修正还没生效，时点姓名等于登记值。
    assert before_rows["990302"]["display_name"] == "合成修正前姓名"
    assert before_rows["990302"]["field_history_available"] is False
    assert before_rows["990302"]["corrected_fields"] == []
    assert before_rows["990303"]["display_name"] == "合成无修正人员"
    assert before_rows["990303"]["field_history_available"] is False

    after = await business_client.get(
        "/api/v1/workforce/people/roster-history?as_of=2026-04-01",
        headers=_auth(admin_token),
    )
    assert after.status_code == 200, after.text
    after_rows = {row["employee_number"]: row for row in after.json()["items"]}
    # 修正已生效，时点姓名取修正后的值。
    assert after_rows["990302"]["display_name"] == "合成修正后姓名"
    assert after_rows["990302"]["field_history_available"] is True
    assert after_rows["990302"]["corrected_fields"] == ["display_name"]
    # 没有修正记录的人：时点姓名等于当前登记值，
    # 这正是「历史花名册不是完整历史回放」的实现口径。
    assert after_rows["990303"]["display_name"] == "合成无修正人员"
    assert after_rows["990303"]["field_history_available"] is False
    assert after_rows["990303"]["corrected_fields"] == []
    # 响应里写明这一限制，界面与文档据此措辞。
    assert "不是完整的历史档案快照" in after.json()["field_history_note"]


async def test_historical_roster_future_date_returns_empty_list(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    """Requirement: D-102 — 未来时点没有数据时返回空列表，而不是 422。"""
    future = await business_client.get(
        f"/api/v1/workforce/people/roster-history?as_of={(date.today() + timedelta(days=30)).isoformat()}",
        headers=_auth(admin_token),
    )
    assert future.status_code == 200, future.text
    assert future.json()["items"] == []
    assert future.json()["total"] == 0


async def test_historical_roster_without_people_at_that_time_returns_empty(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """Requirement: D-102 — 该时点没有在册员工时返回空列表。"""
    organization_type = await _organization_type(db_session, "ROSTER-DEPT-3")
    organization = await _organization(
        db_session,
        code="ROSTER-D",
        name="合成空花名册部门",
        effective_from=date(2026, 1, 1),
        organization_type_id=str(organization_type.id),
    )
    person = await _person(db_session, employee_number="990304", display_name="合成晚期人员")
    employment = await _employment(db_session, person=person, start_date=date(2026, 6, 1))
    await _assignment(
        db_session,
        employment=employment,
        organization_id=str(organization.id),
        job_id=None,
        effective_from=date(2026, 6, 1),
        effective_to=None,
    )

    empty = await business_client.get(
        "/api/v1/workforce/people/roster-history?as_of=2026-03-01",
        headers=_auth(admin_token),
    )
    assert empty.status_code == 200, empty.text
    assert empty.json()["items"] == []
    assert empty.json()["total"] == 0

    present = await business_client.get(
        "/api/v1/workforce/people/roster-history?as_of=2026-07-01",
        headers=_auth(admin_token),
    )
    assert present.status_code == 200, present.text
    assert present.json()["total"] == 1


async def test_historical_roster_filters_by_organization_status_and_search(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """Requirement: D-102 — 服务端筛选：主组织、在职状态与姓名/工号。"""
    organization_type = await _organization_type(db_session, "ROSTER-DEPT-4")
    first_org = await _organization(
        db_session,
        code="ROSTER-E",
        name="合成筛选部门一",
        effective_from=date(2026, 1, 1),
        organization_type_id=str(organization_type.id),
    )
    second_org = await _organization(
        db_session,
        code="ROSTER-F",
        name="合成筛选部门二",
        effective_from=date(2026, 1, 1),
        organization_type_id=str(organization_type.id),
    )

    active_person = await _person(
        db_session, employee_number="990305", display_name="合成在职人员"
    )
    pending_person = await _person(
        db_session, employee_number="990306", display_name="合成待入职人员"
    )
    active_employment = await _employment(
        db_session, person=active_person, start_date=date(2026, 1, 1)
    )
    pending_employment = await _employment(
        db_session,
        person=pending_person,
        start_date=date(2026, 1, 1),
        status="pending_start",
    )
    await _assignment(
        db_session,
        employment=active_employment,
        organization_id=str(first_org.id),
        job_id=None,
        effective_from=date(2026, 1, 1),
        effective_to=None,
    )
    await _assignment(
        db_session,
        employment=pending_employment,
        organization_id=str(second_org.id),
        job_id=None,
        effective_from=date(2026, 1, 1),
        effective_to=None,
    )

    by_organization = await business_client.get(
        f"/api/v1/workforce/people/roster-history?as_of=2026-05-01&organization_id={first_org.id}",
        headers=_auth(admin_token),
    )
    assert by_organization.status_code == 200, by_organization.text
    assert [row["employee_number"] for row in by_organization.json()["items"]] == ["990305"]

    by_status = await business_client.get(
        "/api/v1/workforce/people/roster-history?as_of=2026-05-01&employment_status=pending_start",
        headers=_auth(admin_token),
    )
    assert by_status.status_code == 200, by_status.text
    assert [row["employee_number"] for row in by_status.json()["items"]] == ["990306"]

    by_name = await business_client.get(
        "/api/v1/workforce/people/roster-history?as_of=2026-05-01&search=待入职",
        headers=_auth(admin_token),
    )
    assert by_name.status_code == 200, by_name.text
    assert [row["employee_number"] for row in by_name.json()["items"]] == ["990306"]

    by_number = await business_client.get(
        "/api/v1/workforce/people/roster-history?as_of=2026-05-01&search=990305",
        headers=_auth(admin_token),
    )
    assert by_number.status_code == 200, by_number.text
    assert [row["employee_number"] for row in by_number.json()["items"]] == ["990305"]


async def test_historical_roster_paginates_with_matching_total(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """Requirement: D-102 — 分页与计数行取同一个 total。"""
    organization_type = await _organization_type(db_session, "ROSTER-DEPT-5")
    organization = await _organization(
        db_session,
        code="ROSTER-G",
        name="合成分页部门",
        effective_from=date(2026, 1, 1),
        organization_type_id=str(organization_type.id),
    )
    for index in range(3):
        person = await _person(
            db_session,
            employee_number=f"9904{index:02d}",
            display_name=f"合成分页人员{index}",
        )
        employment = await _employment(db_session, person=person, start_date=date(2026, 1, 1))
        await _assignment(
            db_session,
            employment=employment,
            organization_id=str(organization.id),
            job_id=None,
            effective_from=date(2026, 1, 1),
            effective_to=None,
        )

    page = await business_client.get(
        "/api/v1/workforce/people/roster-history?as_of=2026-05-01&limit=2&offset=0",
        headers=_auth(admin_token),
    )
    assert page.status_code == 200, page.text
    body = page.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 0

    second = await business_client.get(
        "/api/v1/workforce/people/roster-history?as_of=2026-05-01&limit=2&offset=2",
        headers=_auth(admin_token),
    )
    assert second.status_code == 200, second.text
    assert second.json()["total"] == 3
    assert len(second.json()["items"]) == 1


async def test_historical_roster_requires_person_view_permission(
    business_client: AsyncClient,
    admin_token: str,
    restricted_token: str,
) -> None:
    """Requirement: D-102 — 读权限复用 PERSON_VIEW，没有该权限码一律 403。"""
    forbidden = await business_client.get(
        "/api/v1/workforce/people/roster-history?as_of=2026-05-01",
        headers=_auth(restricted_token),
    )
    assert forbidden.status_code == 403, forbidden.text
    assert forbidden.json()["code"] == "PERMISSION_DENIED"
