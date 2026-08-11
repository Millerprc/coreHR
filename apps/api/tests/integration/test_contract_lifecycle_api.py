from datetime import date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.workforce.models import (
    AgreementRelationship,
    Employment,
    LegalEntity,
    Person,
)


pytestmark = pytest.mark.asyncio


def _business_today() -> date:
    return datetime.now(ZoneInfo("Asia/Shanghai")).date()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _contract_context(
    db_session: AsyncSession,
    *,
    suffix: str,
) -> tuple[Person, Employment, AgreementRelationship, LegalEntity, Person, Employment]:
    today = _business_today()
    person = Person(
        employee_number=f"98{suffix.zfill(4)}",
        display_name=f"Synthetic contract person {suffix}",
        status="active",
    )
    other_person = Person(
        employee_number=f"97{suffix.zfill(4)}",
        display_name=f"Synthetic other person {suffix}",
        status="active",
    )
    legal = LegalEntity(
        code=f"LE-CONTRACT-{suffix}",
        name=f"Synthetic contract legal {suffix}",
        country_code="CN",
        status="active",
        effective_from=today - timedelta(days=365),
    )
    db_session.add_all([person, other_person, legal])
    await db_session.flush()
    employment = Employment(
        person_id=person.id,
        employee_type_code="REGULAR",
        status="active",
        planned_start_date=today - timedelta(days=365),
        actual_start_date=today - timedelta(days=365),
        contract_legal_entity_id=legal.id,
        payroll_legal_entity_id=legal.id,
        social_insurance_legal_entity_id=legal.id,
        tax_legal_entity_id=legal.id,
        version=1,
    )
    other_employment = Employment(
        person_id=other_person.id,
        employee_type_code="REGULAR",
        status="active",
        planned_start_date=today - timedelta(days=365),
        actual_start_date=today - timedelta(days=365),
        contract_legal_entity_id=legal.id,
        version=1,
    )
    agreement = AgreementRelationship(
        person_id=person.id,
        agreement_type_code="COOPERATION",
        legal_entity_id=legal.id,
        counterparty_name=None,
        effective_from=today - timedelta(days=30),
        effective_to=None,
        source="synthetic",
    )
    db_session.add_all([employment, other_employment, agreement])
    await db_session.flush()
    return person, employment, agreement, legal, other_person, other_employment


async def _create_contract(
    business_client: AsyncClient,
    admin_token: str,
    *,
    person_id: object,
    employment_id: object | None,
    legal_entity_id: object,
    contract_number: str,
    effective_from: date,
    effective_to: date | None,
    agreement_relationship_id: object | None = None,
    expiry_notice_days: int = 30,
) -> dict[str, object]:
    response = await business_client.post(
        "/api/v1/lifecycle/contracts",
        headers=_auth(admin_token),
        json={
            "person_id": str(person_id),
            "employment_id": str(employment_id) if employment_id else None,
            "agreement_relationship_id": (
                str(agreement_relationship_id) if agreement_relationship_id else None
            ),
            "contract_type_code": "LABOR" if employment_id else "COOPERATION",
            "contract_number": contract_number,
            "legal_entity_id": str(legal_entity_id),
            "signed_on": (effective_from - timedelta(days=5)).isoformat(),
            "effective_from": effective_from.isoformat(),
            "effective_to": effective_to.isoformat() if effective_to else None,
            "expiry_notice_days": expiry_notice_days,
            "metadata_payload": {"source": "synthetic"},
            "change_reason": "Synthetic contract creation",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_contract_requires_relation_owned_by_the_same_person(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    person, _employment, agreement, legal, _other_person, other_employment = (
        await _contract_context(db_session, suffix="1")
    )
    mismatch = await business_client.post(
        "/api/v1/lifecycle/contracts",
        headers=_auth(admin_token),
        json={
            "person_id": str(person.id),
            "employment_id": str(other_employment.id),
            "contract_type_code": "LABOR",
            "contract_number": "SYN-CONTRACT-MISMATCH",
            "effective_from": _business_today().isoformat(),
            "change_reason": "Synthetic mismatch",
        },
    )
    assert mismatch.status_code == 422, mismatch.text
    assert mismatch.json()["code"] == "CONTRACT_RELATION_PERSON_MISMATCH"

    both_relations = await business_client.post(
        "/api/v1/lifecycle/contracts",
        headers=_auth(admin_token),
        json={
            "person_id": str(person.id),
            "employment_id": str(other_employment.id),
            "agreement_relationship_id": str(agreement.id),
            "contract_type_code": "LABOR",
            "contract_number": "SYN-CONTRACT-BOTH",
            "effective_from": _business_today().isoformat(),
            "change_reason": "Synthetic invalid relation selection",
        },
    )
    assert both_relations.status_code == 422, both_relations.text


async def test_contract_amendment_future_termination_and_rollback_are_auditable(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    today = _business_today()
    person, employment, _agreement, legal, _other_person, _other_employment = (
        await _contract_context(db_session, suffix="2")
    )
    original_end = today + timedelta(days=30)
    contract = await _create_contract(
        business_client,
        admin_token,
        person_id=person.id,
        employment_id=employment.id,
        legal_entity_id=legal.id,
        contract_number="SYN-CONTRACT-LIFECYCLE",
        effective_from=today - timedelta(days=365),
        effective_to=original_end,
        expiry_notice_days=45,
    )
    assert contract["version"] == 1

    alerts = await business_client.get(
        f"/api/v1/lifecycle/contracts/expiry-alerts?as_of={today}&days_ahead=90",
        headers=_auth(admin_token),
    )
    assert alerts.status_code == 200, alerts.text
    assert alerts.json()["items"][0]["contract_id"] == contract["id"]
    assert alerts.json()["items"][0]["days_remaining"] == 30

    idempotency_key = str(uuid4())
    amendment_payload = {
        "idempotency_key": idempotency_key,
        "action_type": "amendment",
        "effective_date": today.isoformat(),
        "execution_mode": "direct",
        "reason": "Synthetic contract amendment",
        "amendment": {
            "expiry_notice_days": 60,
            "metadata_payload": {"source": "synthetic", "amended": True},
        },
    }
    amendment = await business_client.post(
        f"/api/v1/lifecycle/contracts/{contract['id']}/actions",
        headers=_auth(admin_token),
        json=amendment_payload,
    )
    assert amendment.status_code == 201, amendment.text
    assert amendment.json()["status"] == "completed"
    duplicate = await business_client.post(
        f"/api/v1/lifecycle/contracts/{contract['id']}/actions",
        headers=_auth(admin_token),
        json=amendment_payload,
    )
    assert duplicate.status_code == 201, duplicate.text
    assert duplicate.json()["id"] == amendment.json()["id"]
    conflict = await business_client.post(
        f"/api/v1/lifecycle/contracts/{contract['id']}/actions",
        headers=_auth(admin_token),
        json={**amendment_payload, "reason": "Different content"},
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["code"] == "HR_EVENT_IDEMPOTENCY_CONFLICT"

    changed = await business_client.get(
        f"/api/v1/lifecycle/contracts/{contract['id']}",
        headers=_auth(admin_token),
    )
    assert changed.status_code == 200
    assert changed.json()["expiry_notice_days"] == 60
    assert changed.json()["version"] == 2

    late_close = await business_client.post(
        f"/api/v1/lifecycle/contracts/{contract['id']}/actions",
        headers=_auth(admin_token),
        json={
            "idempotency_key": str(uuid4()),
            "action_type": "termination",
            "effective_date": (original_end + timedelta(days=1)).isoformat(),
            "execution_mode": "direct",
            "reason": "Synthetic invalid late termination",
        },
    )
    assert late_close.status_code == 422, late_close.text
    assert late_close.json()["code"] == "CONTRACT_EVENT_DATE_AFTER_END"

    termination_date = today + timedelta(days=5)
    termination = await business_client.post(
        f"/api/v1/lifecycle/contracts/{contract['id']}/actions",
        headers=_auth(admin_token),
        json={
            "idempotency_key": str(uuid4()),
            "action_type": "termination",
            "effective_date": termination_date.isoformat(),
            "execution_mode": "direct",
            "reason": "Synthetic future termination",
        },
    )
    assert termination.status_code == 201, termination.text
    assert termination.json()["status"] == "scheduled"

    processed = await business_client.post(
        "/api/v1/lifecycle/hr-events/process",
        headers=_auth(admin_token),
        json={"as_of": termination_date.isoformat()},
    )
    assert processed.status_code == 200, processed.text
    assert termination.json()["id"] in processed.json()["processed_ids"]
    terminated = await business_client.get(
        f"/api/v1/lifecycle/contracts/{contract['id']}",
        headers=_auth(admin_token),
    )
    assert terminated.json()["status"] == "terminated"
    assert terminated.json()["effective_to"] == termination_date.isoformat()

    rollback = await business_client.post(
        f"/api/v1/lifecycle/hr-events/{termination.json()['id']}/rollback",
        headers=_auth(admin_token),
        json={
            "idempotency_key": str(uuid4()),
            "execution_mode": "direct",
            "effective_date": (termination_date + timedelta(days=1)).isoformat(),
            "reason": "Synthetic restore termination",
        },
    )
    assert rollback.status_code == 201, rollback.text
    assert rollback.json()["status"] == "scheduled"
    rollback_processed = await business_client.post(
        "/api/v1/lifecycle/hr-events/process",
        headers=_auth(admin_token),
        json={"as_of": (termination_date + timedelta(days=1)).isoformat()},
    )
    assert rollback_processed.status_code == 200, rollback_processed.text
    assert rollback.json()["id"] in rollback_processed.json()["processed_ids"]
    restored = await business_client.get(
        f"/api/v1/lifecycle/contracts/{contract['id']}",
        headers=_auth(admin_token),
    )
    assert restored.json()["status"] == "active"
    assert restored.json()["effective_to"] == original_end.isoformat()
    assert restored.json()["version"] == 4

    stale_rollback = await business_client.post(
        f"/api/v1/lifecycle/hr-events/{amendment.json()['id']}/rollback",
        headers=_auth(admin_token),
        json={
            "idempotency_key": str(uuid4()),
            "execution_mode": "direct",
            "effective_date": today.isoformat(),
            "reason": "Synthetic stale rollback",
        },
    )
    assert stale_rollback.status_code == 409, stale_rollback.text
    assert stale_rollback.json()["code"] == "CONTRACT_ROLLBACK_NOT_LATEST"

    timeline = await business_client.get(
        f"/api/v1/lifecycle/hr-events?object_type=contract&object_id={contract['id']}",
        headers=_auth(admin_token),
    )
    assert timeline.status_code == 200, timeline.text
    assert timeline.json()["total"] == 3


async def test_contract_renewal_rollback_and_expiry_processing_preserve_lineage(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    today = _business_today()
    person, employment, agreement, legal, _other_person, _other_employment = (
        await _contract_context(db_session, suffix="3")
    )
    original = await _create_contract(
        business_client,
        admin_token,
        person_id=person.id,
        employment_id=employment.id,
        legal_entity_id=legal.id,
        contract_number="SYN-CONTRACT-ORIGINAL",
        effective_from=today - timedelta(days=365),
        effective_to=today,
    )
    renewal_date = today + timedelta(days=1)
    renewal = await business_client.post(
        f"/api/v1/lifecycle/contracts/{original['id']}/actions",
        headers=_auth(admin_token),
        json={
            "idempotency_key": str(uuid4()),
            "action_type": "renewal",
            "effective_date": renewal_date.isoformat(),
            "execution_mode": "direct",
            "reason": "Synthetic renewal",
            "renewal": {
                "contract_number": "SYN-CONTRACT-RENEWED",
                "effective_to": (renewal_date + timedelta(days=365)).isoformat(),
                "signed_on": today.isoformat(),
                "expiry_notice_days": 45,
                "metadata_payload": {"source": "synthetic-renewal"},
            },
        },
    )
    assert renewal.status_code == 201, renewal.text
    assert renewal.json()["status"] == "scheduled"
    processed = await business_client.post(
        "/api/v1/lifecycle/hr-events/process",
        headers=_auth(admin_token),
        json={"as_of": renewal_date.isoformat()},
    )
    assert processed.status_code == 200, processed.text
    event = await business_client.get(
        f"/api/v1/lifecycle/hr-events/{renewal.json()['id']}",
        headers=_auth(admin_token),
    )
    renewed_contract_id = event.json()["actual_payload"]["new_contract_id"]
    renewed = await business_client.get(
        f"/api/v1/lifecycle/contracts/{renewed_contract_id}",
        headers=_auth(admin_token),
    )
    assert renewed.status_code == 200, renewed.text
    assert renewed.json()["predecessor_contract_id"] == original["id"]
    assert renewed.json()["version"] == 1
    original_after = await business_client.get(
        f"/api/v1/lifecycle/contracts/{original['id']}",
        headers=_auth(admin_token),
    )
    assert original_after.json()["status"] == "renewed"

    rollback = await business_client.post(
        f"/api/v1/lifecycle/hr-events/{renewal.json()['id']}/rollback",
        headers=_auth(admin_token),
        json={
            "idempotency_key": str(uuid4()),
            "execution_mode": "direct",
            "effective_date": (renewal_date + timedelta(days=1)).isoformat(),
            "reason": "Synthetic renewal rollback",
        },
    )
    assert rollback.status_code == 201, rollback.text
    rollback_processed = await business_client.post(
        "/api/v1/lifecycle/hr-events/process",
        headers=_auth(admin_token),
        json={"as_of": (renewal_date + timedelta(days=1)).isoformat()},
    )
    assert rollback_processed.status_code == 200, rollback_processed.text
    assert rollback.json()["id"] in rollback_processed.json()["processed_ids"]
    restored_original = await business_client.get(
        f"/api/v1/lifecycle/contracts/{original['id']}",
        headers=_auth(admin_token),
    )
    cancelled_renewal = await business_client.get(
        f"/api/v1/lifecycle/contracts/{renewed_contract_id}",
        headers=_auth(admin_token),
    )
    assert restored_original.json()["status"] == "active"
    assert restored_original.json()["effective_to"] == today.isoformat()
    assert cancelled_renewal.json()["status"] == "cancelled"

    agreement_contract = await _create_contract(
        business_client,
        admin_token,
        person_id=person.id,
        employment_id=None,
        agreement_relationship_id=agreement.id,
        legal_entity_id=legal.id,
        contract_number="SYN-AGREEMENT-DOCUMENT",
        effective_from=today - timedelta(days=30),
        effective_to=today - timedelta(days=1),
    )
    status_refresh = await business_client.post(
        "/api/v1/lifecycle/contracts/process-statuses",
        headers=_auth(admin_token),
        json={"as_of": today.isoformat()},
    )
    assert status_refresh.status_code == 200, status_refresh.text
    assert agreement_contract["id"] in status_refresh.json()["processed_ids"]
    expired = await business_client.get(
        f"/api/v1/lifecycle/contracts/{agreement_contract['id']}",
        headers=_auth(admin_token),
    )
    assert expired.json()["status"] == "expired"
