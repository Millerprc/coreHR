from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.platform.models import UserAccount
from hris.modules.workforce.models import (
    AuditLog,
    Employment,
    EmploymentAssignment,
    JobCatalog,
    LegalEntity,
    Organization,
    Person,
)


pytestmark = pytest.mark.asyncio


def _business_today() -> date:
    return datetime.now(ZoneInfo("Asia/Shanghai")).date()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_direct_future_and_rollback_hr_events_change_effective_results(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    today = _business_today()
    first_organization = Organization(code="734001")
    second_organization = Organization(code="734002")
    first_job = JobCatalog(
        code="JOB-EVENT-1",
        name="合成原职务",
        status="active",
        effective_from=today - timedelta(days=30),
        attributes={},
    )
    second_job = JobCatalog(
        code="JOB-EVENT-2",
        name="合成新职务",
        status="active",
        effective_from=today - timedelta(days=30),
        attributes={},
    )
    future_job = JobCatalog(
        code="JOB-EVENT-FUTURE",
        name="尚未生效职务",
        status="active",
        effective_from=today + timedelta(days=30),
        attributes={},
    )
    legal = LegalEntity(
        code="LE-EVENT",
        name="合成人事事件法人",
        country_code="CN",
        status="active",
        effective_from=today - timedelta(days=30),
    )
    person = Person(
        employee_number="990002",
        legal_name="合成人事事件人员",
        display_name="合成人事事件人员",
        status="active",
    )
    db_session.add_all([
        first_organization,
        second_organization,
        first_job,
        second_job,
        future_job,
        legal,
        person,
    ])
    await db_session.flush()
    employment = Employment(
        person_id=person.id,
        employee_type_code="REGULAR",
        status="active",
        planned_start_date=today - timedelta(days=30),
        actual_start_date=today - timedelta(days=30),
        contract_legal_entity_id=legal.id,
        payroll_legal_entity_id=legal.id,
        social_insurance_legal_entity_id=legal.id,
        tax_legal_entity_id=legal.id,
        version=1,
    )
    db_session.add(employment)
    await db_session.flush()
    assignment = EmploymentAssignment(
        employment_id=employment.id,
        organization_id=first_organization.id,
        job_id=first_job.id,
        relation_type="primary",
        effective_from=today - timedelta(days=30),
        version=1,
    )
    db_session.add(assignment)
    await db_session.flush()

    termination = await business_client.post(
        "/api/v1/lifecycle/hr-events",
        headers=_auth(admin_token),
        json={
            "event_type": "TERMINATION",
            "object_type": "employment",
            "object_id": str(employment.id),
            "effective_date": today.isoformat(),
            "execution_mode": "direct",
            "reason": "合成离职",
            "planned_payload": {"end_reason_code": "VOLUNTARY"},
        },
    )
    assert termination.status_code == 201, termination.text
    assert termination.json()["status"] == "completed"
    await db_session.refresh(employment)
    assert employment.status == "terminated"
    assert employment.end_date == today

    rollback = await business_client.post(
        f"/api/v1/lifecycle/hr-events/{termination.json()['id']}/rollback",
        headers=_auth(admin_token),
        json={
            "execution_mode": "direct",
            "effective_date": today.isoformat(),
            "reason": "撤销错误离职",
        },
    )
    assert rollback.status_code == 201, rollback.text
    assert rollback.json()["status"] == "completed"
    await db_session.refresh(employment)
    assert employment.status == "active"
    assert employment.end_date is None

    tomorrow = today + timedelta(days=1)
    rejected_transfer = await business_client.post(
        "/api/v1/lifecycle/hr-events",
        headers=_auth(admin_token),
        json={
            "event_type": "TRANSFER",
            "object_type": "employment",
            "object_id": str(employment.id),
            "effective_date": tomorrow.isoformat(),
            "execution_mode": "direct",
            "reason": "验证调岗日期必须使用已生效职务",
            "planned_payload": {
                "organization_id": str(second_organization.id),
                "job_id": str(future_job.id),
            },
        },
    )
    assert rejected_transfer.status_code == 422, rejected_transfer.text
    assert rejected_transfer.json()["code"] == "JOB_NOT_EFFECTIVE"

    transfer = await business_client.post(
        "/api/v1/lifecycle/hr-events",
        headers=_auth(admin_token),
        json={
            "event_type": "TRANSFER",
            "object_type": "employment",
            "object_id": str(employment.id),
            "effective_date": tomorrow.isoformat(),
            "execution_mode": "direct",
            "reason": "未来调岗",
            "planned_payload": {
                "organization_id": str(second_organization.id),
                "job_id": str(second_job.id),
            },
        },
    )
    assert transfer.status_code == 201, transfer.text
    assert transfer.json()["status"] == "scheduled"
    await db_session.refresh(assignment)
    assert assignment.effective_to is None

    processed = await business_client.post(
        "/api/v1/lifecycle/hr-events/process",
        headers=_auth(admin_token),
        json={"as_of": tomorrow.isoformat()},
    )
    assert processed.status_code == 200, processed.text
    assert transfer.json()["id"] in processed.json()["processed_ids"]
    await db_session.refresh(assignment)
    assert assignment.effective_to == today

    transfer_detail = await business_client.get(
        f"/api/v1/lifecycle/hr-events/{transfer.json()['id']}",
        headers=_auth(admin_token),
    )
    assert transfer_detail.status_code == 200
    assert transfer_detail.json()["status"] == "completed"
    assert transfer_detail.json()["actual_payload"]["organization_id"] == str(second_organization.id)


async def test_approved_hr_event_executes_after_workflow_completion(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    today = _business_today()
    legal = LegalEntity(
        code="LE-APPROVAL-EVENT",
        name="Synthetic approval legal entity",
        country_code="CN",
        status="active",
        effective_from=today - timedelta(days=30),
    )
    person = Person(
        employee_number="990003",
        legal_name="Synthetic approval employee",
        display_name="Synthetic approval employee",
        status="active",
    )
    db_session.add_all([legal, person])
    await db_session.flush()
    employment = Employment(
        person_id=person.id,
        employee_type_code="REGULAR",
        status="active",
        planned_start_date=today - timedelta(days=30),
        actual_start_date=today - timedelta(days=30),
        contract_legal_entity_id=legal.id,
        payroll_legal_entity_id=legal.id,
        social_insurance_legal_entity_id=legal.id,
        tax_legal_entity_id=legal.id,
        version=1,
    )
    db_session.add(employment)
    await db_session.flush()

    event = await business_client.post(
        "/api/v1/lifecycle/hr-events",
        headers=_auth(admin_token),
        json={
            "event_type": "TERMINATION",
            "object_type": "employment",
            "object_id": str(employment.id),
            "effective_date": today.isoformat(),
            "execution_mode": "approval",
            "reason": "Synthetic approved termination",
            "planned_payload": {"end_reason_code": "VOLUNTARY"},
        },
    )
    assert event.status_code == 201, event.text
    assert event.json()["status"] == "pending_approval"

    definition = await business_client.post(
        "/api/v1/workflows/definitions",
        headers=_auth(admin_token),
        json={
            "code": "HR_EVENT_APPROVAL",
            "name": "Synthetic HR event approval",
            "category": "hr_event",
            "nodes": [
                {"code": "START", "name": "Start", "node_type": "start"},
                {
                    "code": "APPROVE",
                    "name": "Approve",
                    "node_type": "approval",
                    "sign_mode": "any",
                    "assignees": [
                        {"assignee_type": "role", "assignee_ref": "HR_ADMIN"}
                    ],
                },
                {"code": "END", "name": "End", "node_type": "end"},
            ],
            "edges": [
                {"source": "START", "target": "APPROVE"},
                {"source": "APPROVE", "target": "END"},
            ],
            "change_reason": "Synthetic approval workflow",
        },
    )
    assert definition.status_code == 201, definition.text
    published = await business_client.post(
        f"/api/v1/lifecycle/workflows/{definition.json()['id']}/publish",
        headers=_auth(admin_token),
    )
    assert published.status_code == 200, published.text
    started = await business_client.post(
        "/api/v1/lifecycle/workflow-instances",
        headers=_auth(admin_token),
        json={
            "workflow_definition_id": definition.json()["id"],
            "business_object_type": "hr_event",
            "business_object_id": event.json()["id"],
            "context": {},
        },
    )
    assert started.status_code == 201, started.text
    detail = await business_client.get(
        f"/api/v1/lifecycle/workflow-instances/{started.json()['id']}",
        headers=_auth(admin_token),
    )
    task = detail.json()["tasks"][0]
    decision = await business_client.post(
        f"/api/v1/lifecycle/workflow-tasks/{task['id']}/decision",
        headers=_auth(admin_token),
        json={"decision": "approve", "comment": "Approved"},
    )
    assert decision.status_code == 200, decision.text

    event_after = await business_client.get(
        f"/api/v1/lifecycle/hr-events/{event.json()['id']}",
        headers=_auth(admin_token),
    )
    assert event_after.status_code == 200
    assert event_after.json()["status"] == "completed"
    await db_session.refresh(employment)
    assert employment.status == "terminated"
    assert employment.end_date == today


async def test_onboarding_requires_pending_start_and_rejects_open_duplicate(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    today = _business_today()
    tomorrow = today + timedelta(days=1)
    legal = LegalEntity(
        code="LE-ONBOARDING-GUARD",
        name="Synthetic onboarding legal entity",
        country_code="CN",
        status="active",
        effective_from=today - timedelta(days=30),
    )
    person = Person(
        employee_number="990004",
        legal_name="Synthetic pending employee",
        display_name="Synthetic pending employee",
        status="active",
    )
    db_session.add_all([legal, person])
    await db_session.flush()
    employment = Employment(
        person_id=person.id,
        employee_type_code="REGULAR",
        status="pending_start",
        planned_start_date=tomorrow,
        contract_legal_entity_id=legal.id,
        payroll_legal_entity_id=legal.id,
        social_insurance_legal_entity_id=legal.id,
        tax_legal_entity_id=legal.id,
        version=1,
    )
    db_session.add(employment)
    await db_session.flush()

    event = await business_client.post(
        "/api/v1/lifecycle/hr-events",
        headers=_auth(admin_token),
        json={
            "event_type": "ONBOARDING",
            "object_type": "employment",
            "object_id": str(employment.id),
            "effective_date": tomorrow.isoformat(),
            "execution_mode": "direct",
            "reason": "Synthetic scheduled onboarding",
            "planned_payload": {},
        },
    )
    assert event.status_code == 201, event.text
    assert event.json()["status"] == "scheduled"

    duplicate = await business_client.post(
        "/api/v1/lifecycle/hr-events",
        headers=_auth(admin_token),
        json={
            "event_type": "ONBOARDING",
            "object_type": "employment",
            "object_id": str(employment.id),
            "effective_date": tomorrow.isoformat(),
            "execution_mode": "approval",
            "reason": "Synthetic duplicate onboarding",
            "planned_payload": {},
        },
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["code"] == "ONBOARDING_EVENT_ALREADY_OPEN"

    employment.status = "active"
    employment.actual_start_date = today
    await db_session.flush()
    processed = await business_client.post(
        "/api/v1/lifecycle/hr-events/process",
        headers=_auth(admin_token),
        json={"as_of": tomorrow.isoformat()},
    )
    assert processed.status_code == 200, processed.text
    assert processed.json()["processed_ids"] == []
    assert processed.json()["failed"][0]["event_id"] == event.json()["id"]

    await db_session.refresh(employment)
    assert employment.status == "active"
    assert employment.actual_start_date == today

    invalid_state = await business_client.post(
        "/api/v1/lifecycle/hr-events",
        headers=_auth(admin_token),
        json={
            "event_type": "ONBOARDING",
            "object_type": "employment",
            "object_id": str(employment.id),
            "effective_date": tomorrow.isoformat(),
            "execution_mode": "approval",
            "reason": "Synthetic invalid onboarding",
            "planned_payload": {},
        },
    )
    assert invalid_state.status_code == 409, invalid_state.text
    assert invalid_state.json()["code"] == "ONBOARDING_EMPLOYMENT_STATUS_INVALID"


async def test_ssc_can_initiate_only_onboarding_and_creation_is_audited(
    business_client: AsyncClient,
    admin_token: str,
    ssc_token: str,
    lifecycle_admin_token: str,
    restricted_token: str,
    db_session: AsyncSession,
) -> None:
    today = _business_today()
    legal = LegalEntity(
        code="LE-SSC-ONBOARDING",
        name="Synthetic SSC onboarding legal entity",
        country_code="CN",
        status="active",
        effective_from=today - timedelta(days=30),
    )
    person = Person(
        employee_number="990005",
        legal_name="Synthetic SSC pending employee",
        display_name="Synthetic SSC pending employee",
        status="active",
    )
    db_session.add_all([legal, person])
    await db_session.flush()
    employment = Employment(
        person_id=person.id,
        employee_type_code="REGULAR",
        status="pending_start",
        planned_start_date=today,
        contract_legal_entity_id=legal.id,
        payroll_legal_entity_id=legal.id,
        social_insurance_legal_entity_id=legal.id,
        tax_legal_entity_id=legal.id,
        version=1,
    )
    db_session.add(employment)
    await db_session.flush()
    onboarding_payload = {
        "event_type": "ONBOARDING",
        "object_type": "employment",
        "object_id": str(employment.id),
        "effective_date": today.isoformat(),
        "execution_mode": "approval",
        "reason": "  SSC initiates synthetic onboarding  ",
        "planned_payload": {},
    }

    denied = await business_client.post(
        "/api/v1/lifecycle/hr-events",
        headers=_auth(restricted_token),
        json=onboarding_payload,
    )
    assert denied.status_code == 403, denied.text
    assert denied.json()["code"] == "PERMISSION_DENIED"

    lifecycle_admin_denied = await business_client.post(
        "/api/v1/lifecycle/hr-events",
        headers=_auth(lifecycle_admin_token),
        json=onboarding_payload,
    )
    assert lifecycle_admin_denied.status_code == 403, lifecycle_admin_denied.text
    assert lifecycle_admin_denied.json()["code"] == "PERMISSION_DENIED"

    created = await business_client.post(
        "/api/v1/lifecycle/hr-events",
        headers=_auth(ssc_token),
        json=onboarding_payload,
    )
    assert created.status_code == 201, created.text
    assert created.json()["reason"] == "SSC initiates synthetic onboarding"
    assert created.json()["status"] == "pending_approval"

    ssc_user = await db_session.scalar(
        select(UserAccount).where(UserAccount.username == "synthetic-ssc")
    )
    audit = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "create",
            AuditLog.object_type == "hr_event",
            AuditLog.object_id == UUID(created.json()["id"]),
        )
    )
    assert ssc_user is not None
    assert audit is not None
    assert audit.actor_id == ssc_user.id
    assert audit.reason == "SSC initiates synthetic onboarding"
    assert audit.after_payload["event_type"] == "ONBOARDING"
    assert audit.after_payload["object_id"] == str(employment.id)

    termination = await business_client.post(
        "/api/v1/lifecycle/hr-events",
        headers=_auth(ssc_token),
        json={
            **onboarding_payload,
            "event_type": "TERMINATION",
            "reason": "SSC must not terminate employment",
        },
    )
    assert termination.status_code == 403, termination.text
    assert termination.json()["code"] == "PERMISSION_DENIED"

    admin_blank_reason = await business_client.post(
        "/api/v1/lifecycle/hr-events",
        headers=_auth(admin_token),
        json={**onboarding_payload, "reason": "   "},
    )
    assert admin_blank_reason.status_code == 422, admin_blank_reason.text
