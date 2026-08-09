from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.platform.governance_models import OutboxEvent
from hris.modules.workforce.models import (
    LegalEntity,
    Organization,
    OrganizationPersonRelation,
    OrganizationType,
    OrganizationVersion,
    Person,
)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _command(expected_version: int) -> dict[str, object]:
    return {
        "expected_version": expected_version,
        "idempotency_key": str(uuid4()),
        "change_reason": "合成关系测试",
    }


async def _seed_relations_domain(
    db_session: AsyncSession,
) -> tuple[list[Organization], list[LegalEntity], list[Person]]:
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    organization_type = OrganizationType(
        code="RELATION_TEST_BU",
        name="合成关系事业部",
        sort_order=1,
        is_active=True,
    )
    organizations = [
        Organization(code="710001"),
        Organization(code="710002"),
    ]
    legal_entities = [
        LegalEntity(
            code="LEGAL_TEST_1",
            name="合成法人一",
            registered_name="合成法人一",
            country_code="CN",
            status="active",
            effective_from=today,
        ),
        LegalEntity(
            code="LEGAL_TEST_2",
            name="合成法人二",
            registered_name="合成法人二",
            country_code="CN",
            status="active",
            effective_from=today,
        ),
    ]
    people = [
        Person(display_name=f"合成人员{index}", status="active")
        for index in range(1, 6)
    ]
    db_session.add_all([organization_type, *organizations, *legal_entities, *people])
    await db_session.flush()
    db_session.add_all(
        [
            OrganizationVersion(
                organization_id=organization.id,
                version=1,
                name=f"合成组织{index}",
                organization_type_id=organization_type.id,
                status="active",
                effective_from=today,
                is_current=True,
                change_reason="合成关系测试初始化",
            )
            for index, organization in enumerate(organizations, start=1)
        ]
    )
    db_session.add(
        OrganizationPersonRelation(
            organization_id=organizations[0].id,
            person_id=people[4].id,
            relation_type="primary",
            effective_from=today,
            note="BP人员原有实线组织",
        )
    )
    await db_session.flush()
    return organizations, legal_entities, people


async def test_legal_leader_and_bp_relations_are_effective_dated(
    business_client: AsyncClient,
    admin_token: str,
    restricted_token: str,
    db_session: AsyncSession,
) -> None:
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    tomorrow = today + timedelta(days=1)
    organizations, legal_entities, people = await _seed_relations_domain(db_session)
    first_org, second_org = organizations

    first_legal = await business_client.put(
        f"/api/v1/organizations/{first_org.id}/legal-entities",
        headers=_auth(admin_token),
        json={
            "legal_entity_ids": [str(item.id) for item in legal_entities],
            "effective_from": today.isoformat(),
            "command": _command(1),
        },
    )
    assert first_legal.status_code == 200, first_legal.text
    assert set(first_legal.json()["related_ids"]) == {
        str(item.id) for item in legal_entities
    }
    assert first_legal.json()["version"] == 2

    second_legal = await business_client.put(
        f"/api/v1/organizations/{second_org.id}/legal-entities",
        headers=_auth(admin_token),
        json={
            "legal_entity_ids": [str(legal_entities[0].id)],
            "effective_from": today.isoformat(),
            "command": _command(1),
        },
    )
    assert second_legal.status_code == 200

    leaders = await business_client.put(
        f"/api/v1/organizations/{first_org.id}/leaders",
        headers=_auth(admin_token),
        json={
            "person_ids": [str(person.id) for person in people[:3]],
            "effective_from": today.isoformat(),
            "command": _command(1),
        },
    )
    assert leaders.status_code == 200
    assert len(leaders.json()["related_ids"]) == 3

    fourth_leader = await business_client.put(
        f"/api/v1/organizations/{first_org.id}/leaders",
        headers=_auth(admin_token),
        json={
            "person_ids": [str(person.id) for person in people[:4]],
            "effective_from": tomorrow.isoformat(),
            "command": _command(2),
        },
    )
    assert fourth_leader.status_code == 409
    assert fourth_leader.json()["code"] == "LEADER_LIMIT_EXCEEDED"

    bp_command = _command(1)
    bp_payload = {
        "person_id": str(people[4].id),
        "bp_type": "HRBP",
        "organization_ids": [str(first_org.id), str(second_org.id)],
        "effective_from": today.isoformat(),
        "command": bp_command,
    }
    membership = await business_client.post(
        "/api/v1/bp-memberships",
        headers=_auth(admin_token),
        json=bp_payload,
    )
    assert membership.status_code == 201, membership.text
    assert membership.json()["bp_type"] == "HRBP"
    assert set(membership.json()["organization_ids"]) == {
        str(first_org.id),
        str(second_org.id),
    }

    repeated = await business_client.post(
        "/api/v1/bp-memberships",
        headers=_auth(admin_token),
        json=bp_payload,
    )
    assert repeated.status_code == 201
    assert repeated.json()["id"] == membership.json()["id"]

    overlap = await business_client.post(
        "/api/v1/bp-memberships",
        headers=_auth(admin_token),
        json={
            "person_id": str(people[4].id),
            "bp_type": "EBP",
            "organization_ids": [str(first_org.id)],
            "effective_from": today.isoformat(),
            "command": _command(2),
        },
    )
    assert overlap.status_code == 409
    assert overlap.json()["code"] == "BP_TYPE_OVERLAP"

    future_scopes = await business_client.put(
        f"/api/v1/bp-memberships/{membership.json()['id']}/service-scopes",
        headers=_auth(admin_token),
        json={
            "organization_ids": [str(second_org.id)],
            "effective_from": tomorrow.isoformat(),
            "command": _command(2),
        },
    )
    assert future_scopes.status_code == 200, future_scopes.text
    assert future_scopes.json()["version"] == 3
    assert future_scopes.json()["organization_ids"] == [str(second_org.id)]

    cleared = await business_client.put(
        f"/api/v1/organizations/{first_org.id}/legal-entities",
        headers=_auth(admin_token),
        json={
            "legal_entity_ids": [],
            "effective_from": tomorrow.isoformat(),
            "command": _command(2),
        },
    )
    assert cleared.status_code == 200
    assert cleared.json()["related_ids"] == []

    current_relations = await business_client.get(
        f"/api/v1/organizations/{first_org.id}/relations?effective_at={today.isoformat()}",
        headers=_auth(restricted_token),
    )
    future_relations = await business_client.get(
        f"/api/v1/organizations/{first_org.id}/relations?effective_at={tomorrow.isoformat()}",
        headers=_auth(restricted_token),
    )
    assert current_relations.status_code == 200
    assert len(current_relations.json()["legal_entity_ids"]) == 2
    assert len(current_relations.json()["leader_person_ids"]) == 3
    assert current_relations.json()["bp_membership_ids"] == [membership.json()["id"]]
    assert future_relations.json()["legal_entity_ids"] == []
    assert future_relations.json()["legal_entity_version"] == 3
    assert future_relations.json()["bp_membership_ids"] == []

    second_future = await business_client.get(
        f"/api/v1/organizations/{second_org.id}/relations?effective_at={tomorrow.isoformat()}",
        headers=_auth(restricted_token),
    )
    assert second_future.json()["bp_membership_ids"] == [membership.json()["id"]]

    primary_count = await db_session.scalar(
        select(func.count())
        .select_from(OrganizationPersonRelation)
        .where(
            OrganizationPersonRelation.person_id == people[4].id,
            OrganizationPersonRelation.relation_type == "primary",
        )
    )
    outbox = await db_session.scalar(
        select(OutboxEvent).where(
            OutboxEvent.event_type == "organization.bp_membership.created",
            OutboxEvent.aggregate_id == people[4].id,
        )
    )
    assert primary_count == 1
    assert outbox is not None

    denied_write = await business_client.put(
        f"/api/v1/organizations/{second_org.id}/leaders",
        headers=_auth(restricted_token),
        json={
            "person_ids": [str(people[0].id)],
            "effective_from": today.isoformat(),
            "command": _command(1),
        },
    )
    assert denied_write.status_code == 403
    assert denied_write.json()["code"] == "PERMISSION_DENIED"
