from base64 import urlsafe_b64encode
from datetime import date
import json
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.config import get_settings
from hris.modules.workforce.models import AuditLog, PersonDocument


pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _legal_entity(
    client: AsyncClient,
    token: str,
    *,
    code: str,
) -> str:
    response = await client.post(
        "/api/v1/workforce/legal-entities",
        headers=_auth(token),
        json={
            "code": code,
            "name": f"Synthetic legal entity {code}",
            "country_code": "CN",
            "effective_from": "2026-01-01",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_person_legal_name_defaults_display_and_sensitive_audit_has_no_plaintext(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    created = await business_client.post(
        "/api/v1/workforce/persons",
        headers=_auth(admin_token),
        json={
            "legal_name": "Synthetic Legal Person",
            "reserve_employee_number": False,
            "change_reason": "Create synthetic personnel record",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["legal_name"] == "Synthetic Legal Person"
    assert created.json()["display_name"] == "Synthetic Legal Person"

    updated = await business_client.patch(
        f"/api/v1/workforce/persons/{created.json()['id']}",
        headers=_auth(admin_token),
        json={
            "birth_date": "1991-02-03",
            "ethnicity_code": "SYNTHETIC",
            "marital_status_code": "UNSPECIFIED",
            "political_status_code": "UNSPECIFIED",
            "change_reason": "Correct synthetic base fields",
        },
    )
    assert updated.status_code == 200, updated.text

    audits = list(
        (
            await db_session.scalars(
                select(AuditLog)
                .where(
                    AuditLog.object_type == "person",
                    AuditLog.object_id == UUID(created.json()["id"]),
                )
                .order_by(AuditLog.occurred_at)
            )
        ).all()
    )
    serialized = " ".join(
        f"{item.before_payload} {item.after_payload}" for item in audits
    )
    assert "1991-02-03" not in serialized
    assert "Synthetic Legal Person" not in serialized
    assert set(audits[-1].after_payload["changed_fields"]) == {
        "birth_date",
        "ethnicity_code",
        "marital_status_code",
        "political_status_code",
    }


async def test_four_legal_entities_keep_effective_dated_versions(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    first_legal_id = await _legal_entity(
        business_client,
        admin_token,
        code="LE-PERSONNEL-001",
    )
    second_legal_id = await _legal_entity(
        business_client,
        admin_token,
        code="LE-PERSONNEL-002",
    )
    person = await business_client.post(
        "/api/v1/workforce/persons",
        headers=_auth(admin_token),
        json={
            "legal_name": "Synthetic Entity Version Person",
            "reserve_employee_number": True,
            "change_reason": "Create synthetic pending employee",
        },
    )
    assert person.status_code == 201, person.text
    employment = await business_client.post(
        "/api/v1/workforce/employments",
        headers=_auth(admin_token),
        json={
            "person_id": person.json()["id"],
            "employee_type_code": "REGULAR",
            "planned_start_date": "2026-08-10",
            "contract_legal_entity_id": first_legal_id,
            "change_reason": "Create synthetic labor relationship",
        },
    )
    assert employment.status_code == 201, employment.text
    employment_id = employment.json()["id"]

    initial = await business_client.get(
        f"/api/v1/workforce/employments/{employment_id}/legal-entity-relations",
        headers=_auth(admin_token),
        params={"effective_at": "2026-08-10"},
    )
    assert initial.status_code == 200, initial.text
    assert {item["relation_kind"] for item in initial.json()} == {
        "contract",
        "payroll",
        "social_insurance",
        "tax",
    }
    assert all(item["legal_entity_id"] == first_legal_id for item in initial.json())

    changed = await business_client.post(
        f"/api/v1/workforce/employments/{employment_id}/legal-entity-relations",
        headers=_auth(admin_token),
        json={
            "relation_kind": "payroll",
            "legal_entity_id": second_legal_id,
            "effective_from": "2026-09-01",
            "change_reason": "Move synthetic payroll entity",
        },
    )
    assert changed.status_code == 201, changed.text
    assert changed.json()["version"] == 2

    august = await business_client.get(
        f"/api/v1/workforce/employments/{employment_id}/legal-entity-relations",
        headers=_auth(admin_token),
        params={"effective_at": "2026-08-31"},
    )
    september = await business_client.get(
        f"/api/v1/workforce/employments/{employment_id}/legal-entity-relations",
        headers=_auth(admin_token),
        params={"effective_at": "2026-09-01"},
    )
    assert august.status_code == 200
    assert september.status_code == 200
    august_payroll = next(item for item in august.json() if item["relation_kind"] == "payroll")
    september_payroll = next(
        item for item in september.json() if item["relation_kind"] == "payroll"
    )
    assert august_payroll["legal_entity_id"] == first_legal_id
    assert august_payroll["effective_to"] == date(2026, 8, 31).isoformat()
    assert september_payroll["legal_entity_id"] == second_legal_id


async def test_sensitive_document_is_encrypted_masked_permissioned_and_audited(
    business_client: AsyncClient,
    admin_token: str,
    restricted_token: str,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    person = await business_client.post(
        "/api/v1/workforce/persons",
        headers=_auth(admin_token),
        json={
            "legal_name": "Synthetic Protected Person",
            "reserve_employee_number": False,
            "change_reason": "Create synthetic protected person",
        },
    )
    assert person.status_code == 201, person.text
    person_id = person.json()["id"]
    document_payload = {
        "document_type_code": "SYNTHETIC_ID",
        "document_number": "SYN-19900101-0001",
        "issuing_country_code": "CN",
        "is_primary": True,
        "effective_from": "2026-08-12",
        "change_reason": "Add synthetic protected identity",
    }

    for environment_name in (
        "COREHR_PERSONNEL_ENCRYPTION_KEYS",
        "COREHR_PERSONNEL_ACTIVE_KEY_VERSION",
        "COREHR_PERSONNEL_SEARCH_KEY",
    ):
        monkeypatch.delenv(environment_name, raising=False)
    get_settings.cache_clear()
    unavailable = await business_client.post(
        f"/api/v1/workforce/persons/{person_id}/documents",
        headers=_auth(admin_token),
        json=document_payload,
    )
    assert unavailable.status_code == 503
    assert unavailable.json()["code"] == "PERSONNEL_SENSITIVE_KEY_UNAVAILABLE"
    assert document_payload["document_number"] not in unavailable.text

    encryption_key = urlsafe_b64encode(bytes(range(32))).decode()
    search_key = urlsafe_b64encode(bytes(reversed(range(32)))).decode()
    monkeypatch.setenv(
        "COREHR_PERSONNEL_ENCRYPTION_KEYS",
        json.dumps({"synthetic-v1": encryption_key}),
    )
    monkeypatch.setenv("COREHR_PERSONNEL_ACTIVE_KEY_VERSION", "synthetic-v1")
    monkeypatch.setenv("COREHR_PERSONNEL_SEARCH_KEY", search_key)
    get_settings.cache_clear()

    created = await business_client.post(
        f"/api/v1/workforce/persons/{person_id}/documents",
        headers=_auth(admin_token),
        json=document_payload,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["masked_document_number"] != document_payload["document_number"]
    assert document_payload["document_number"] not in created.text
    assert "ciphertext" not in created.text
    assert "digest" not in created.text

    stored = await db_session.get(PersonDocument, UUID(body["id"]))
    assert stored is not None
    assert document_payload["document_number"] not in stored.document_number_ciphertext.decode(
        "utf-8", errors="ignore"
    )
    assert not hasattr(stored, "document_number")

    denied = await business_client.post(
        f"/api/v1/workforce/persons/{person_id}/sensitive-values/document/{body['id']}/document_number/reveal",
        headers=_auth(restricted_token),
        json={"reason": "Synthetic denied reveal"},
    )
    assert denied.status_code == 403
    assert document_payload["document_number"] not in denied.text

    missing_reason = await business_client.post(
        f"/api/v1/workforce/persons/{person_id}/sensitive-values/document/{body['id']}/document_number/reveal",
        headers=_auth(admin_token),
        json={"reason": ""},
    )
    assert missing_reason.status_code == 422

    revealed = await business_client.post(
        f"/api/v1/workforce/persons/{person_id}/sensitive-values/document/{body['id']}/document_number/reveal",
        headers=_auth(admin_token),
        json={"reason": "Verify synthetic identity for test"},
    )
    assert revealed.status_code == 200, revealed.text
    assert revealed.json()["value"] == "SYN199001010001"

    audit = await db_session.scalar(
        select(AuditLog)
        .where(AuditLog.action == "reveal", AuditLog.object_id == UUID(body["id"]))
        .order_by(AuditLog.occurred_at.desc())
        .limit(1)
    )
    assert audit is not None
    assert audit.reason == "Verify synthetic identity for test"
    assert document_payload["document_number"] not in str(audit.after_payload)
    assert "SYN199001010001" not in str(audit.after_payload)
    get_settings.cache_clear()
