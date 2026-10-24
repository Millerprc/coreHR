# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""HR 事件执行路径上的 person 级兼岗集成测试。

Requirement: D-104 — 兼岗以「人员级组织关系」（organization_person_relations）为
唯一权威载体。本文件覆盖人事事件链上的三条路径：

1. ``CONCURRENT_ASSIGNMENT`` 事件生效 → 写 organization_person_relations，
   **不再**写 employment 级 EmploymentAssignment；
2. ``END_ASSIGNMENT`` 事件带 ``concurrent_position_id`` → 关闭 person 级兼岗区间；
3. ``CONCURRENT_ASSIGNMENT`` 事件回退 → 关闭 person 级兼岗区间。

Requirement: D-026 — 同一时间只能有一个主组织，兼岗可同时存在多个。
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.workforce.models import (
    Employment,
    EmploymentAssignment,
    JobCatalog,
    LegalEntity,
    Organization,
    OrganizationPersonRelation,
    Person,
)


pytestmark = pytest.mark.asyncio


HR_EVENTS_PATH = "/api/v1/lifecycle/hr-events"


def _business_today() -> date:
    return datetime.now(ZoneInfo("Asia/Shanghai")).date()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_employment_context(
    db_session: AsyncSession,
    label: str,
    employee_number: str,
) -> tuple[Employment, Organization, JobCatalog]:
    """造一个「有主职的雇佣 + 目标部门 + 目标职务」的上下文。"""
    today = _business_today()
    legal = LegalEntity(
        code=f"LE-CP-{label}",
        name=f"合成兼岗事件法人{label}",
        country_code="CN",
        status="active",
        effective_from=today - timedelta(days=60),
    )
    primary_organization = Organization(code=f"CP-ORG-P-{label}")
    target_organization = Organization(code=f"CP-ORG-T-{label}")
    primary_job = JobCatalog(
        code=f"JOB-CP-P-{label}",
        name=f"合成兼岗主职{label}",
        status="active",
        effective_from=today - timedelta(days=60),
        attributes={},
    )
    target_job = JobCatalog(
        code=f"JOB-CP-T-{label}",
        name=f"合成兼岗目标职{label}",
        status="active",
        effective_from=today - timedelta(days=60),
        attributes={},
    )
    person = Person(
        employee_number=employee_number,
        legal_name=f"合成兼岗事件人员{label}",
        display_name=f"合成兼岗事件人员{label}",
        status="active",
    )
    db_session.add_all([
        legal,
        primary_organization,
        target_organization,
        primary_job,
        target_job,
        person,
    ])
    await db_session.flush()
    employment = Employment(
        person_id=person.id,
        employee_type_code="REGULAR",
        status="active",
        planned_start_date=today - timedelta(days=60),
        actual_start_date=today - timedelta(days=60),
        contract_legal_entity_id=legal.id,
        payroll_legal_entity_id=legal.id,
        social_insurance_legal_entity_id=legal.id,
        tax_legal_entity_id=legal.id,
        version=1,
    )
    db_session.add(employment)
    await db_session.flush()
    db_session.add(
        EmploymentAssignment(
            employment_id=employment.id,
            organization_id=primary_organization.id,
            job_id=primary_job.id,
            relation_type="primary",
            effective_from=today - timedelta(days=60),
            version=1,
        )
    )
    await db_session.flush()
    return employment, target_organization, target_job


async def _concurrent_relations(
    db_session: AsyncSession,
    person_id: object,
) -> list[OrganizationPersonRelation]:
    return list(
        (
            await db_session.execute(
                select(OrganizationPersonRelation).where(
                    OrganizationPersonRelation.person_id == person_id,
                    OrganizationPersonRelation.relation_type == "concurrent",
                )
            )
        ).scalars().all()
    )


async def test_concurrent_assignment_event_writes_person_level_relation(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """Requirement: D-104 — 兼岗事件写人员级组织关系，不写 employment 级任职。"""
    today = _business_today()
    employment, target_organization, target_job = await _seed_employment_context(
        db_session, "01", "990101"
    )

    created = await business_client.post(
        HR_EVENTS_PATH,
        headers=_auth(admin_token),
        json={
            "event_type": "CONCURRENT_ASSIGNMENT",
            "object_type": "employment",
            "object_id": str(employment.id),
            "effective_date": today.isoformat(),
            "execution_mode": "direct",
            "reason": "合成兼岗事件",
            "planned_payload": {
                "organization_id": str(target_organization.id),
                "job_id": str(target_job.id),
            },
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "completed"
    assert body["actual_payload"]["relation_type"] == "concurrent"
    assert body["actual_payload"]["person_id"] == str(employment.person_id)

    relations = await _concurrent_relations(db_session, employment.person_id)
    assert len(relations) == 1, "兼岗事件应写入一条人员级组织关系"
    assert relations[0].organization_id == target_organization.id
    assert relations[0].effective_from == today
    assert relations[0].effective_to is None

    # 关键断言：employment 级任职表不得出现兼岗行。
    employment_level = (
        await db_session.execute(
            select(EmploymentAssignment).where(
                EmploymentAssignment.employment_id == employment.id,
                EmploymentAssignment.relation_type == "concurrent",
            )
        )
    ).scalars().all()
    assert employment_level == [], "兼岗事件不得落到 employment 级任职表"

    # 既有主职不受影响。
    primaries = (
        await db_session.execute(
            select(EmploymentAssignment).where(
                EmploymentAssignment.employment_id == employment.id,
                EmploymentAssignment.relation_type == "primary",
            )
        )
    ).scalars().all()
    assert len(primaries) == 1
    assert primaries[0].effective_to is None


async def test_end_assignment_event_closes_person_level_concurrent_position(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """Requirement: D-104 — END_ASSIGNMENT 带 concurrent_position_id 可结束兼岗。"""
    today = _business_today()
    employment, target_organization, target_job = await _seed_employment_context(
        db_session, "02", "990102"
    )

    created = await business_client.post(
        HR_EVENTS_PATH,
        headers=_auth(admin_token),
        json={
            "event_type": "CONCURRENT_ASSIGNMENT",
            "object_type": "employment",
            "object_id": str(employment.id),
            "effective_date": today.isoformat(),
            "execution_mode": "direct",
            "reason": "合成兼岗事件",
            "planned_payload": {
                "organization_id": str(target_organization.id),
                "job_id": str(target_job.id),
            },
        },
    )
    assert created.status_code == 201, created.text
    concurrent_position_id = created.json()["actual_payload"]["concurrent_position_id"]

    ended = await business_client.post(
        HR_EVENTS_PATH,
        headers=_auth(admin_token),
        json={
            "event_type": "END_ASSIGNMENT",
            "object_type": "employment",
            "object_id": str(employment.id),
            "effective_date": today.isoformat(),
            "execution_mode": "direct",
            "reason": "合成结束兼岗",
            "planned_payload": {"concurrent_position_id": concurrent_position_id},
        },
    )
    assert ended.status_code == 201, ended.text
    assert ended.json()["actual_payload"]["concurrent_position_id"] == concurrent_position_id

    relations = await _concurrent_relations(db_session, employment.person_id)
    assert len(relations) == 1
    assert relations[0].effective_to == today


async def test_rollback_of_concurrent_assignment_event_closes_relation(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """Requirement: D-104 — 兼岗事件回退按人员级关系处理，不依赖 employment 级任职。"""
    today = _business_today()
    employment, target_organization, target_job = await _seed_employment_context(
        db_session, "03", "990103"
    )

    created = await business_client.post(
        HR_EVENTS_PATH,
        headers=_auth(admin_token),
        json={
            "event_type": "CONCURRENT_ASSIGNMENT",
            "object_type": "employment",
            "object_id": str(employment.id),
            "effective_date": today.isoformat(),
            "execution_mode": "direct",
            "reason": "合成兼岗事件",
            "planned_payload": {
                "organization_id": str(target_organization.id),
                "job_id": str(target_job.id),
            },
        },
    )
    assert created.status_code == 201, created.text

    rollback = await business_client.post(
        f"{HR_EVENTS_PATH}/{created.json()['id']}/rollback",
        headers=_auth(admin_token),
        json={
            "execution_mode": "direct",
            "effective_date": today.isoformat(),
            "reason": "撤销错误兼岗",
        },
    )
    assert rollback.status_code == 201, rollback.text
    assert rollback.json()["status"] == "completed"

    relations = await _concurrent_relations(db_session, employment.person_id)
    assert len(relations) == 1
    assert relations[0].effective_to == today
