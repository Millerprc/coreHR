from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.workforce.models import Organization


pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_person_archive_keeps_employment_assignment_and_agreement_history(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    first_organization = Organization(code="731001")
    second_organization = Organization(code="731002")
    db_session.add_all([first_organization, second_organization])
    await db_session.flush()

    for dimension_type, code, name in (
        ("LEVEL", "L6", "六级"),
        ("GRADE", "G2", "二等"),
        ("CLASS", "C2", "二类"),
        ("SEQUENCE", "TECH", "技术"),
    ):
        dimension = await business_client.post(
            "/api/v1/workforce/job-dimensions",
            headers=_auth(admin_token),
            json={
                "dimension_type": dimension_type,
                "code": code,
                "name": name,
                "effective_from": "2026-01-01",
                "change_reason": "建立合成职务维度",
            },
        )
        assert dimension.status_code == 201, dimension.text

    legal = await business_client.post(
        "/api/v1/workforce/legal-entities",
        headers=_auth(admin_token),
        json={
            "code": "LE-SYNTHETIC",
            "name": "合成测试法人",
            "country_code": "CN",
            "effective_from": "2026-01-01",
        },
    )
    assert legal.status_code == 201, legal.text
    legal_id = legal.json()["id"]

    job = await business_client.post(
        "/api/v1/workforce/jobs",
        headers=_auth(admin_token),
        json={
            "code": "JOB-SYNTHETIC",
            "name": "合成测试职务",
            "level_code": "L6",
            "grade_code": "G2",
            "class_code": "C2",
            "sequence_code": "TECH",
            "effective_from": "2026-01-01",
            "change_reason": "建立合成测试职务",
        },
    )
    assert job.status_code == 201, job.text
    job_id = job.json()["id"]

    person = await business_client.post(
        "/api/v1/workforce/persons",
        headers=_auth(admin_token),
        json={
            "display_name": "合成测试人员",
            "country_code": "CN",
            "reserve_employee_number": True,
            "change_reason": "建立待入职档案",
        },
    )
    assert person.status_code == 201, person.text
    person_id = person.json()["id"]
    assert person.json()["employee_number"].isdigit()
    assert len(person.json()["employee_number"]) == 6

    employment = await business_client.post(
        "/api/v1/workforce/employments",
        headers=_auth(admin_token),
        json={
            "person_id": person_id,
            "employee_type_code": "REGULAR",
            "planned_start_date": "2026-08-10",
            "contract_legal_entity_id": legal_id,
            "change_reason": "建立待入职劳动关系",
        },
    )
    assert employment.status_code == 201, employment.text
    employment_id = employment.json()["id"]
    assert employment.json()["status"] == "pending_start"
    assert employment.json()["payroll_legal_entity_id"] == legal_id
    assert employment.json()["social_insurance_legal_entity_id"] == legal_id
    assert employment.json()["tax_legal_entity_id"] == legal_id

    assignment = await business_client.post(
        "/api/v1/workforce/employment-assignments",
        headers=_auth(admin_token),
        json={
            "employment_id": employment_id,
            "organization_id": str(first_organization.id),
            "job_id": job_id,
            "relation_type": "primary",
            "effective_from": "2026-08-10",
            "change_reason": "设置计划主组织和主职务",
        },
    )
    assert assignment.status_code == 201, assignment.text

    overlapping_primary = await business_client.post(
        "/api/v1/workforce/employment-assignments",
        headers=_auth(admin_token),
        json={
            "employment_id": employment_id,
            "organization_id": str(second_organization.id),
            "job_id": job_id,
            "relation_type": "primary",
            "effective_from": "2026-09-01",
            "change_reason": "错误的重叠主关系",
        },
    )
    assert overlapping_primary.status_code == 409
    assert overlapping_primary.json()["code"] == "PRIMARY_ASSIGNMENT_PERIOD_OVERLAP"

    agreement = await business_client.post(
        "/api/v1/workforce/agreement-relationships",
        headers=_auth(admin_token),
        json={
            "person_id": person_id,
            "agreement_type_code": "COOPERATION",
            "counterparty_name": "合成测试合作方",
            "effective_from": "2026-08-10",
            "source": "manual",
            "change_reason": "登记并行协议关系",
        },
    )
    assert agreement.status_code == 201, agreement.text

    updated = await business_client.patch(
        f"/api/v1/workforce/persons/{person_id}",
        headers=_auth(admin_token),
        json={"former_name": "合成曾用名", "change_reason": "基础档案更正"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["former_name"] == "合成曾用名"

    archive = await business_client.get(
        f"/api/v1/workforce/persons/{person_id}",
        headers=_auth(admin_token),
    )
    assert archive.status_code == 200, archive.text
    assert archive.json()["person"]["former_name"] == "合成曾用名"
    assert len(archive.json()["employments"]) == 1
    assert len(archive.json()["assignments"]) == 1
    assert len(archive.json()["agreements"]) == 1


async def test_employment_overlap_does_not_block_non_employment_agreements(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    person = await business_client.post(
        "/api/v1/workforce/persons",
        headers=_auth(admin_token),
        json={
            "display_name": "仅协议合成人员",
            "reserve_employee_number": False,
            "change_reason": "建立人员主数据",
        },
    )
    assert person.status_code == 201
    agreement = await business_client.post(
        "/api/v1/workforce/agreement-relationships",
        headers=_auth(admin_token),
        json={
            "person_id": person.json()["id"],
            "agreement_type_code": "DISPATCH",
            "counterparty_name": "合成派遣单位",
            "effective_from": date.today().isoformat(),
            "effective_to": (date.today() + timedelta(days=365)).isoformat(),
            "change_reason": "登记派遣协议关系",
        },
    )
    assert agreement.status_code == 201, agreement.text

    archive = await business_client.get(
        f"/api/v1/workforce/persons/{person.json()['id']}",
        headers=_auth(admin_token),
    )
    assert archive.status_code == 200
    assert archive.json()["employments"] == []
    assert len(archive.json()["agreements"]) == 1
