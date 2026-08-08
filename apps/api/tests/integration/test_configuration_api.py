from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.workforce.models import AuditLog


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_dictionary(
    client: AsyncClient,
    token: str,
    *,
    code: str,
    name: str,
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/configuration/dictionaries",
        headers=_auth(token),
        json={"code": code, "name": name},
    )
    assert response.status_code == 201
    return response.json()


async def test_dictionary_create_and_list(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    created = await _create_dictionary(
        business_client,
        admin_token,
        code="EMPLOYEE_TYPE",
        name="人员类型",
    )

    response = await business_client.get(
        "/api/v1/configuration/dictionaries",
        headers=_auth(admin_token),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == created["id"]


async def test_dictionary_conflicts_parent_rules_and_safe_deactivation(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    first = await _create_dictionary(
        business_client,
        admin_token,
        code="JOB_LEVEL",
        name="职级",
    )
    second = await _create_dictionary(
        business_client,
        admin_token,
        code="JOB_GRADE",
        name="职等",
    )

    duplicate = await business_client.post(
        "/api/v1/configuration/dictionaries",
        headers=_auth(admin_token),
        json={"code": "JOB_LEVEL", "name": "重复"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "DICTIONARY_CODE_CONFLICT"

    parent = await business_client.post(
        f"/api/v1/configuration/dictionaries/{first['id']}/items",
        headers=_auth(admin_token),
        json={"code": "LEVEL_6", "name": "六级"},
    )
    assert parent.status_code == 201

    duplicate_item = await business_client.post(
        f"/api/v1/configuration/dictionaries/{first['id']}/items",
        headers=_auth(admin_token),
        json={"code": "LEVEL_6", "name": "重复"},
    )
    assert duplicate_item.status_code == 409
    assert duplicate_item.json()["code"] == "DICTIONARY_ITEM_CODE_CONFLICT"

    invalid_parent = await business_client.post(
        f"/api/v1/configuration/dictionaries/{second['id']}/items",
        headers=_auth(admin_token),
        json={
            "code": "GRADE_2",
            "name": "二级",
            "parent_item_id": parent.json()["id"],
        },
    )
    assert invalid_parent.status_code == 422
    assert invalid_parent.json()["code"] == "DICTIONARY_ITEM_PARENT_INVALID"

    child = await business_client.post(
        f"/api/v1/configuration/dictionaries/{first['id']}/items",
        headers=_auth(admin_token),
        json={
            "code": "LEVEL_6_PRO",
            "name": "六级专业总",
            "parent_item_id": parent.json()["id"],
        },
    )
    assert child.status_code == 201
    assert child.json()["level"] == 1

    in_use = await business_client.post(
        f"/api/v1/configuration/dictionary-items/{parent.json()['id']}/deactivate",
        headers=_auth(admin_token),
        json={"reason": "合成数据验证"},
    )
    assert in_use.status_code == 409
    assert in_use.json()["code"] == "DICTIONARY_ITEM_IN_USE"

    deactivated = await business_client.post(
        f"/api/v1/configuration/dictionary-items/{child.json()['id']}/deactivate",
        headers=_auth(admin_token),
        json={"reason": "合成数据验证"},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    audit = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "configuration.item.deactivate",
            AuditLog.object_id == UUID(child.json()["id"]),
        )
    )
    assert audit is not None
    assert audit.reason == "合成数据验证"
    assert audit.trace_id == deactivated.headers["X-Trace-ID"]
    assert audit.before_payload["is_active"] is True
    assert audit.after_payload["is_active"] is False


async def test_configuration_routes_deny_unknown_scope_and_physical_delete(
    business_client: AsyncClient,
    admin_token: str,
    restricted_token: str,
) -> None:
    dictionary = await _create_dictionary(
        business_client,
        admin_token,
        code="EMPLOYEE_STATUS",
        name="人员状态",
    )

    denied = await business_client.get(
        "/api/v1/configuration/dictionaries",
        headers=_auth(restricted_token),
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "PERMISSION_DENIED"

    no_delete = await business_client.delete(
        f"/api/v1/configuration/dictionaries/{dictionary['id']}?request_id={uuid4()}",
        headers=_auth(admin_token),
    )
    assert no_delete.status_code == 405


async def test_dictionary_reparent_updates_descendant_levels_and_rejects_cycles(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    dictionary = await _create_dictionary(
        business_client,
        admin_token,
        code="JOB_FAMILY",
        name="职类",
    )

    ids: list[str] = []
    parent_id: str | None = None
    for code, name in (
        ("TECH", "技术"),
        ("BACKEND", "后端"),
        ("PYTHON", "Python"),
    ):
        response = await business_client.post(
            f"/api/v1/configuration/dictionaries/{dictionary['id']}/items",
            headers=_auth(admin_token),
            json={"code": code, "name": name, "parent_item_id": parent_id},
        )
        assert response.status_code == 201
        ids.append(response.json()["id"])
        parent_id = response.json()["id"]

    moved = await business_client.patch(
        f"/api/v1/configuration/dictionary-items/{ids[1]}",
        headers=_auth(admin_token),
        json={"parent_item_id": None},
    )
    assert moved.status_code == 200
    assert moved.json()["level"] == 0

    listed = await business_client.get(
        f"/api/v1/configuration/dictionaries/{dictionary['id']}/items",
        headers=_auth(admin_token),
    )
    levels = {item["id"]: item["level"] for item in listed.json()["items"]}
    assert levels[ids[2]] == 1

    cycle = await business_client.patch(
        f"/api/v1/configuration/dictionary-items/{ids[1]}",
        headers=_auth(admin_token),
        json={"parent_item_id": ids[2]},
    )
    assert cycle.status_code == 422
    assert cycle.json()["code"] == "DICTIONARY_ITEM_PARENT_INVALID"
