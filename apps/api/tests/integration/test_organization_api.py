from datetime import datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.platform.governance_models import OutboxEvent
from hris.modules.workforce.models import AuditLog
from hris.modules.workforce.organization_models import OrganizationEvent


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _command(expected_version: int = 1) -> dict[str, object]:
    return {
        "expected_version": expected_version,
        "idempotency_key": str(uuid4()),
        "change_reason": "合成组织测试",
    }


async def _create_type(
    client: AsyncClient,
    token: str,
    code: str,
    name: str,
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/organization-types",
        headers=_auth(token),
        json={"code": code, "name": name},
    )
    assert response.status_code == 201
    return response.json()


async def _create_organization(
    client: AsyncClient,
    token: str,
    *,
    name: str,
    organization_type_id: str,
    effective_from: str,
    parent_organization_id: str | None = None,
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/organizations",
        headers=_auth(token),
        json={
            "name": name,
            "organization_type_id": organization_type_id,
            "parent_organization_id": parent_organization_id,
            "country_code": "CN",
            "effective_from": effective_from,
            "command": _command(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _find_parent_code(nodes: list[dict[str, object]], child_code: str) -> str | None:
    def visit(node: dict[str, object], parent_code: str | None) -> str | None:
        if node["code"] == child_code:
            return parent_code
        for child in node["children"]:
            result = visit(child, str(node["code"]))
            if result is not None:
                return result
        return None

    for node in nodes:
        result = visit(node, None)
        if result is not None:
            return result
    return None


async def test_organization_type_crud_and_permissions(
    business_client: AsyncClient,
    admin_token: str,
    restricted_token: str,
) -> None:
    group_type = await _create_type(
        business_client,
        admin_token,
        "GROUP",
        "集团",
    )
    duplicate = await business_client.post(
        "/api/v1/organization-types",
        headers=_auth(admin_token),
        json={"code": "GROUP", "name": "重复集团"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "ORGANIZATION_TYPE_CODE_CONFLICT"

    updated = await business_client.patch(
        f"/api/v1/organization-types/{group_type['id']}",
        headers=_auth(admin_token),
        json={"is_active": False, "change_reason": "合成停用测试"},
    )
    assert updated.status_code == 200
    assert updated.json()["code"] == "GROUP"
    assert updated.json()["is_active"] is False

    listed = await business_client.get(
        "/api/v1/organization-types",
        headers=_auth(restricted_token),
    )
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == group_type["id"]

    denied = await business_client.patch(
        f"/api/v1/organization-types/{group_type['id']}",
        headers=_auth(restricted_token),
        json={"is_active": False, "change_reason": "合成权限测试"},
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "PERMISSION_DENIED"


async def test_current_tree_future_detail_cycle_and_version_conflicts(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    tomorrow = today + timedelta(days=1)
    group_type = await _create_type(business_client, admin_token, "GROUP", "集团")
    bg_type = await _create_type(business_client, admin_token, "BG", "事业群")
    bu_type = await _create_type(business_client, admin_token, "BU", "事业部")
    await _create_type(business_client, admin_token, "DEPARTMENT", "部门")

    group = await _create_organization(
        business_client,
        admin_token,
        name="合成集团",
        organization_type_id=str(group_type["id"]),
        effective_from=today.isoformat(),
    )
    bg1 = await _create_organization(
        business_client,
        admin_token,
        name="合成事业群一",
        organization_type_id=str(bg_type["id"]),
        parent_organization_id=str(group["id"]),
        effective_from=today.isoformat(),
    )
    bu = await _create_organization(
        business_client,
        admin_token,
        name="合成事业部",
        organization_type_id=str(bu_type["id"]),
        parent_organization_id=str(bg1["id"]),
        effective_from=today.isoformat(),
    )
    bg2 = await _create_organization(
        business_client,
        admin_token,
        name="合成事业群二",
        organization_type_id=str(bg_type["id"]),
        parent_organization_id=str(group["id"]),
        effective_from=today.isoformat(),
    )
    assert [group["code"], bg1["code"], bu["code"], bg2["code"]] == [
        "000001",
        "000002",
        "000003",
        "000004",
    ]

    move_command = _command(expected_version=1)
    move_payload = {
        "name": bu["name"],
        "organization_type_id": bu["organization_type_id"],
        "parent_organization_id": bg2["id"],
        "country_code": "CN",
        "status": "active",
        "effective_date": tomorrow.isoformat(),
        "command": move_command,
    }
    scheduled = await business_client.post(
        f"/api/v1/organizations/{bu['id']}/versions",
        headers=_auth(admin_token),
        json=move_payload,
    )
    assert scheduled.status_code == 201, scheduled.text
    assert scheduled.json()["status"] == "planned"

    repeated = await business_client.post(
        f"/api/v1/organizations/{bu['id']}/versions",
        headers=_auth(admin_token),
        json=move_payload,
    )
    assert repeated.status_code == 201
    assert repeated.json()["id"] == scheduled.json()["id"]

    current_tree = await business_client.get(
        "/api/v1/organizations/tree",
        headers=_auth(admin_token),
    )
    assert current_tree.status_code == 200
    assert _find_parent_code(current_tree.json(), str(bu["code"])) == bg1["code"]

    future_detail = await business_client.get(
        f"/api/v1/organizations/{bu['id']}?effective_at={tomorrow.isoformat()}",
        headers=_auth(admin_token),
    )
    assert future_detail.status_code == 200
    assert future_detail.json()["parent_organization_code"] == bg2["code"]
    assert future_detail.json()["version"] == 2

    future_tree = await business_client.get(
        f"/api/v1/organizations/tree?effective_at={tomorrow.isoformat()}",
        headers=_auth(admin_token),
    )
    assert future_tree.status_code == 422
    assert future_tree.json()["code"] == "CURRENT_TREE_ONLY"

    stale_payload = {**move_payload, "command": _command(expected_version=1)}
    stale = await business_client.post(
        f"/api/v1/organizations/{bu['id']}/versions",
        headers=_auth(admin_token),
        json=stale_payload,
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "VERSION_CONFLICT"

    cycle = await business_client.post(
        f"/api/v1/organizations/{group['id']}/versions",
        headers=_auth(admin_token),
        json={
            "name": group["name"],
            "organization_type_id": group["organization_type_id"],
            "parent_organization_id": bu["id"],
            "country_code": "CN",
            "status": "active",
            "effective_date": tomorrow.isoformat(),
            "command": _command(expected_version=1),
        },
    )
    assert cycle.status_code == 409
    assert cycle.json()["code"] == "ORGANIZATION_CYCLE"

    legacy_bypass = await business_client.post(
        "/api/v1/workforce/organizations",
        headers=_auth(admin_token),
        json={"code": "888888"},
    )
    assert legacy_bypass.status_code == 404


async def test_apply_cancel_history_audit_and_outbox(
    business_client: AsyncClient,
    admin_token: str,
    restricted_token: str,
    db_session: AsyncSession,
) -> None:
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    tomorrow = today + timedelta(days=1)
    day_after = today + timedelta(days=2)
    group_type = await _create_type(business_client, admin_token, "GROUP", "集团")
    bg_type = await _create_type(business_client, admin_token, "BG", "事业群")
    bu_type = await _create_type(business_client, admin_token, "BU", "事业部")
    group = await _create_organization(
        business_client,
        admin_token,
        name="合成集团",
        organization_type_id=str(group_type["id"]),
        effective_from=today.isoformat(),
    )
    bg1 = await _create_organization(
        business_client,
        admin_token,
        name="合成事业群一",
        organization_type_id=str(bg_type["id"]),
        parent_organization_id=str(group["id"]),
        effective_from=today.isoformat(),
    )
    bg2 = await _create_organization(
        business_client,
        admin_token,
        name="合成事业群二",
        organization_type_id=str(bg_type["id"]),
        parent_organization_id=str(group["id"]),
        effective_from=today.isoformat(),
    )
    bu = await _create_organization(
        business_client,
        admin_token,
        name="合成事业部",
        organization_type_id=str(bu_type["id"]),
        parent_organization_id=str(bg1["id"]),
        effective_from=today.isoformat(),
    )

    client_code = await business_client.post(
        "/api/v1/organizations",
        headers=_auth(admin_token),
        json={
            "code": "999999",
            "name": "禁止指定编码",
            "organization_type_id": bu_type["id"],
            "effective_from": today.isoformat(),
            "command": _command(),
        },
    )
    assert client_code.status_code == 422
    assert client_code.json()["code"] == "REQUEST_VALIDATION_FAILED"

    scheduled = await business_client.post(
        f"/api/v1/organizations/{bu['id']}/versions",
        headers=_auth(admin_token),
        json={
            "name": bu["name"],
            "organization_type_id": bu["organization_type_id"],
            "parent_organization_id": bg2["id"],
            "country_code": "CN",
            "status": "active",
            "effective_date": tomorrow.isoformat(),
            "command": _command(expected_version=1),
        },
    )
    assert scheduled.status_code == 201

    denied_apply = await business_client.post(
        f"/api/v1/organization-events/apply-due?business_date={tomorrow.isoformat()}",
        headers=_auth(restricted_token),
    )
    assert denied_apply.status_code == 403
    assert denied_apply.json()["code"] == "PERMISSION_DENIED"

    applied = await business_client.post(
        f"/api/v1/organization-events/apply-due?business_date={tomorrow.isoformat()}",
        headers=_auth(admin_token),
    )
    assert applied.status_code == 200
    assert applied.json()["applied_count"] == 1

    historical = await business_client.get(
        f"/api/v1/organizations/{bu['id']}?effective_at={today.isoformat()}",
        headers=_auth(admin_token),
    )
    effective = await business_client.get(
        f"/api/v1/organizations/{bu['id']}?effective_at={tomorrow.isoformat()}",
        headers=_auth(admin_token),
    )
    assert historical.json()["parent_organization_code"] == bg1["code"]
    assert historical.json()["version"] == 1
    assert effective.json()["parent_organization_code"] == bg2["code"]
    assert effective.json()["version"] == 2

    second = await business_client.post(
        f"/api/v1/organizations/{bu['id']}/versions",
        headers=_auth(admin_token),
        json={
            "name": "合成事业部新名称",
            "organization_type_id": bu["organization_type_id"],
            "parent_organization_id": bg2["id"],
            "country_code": "CN",
            "status": "active",
            "effective_date": day_after.isoformat(),
            "command": _command(expected_version=2),
        },
    )
    assert second.status_code == 201

    cancelled = await business_client.post(
        f"/api/v1/organization-events/{second.json()['id']}/cancel",
        headers=_auth(admin_token),
        json=_command(expected_version=3),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    event = await db_session.scalar(
        select(OrganizationEvent).where(
            OrganizationEvent.id == UUID(scheduled.json()["id"])
        )
    )
    apply_audit = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "organization.version.apply",
            AuditLog.object_id == UUID(str(bu["id"])),
        )
    )
    outbox = await db_session.scalar(
        select(OutboxEvent).where(
            OutboxEvent.event_type == "organization.version.applied",
            OutboxEvent.aggregate_id == UUID(str(bu["id"])),
        )
    )
    assert event is not None and event.status == "applied"
    assert apply_audit is not None
    assert apply_audit.trace_id == applied.headers["X-Trace-ID"]
    assert outbox is not None
    assert set(outbox.payload) == {"organization_id", "event_id", "version"}
