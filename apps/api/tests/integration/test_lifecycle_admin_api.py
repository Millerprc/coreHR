from datetime import date, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.workforce.models import JobCatalog, LegalEntity, Organization, Person


pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_candidate_application_and_contract_admin_lifecycle(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    today = date.today()
    organization = Organization(code="735001")
    job = JobCatalog(
        code="JOB-LIFECYCLE",
        name="Synthetic lifecycle job",
        status="active",
        effective_from=today - timedelta(days=1),
        attributes={},
    )
    legal = LegalEntity(
        code="LE-LIFECYCLE",
        name="Synthetic lifecycle legal entity",
        country_code="CN",
        status="active",
        effective_from=today - timedelta(days=1),
    )
    person = Person(employee_number="990004", display_name="Synthetic lifecycle person", status="active")
    db_session.add_all([organization, job, legal, person])
    await db_session.flush()

    recruitment = await business_client.post(
        "/api/v1/lifecycle/recruitment-requests",
        headers=_auth(admin_token),
        json={
            "organization_id": str(organization.id),
            "job_id": str(job.id),
            "requested_count": 1,
            "target_month": today.replace(day=1).isoformat(),
            "reason": "Synthetic lifecycle recruitment",
        },
    )
    assert recruitment.status_code == 201, recruitment.text

    candidate = await business_client.post(
        "/api/v1/lifecycle/candidates",
        headers=_auth(admin_token),
        json={
            "display_name": "Synthetic candidate",
            "contact_payload": {"mobile": "13800000000"},
        },
    )
    assert candidate.status_code == 201, candidate.text
    candidate_id = candidate.json()["id"]
    candidate_page = await business_client.get(
        "/api/v1/lifecycle/candidates?search=Synthetic",
        headers=_auth(admin_token),
    )
    assert candidate_page.status_code == 200
    assert candidate_page.json()["total"] == 1
    application = await business_client.post(
        "/api/v1/lifecycle/applications",
        headers=_auth(admin_token),
        json={
            "candidate_id": candidate_id,
            "recruitment_request_id": recruitment.json()["id"],
            "current_stage": "screening",
        },
    )
    assert application.status_code == 201, application.text
    application_id = application.json()["id"]
    for next_status in ("screening", "interview", "offer"):
        updated = await business_client.patch(
            f"/api/v1/lifecycle/applications/{application_id}",
            headers=_auth(admin_token),
            json={
                "status": next_status,
                "current_stage": next_status,
                "change_reason": f"Move to {next_status}",
            },
        )
        assert updated.status_code == 200, updated.text
    hired = await business_client.post(
        f"/api/v1/lifecycle/applications/{application_id}/hire",
        headers=_auth(admin_token),
        json={
            "idempotency_key": str(uuid4()),
            "planned_start_date": today.isoformat(),
            "employee_type_code": "REGULAR",
            "contract_legal_entity_id": str(legal.id),
            "existing_person_id": str(person.id),
            "reason": "Synthetic accepted offer",
        },
    )
    assert hired.status_code == 201, hired.text
    assert hired.json()["person_id"] == str(person.id)
    application_page = await business_client.get(
        "/api/v1/lifecycle/applications?status=hired",
        headers=_auth(admin_token),
    )
    assert application_page.status_code == 200
    assert application_page.json()["total"] == 1

    contract = await business_client.post(
        "/api/v1/lifecycle/contracts",
        headers=_auth(admin_token),
        json={
            "person_id": str(person.id),
            "contract_type_code": "LABOR",
            "contract_number": "SYN-LC-001",
            "legal_entity_id": str(legal.id),
            "effective_from": today.isoformat(),
            "metadata_payload": {"source": "synthetic"},
            "change_reason": "Synthetic contract creation",
        },
    )
    assert contract.status_code == 201, contract.text
    contract_id = contract.json()["id"]
    terminated = await business_client.post(
        f"/api/v1/lifecycle/contracts/{contract_id}/actions",
        headers=_auth(admin_token),
        json={
            "idempotency_key": str(uuid4()),
            "action_type": "termination",
            "effective_date": today.isoformat(),
            "execution_mode": "direct",
            "reason": "Synthetic contract close",
        },
    )
    assert terminated.status_code == 201, terminated.text
    contract_page = await business_client.get(
        f"/api/v1/lifecycle/contracts?person_id={person.id}",
        headers=_auth(admin_token),
    )
    assert contract_page.status_code == 200
    assert contract_page.json()["items"][0]["status"] == "terminated"
