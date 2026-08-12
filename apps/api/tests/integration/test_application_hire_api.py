from datetime import date, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.workforce.models import (
    Employment,
    EmploymentAssignment,
    JobCatalog,
    LegalEntity,
    Organization,
    Person,
)
from hris.modules.workflow.models import Candidate, JobApplication


pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _application_at_offer(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
    *,
    suffix: str,
) -> tuple[dict[str, object], Organization, JobCatalog, LegalEntity]:
    today = date.today()
    organization = Organization(code=f"74{suffix.zfill(4)}")
    job = JobCatalog(
        code=f"JOB-HIRE-{suffix}",
        name=f"Synthetic hire job {suffix}",
        status="active",
        effective_from=today - timedelta(days=1),
        attributes={},
    )
    legal = LegalEntity(
        code=f"LE-HIRE-{suffix}",
        name=f"Synthetic hire legal entity {suffix}",
        country_code="CN",
        status="active",
        effective_from=today - timedelta(days=1),
    )
    db_session.add_all([organization, job, legal])
    await db_session.flush()

    recruitment = await business_client.post(
        "/api/v1/lifecycle/recruitment-requests",
        headers=_auth(admin_token),
        json={
            "organization_id": str(organization.id),
            "job_id": str(job.id),
            "requested_count": 1,
            "target_month": today.replace(day=1).isoformat(),
            "reason": "Synthetic hire recruitment",
        },
    )
    assert recruitment.status_code == 201, recruitment.text
    candidate = await business_client.post(
        "/api/v1/lifecycle/candidates",
        headers=_auth(admin_token),
        json={
            "display_name": f"Synthetic hire candidate {suffix}",
            "contact_payload": {"mobile": "13800000000"},
        },
    )
    assert candidate.status_code == 201, candidate.text
    application = await business_client.post(
        "/api/v1/lifecycle/applications",
        headers=_auth(admin_token),
        json={
            "candidate_id": candidate.json()["id"],
            "recruitment_request_id": recruitment.json()["id"],
            "current_stage": "screening",
        },
    )
    assert application.status_code == 201, application.text
    for next_status in ("screening", "interview", "offer"):
        updated = await business_client.patch(
            f"/api/v1/lifecycle/applications/{application.json()['id']}",
            headers=_auth(admin_token),
            json={
                "status": next_status,
                "current_stage": next_status,
                "change_reason": f"Synthetic move to {next_status}",
            },
        )
        assert updated.status_code == 200, updated.text
    return application.json(), organization, job, legal


async def test_hire_application_creates_pending_start_records_idempotently(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    application, organization, job, legal = await _application_at_offer(
        business_client,
        admin_token,
        db_session,
        suffix="1",
    )
    application_id = str(application["id"])

    direct_hired = await business_client.patch(
        f"/api/v1/lifecycle/applications/{application_id}",
        headers=_auth(admin_token),
        json={
            "status": "hired",
            "current_stage": "hired",
            "change_reason": "Must use the hire command",
        },
    )
    assert direct_hired.status_code == 409, direct_hired.text
    assert direct_hired.json()["code"] == "APPLICATION_HIRE_COMMAND_REQUIRED"
    direct_hired_stage = await business_client.patch(
        f"/api/v1/lifecycle/applications/{application_id}",
        headers=_auth(admin_token),
        json={
            "current_stage": "hired",
            "change_reason": "Must not bypass the hire command through the stage",
        },
    )
    assert direct_hired_stage.status_code == 409, direct_hired_stage.text
    assert direct_hired_stage.json()["code"] == "APPLICATION_HIRE_COMMAND_REQUIRED"

    idempotency_key = str(uuid4())
    payload = {
        "idempotency_key": idempotency_key,
        "planned_start_date": "2026-09-01",
        "employee_type_code": "REGULAR",
        "contract_legal_entity_id": str(legal.id),
        "gender_code": "UNKNOWN",
        "nationality_code": "CHN",
        "country_code": "CHN",
        "probation_end_date": "2026-11-30",
        "reason": "Synthetic accepted offer",
    }
    first = await business_client.post(
        f"/api/v1/lifecycle/applications/{application_id}/hire",
        headers=_auth(admin_token),
        json=payload,
    )
    assert first.status_code == 201, first.text
    result = first.json()
    assert result["application_id"] == application_id
    assert result["planned_start_date"] == "2026-09-01"

    duplicate = await business_client.post(
        f"/api/v1/lifecycle/applications/{application_id}/hire",
        headers=_auth(admin_token),
        json=payload,
    )
    assert duplicate.status_code == 201, duplicate.text
    assert duplicate.json()["id"] == result["id"]

    conflict = await business_client.post(
        f"/api/v1/lifecycle/applications/{application_id}/hire",
        headers=_auth(admin_token),
        json={**payload, "employee_type_code": "INTERN"},
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["code"] == "IDEMPOTENCY_KEY_REUSED"

    candidate = await db_session.get(Candidate, application["candidate_id"])
    stored_application = await db_session.get(JobApplication, application_id)
    person = await db_session.get(Person, result["person_id"])
    employment = await db_session.get(Employment, result["employment_id"])
    assignment = await db_session.get(EmploymentAssignment, result["assignment_id"])
    assert candidate is not None and candidate.status == "converted"
    assert candidate.linked_person_id == person.id
    assert stored_application is not None and stored_application.status == "hired"
    assert person is not None and person.employee_number is not None
    assert employment is not None and employment.status == "pending_start"
    assert employment.contract_legal_entity_id == legal.id
    assert employment.payroll_legal_entity_id == legal.id
    assert employment.social_insurance_legal_entity_id == legal.id
    assert employment.tax_legal_entity_id == legal.id
    assert assignment is not None and assignment.organization_id == organization.id
    assert assignment.job_id == job.id
    assert assignment.relation_type == "primary"

    employment_count = await db_session.scalar(
        select(func.count()).select_from(Employment).where(Employment.person_id == person.id)
    )
    assert employment_count == 1


async def test_hire_application_can_reuse_existing_person_and_employee_number(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    application, _organization, _job, legal = await _application_at_offer(
        business_client,
        admin_token,
        db_session,
        suffix="2",
    )
    existing_person = Person(
        employee_number="992002",
        legal_name="Synthetic returning person",
        display_name="Synthetic returning person",
        status="active",
    )
    db_session.add(existing_person)
    await db_session.flush()

    response = await business_client.post(
        f"/api/v1/lifecycle/applications/{application['id']}/hire",
        headers=_auth(admin_token),
        json={
            "idempotency_key": str(uuid4()),
            "planned_start_date": "2026-10-01",
            "employee_type_code": "REGULAR",
            "contract_legal_entity_id": str(legal.id),
            "existing_person_id": str(existing_person.id),
            "reason": "Synthetic rehire",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["person_id"] == str(existing_person.id)
    refreshed = await db_session.get(Person, existing_person.id)
    assert refreshed is not None and refreshed.employee_number == "992002"
