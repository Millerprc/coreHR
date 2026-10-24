# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

from datetime import datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.workforce.organization_models import OrganizationEvent


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _command(expected_version: int = 1) -> dict[str, object]:
    return {
        "expected_version": expected_version,
        "idempotency_key": str(uuid4()),
        "change_reason": "合成组织树时点测试",
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
    assert response.status_code == 201, response.text
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


def _flatten(nodes: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    """把组织树拍平成「编码 -> 节点 + 上级编码」，便于比较两个时点的结构差异。"""
    flattened: dict[str, dict[str, object]] = {}

    def visit(items: list[dict[str, object]], parent_code: str | None) -> None:
        for node in items:
            code = str(node["code"])
            flattened[code] = {**node, "parent_code": parent_code}
            visit(node["children"], code)

    visit(nodes, None)
    return flattened


async def test_organization_tree_as_of_renders_historical_structure(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    """Requirement: D-103 — 历史时点的组织树按生效日期切片，与当前树结果不同。"""
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    group_type = await _create_type(business_client, admin_token, "GROUP", "集团")
    department_type = await _create_type(business_client, admin_token, "DEPARTMENT", "部门")

    group = await _create_organization(
        business_client,
        admin_token,
        name="合成集团",
        organization_type_id=str(group_type["id"]),
        effective_from=(today - timedelta(days=10)).isoformat(),
    )
    department = await _create_organization(
        business_client,
        admin_token,
        name="合成部门",
        organization_type_id=str(department_type["id"]),
        parent_organization_id=str(group["id"]),
        effective_from=(today - timedelta(days=10)).isoformat(),
    )

    renamed = await business_client.post(
        f"/api/v1/organizations/{group['id']}/versions",
        headers=_auth(admin_token),
        json={
            "name": "合成集团历史名称",
            "organization_type_id": group["organization_type_id"],
            "parent_organization_id": None,
            "country_code": "CN",
            "status": "active",
            "effective_date": (today - timedelta(days=5)).isoformat(),
            "command": _command(),
        },
    )
    assert renamed.status_code == 201, renamed.text
    assert renamed.json()["status"] == "applied"

    late_department = await _create_organization(
        business_client,
        admin_token,
        name="合成后设部门",
        organization_type_id=str(department_type["id"]),
        parent_organization_id=str(group["id"]),
        effective_from=(today - timedelta(days=3)).isoformat(),
    )

    current = await business_client.get(
        "/api/v1/organizations/tree",
        headers=_auth(admin_token),
    )
    assert current.status_code == 200, current.text
    current_nodes = _flatten(current.json())
    assert current_nodes[group["code"]]["name"] == "合成集团历史名称"
    assert current_nodes[department["code"]]["parent_code"] == group["code"]
    assert current_nodes[late_department["code"]]["parent_code"] == group["code"]

    historical = await business_client.get(
        f"/api/v1/organizations/tree?as_of={(today - timedelta(days=8)).isoformat()}",
        headers=_auth(admin_token),
    )
    assert historical.status_code == 200, historical.text
    historical_nodes = _flatten(historical.json())
    # 改名在该时点尚未生效，组织名称仍是登记名称。
    assert historical_nodes[group["code"]]["name"] == "合成集团"
    assert historical_nodes[department["code"]]["parent_code"] == group["code"]
    # 后设部门在该时点还不存在，时点组织树不包含它。
    assert late_department["code"] not in historical_nodes
    # 切片生效：历史时点与当前树的组织架构结果不同。
    assert historical.json() != current.json()

    between = await business_client.get(
        f"/api/v1/organizations/tree?as_of={(today - timedelta(days=2)).isoformat()}",
        headers=_auth(admin_token),
    )
    assert between.status_code == 200, between.text
    between_nodes = _flatten(between.json())
    assert between_nodes[group["code"]]["name"] == "合成集团历史名称"
    assert late_department["code"] in between_nodes


async def test_organization_tree_as_of_applies_effective_events(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """Requirement: D-103 — 生效事件口径：生效日期 ≤ as_of 的事件即计入时点组织树。"""
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    group_type = await _create_type(business_client, admin_token, "GROUP", "集团")
    group = await _create_organization(
        business_client,
        admin_token,
        name="合成集团",
        organization_type_id=str(group_type["id"]),
        effective_from=(today - timedelta(days=10)).isoformat(),
    )

    # 直接落一条尚未落成版本行的版本变更事件，模拟「事件已到期但尚未被应用」。
    db_session.add(
        OrganizationEvent(
            organization_id=UUID(str(group["id"])),
            event_type="VERSION_CHANGE",
            effective_date=today - timedelta(days=4),
            status="planned",
            payload={
                "name": "合成集团事件名称",
                "organization_type_id": group["organization_type_id"],
                "parent_organization_id": None,
                "country_code": "CN",
                "status": "active",
            },
            expected_version=1,
            idempotency_key=uuid4(),
            change_reason="合成事件时点测试",
        )
    )
    await db_session.flush()

    after_event = await business_client.get(
        f"/api/v1/organizations/tree?as_of={(today - timedelta(days=2)).isoformat()}",
        headers=_auth(admin_token),
    )
    assert after_event.status_code == 200, after_event.text
    assert _flatten(after_event.json())[group["code"]]["name"] == "合成集团事件名称"

    before_event = await business_client.get(
        f"/api/v1/organizations/tree?as_of={(today - timedelta(days=6)).isoformat()}",
        headers=_auth(admin_token),
    )
    assert before_event.status_code == 200, before_event.text
    assert _flatten(before_event.json())[group["code"]]["name"] == "合成集团"


async def test_organization_tree_without_as_of_returns_current_tree(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    """Requirement: D-103 — 不传 as_of 时返回当前树，且与 as_of=当天 完全一致。"""
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    group_type = await _create_type(business_client, admin_token, "GROUP", "集团")
    department_type = await _create_type(business_client, admin_token, "DEPARTMENT", "部门")
    group = await _create_organization(
        business_client,
        admin_token,
        name="合成集团",
        organization_type_id=str(group_type["id"]),
        effective_from=today.isoformat(),
    )
    await _create_organization(
        business_client,
        admin_token,
        name="合成部门",
        organization_type_id=str(department_type["id"]),
        parent_organization_id=str(group["id"]),
        effective_from=today.isoformat(),
    )

    default_tree = await business_client.get(
        "/api/v1/organizations/tree",
        headers=_auth(admin_token),
    )
    today_tree = await business_client.get(
        f"/api/v1/organizations/tree?as_of={today.isoformat()}",
        headers=_auth(admin_token),
    )
    assert default_tree.status_code == 200, default_tree.text
    assert today_tree.status_code == 200, today_tree.text
    assert default_tree.json() == today_tree.json()
    default_nodes = _flatten(default_tree.json())
    assert default_nodes[group["code"]]["name"] == "合成集团"


async def test_organization_tree_as_of_rejects_future_and_invalid_dates(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    """Requirement: D-013 / D-103 — 只允许当前与历史时点，非法日期返回 422。"""
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    tomorrow = today + timedelta(days=1)

    future = await business_client.get(
        f"/api/v1/organizations/tree?as_of={tomorrow.isoformat()}",
        headers=_auth(admin_token),
    )
    assert future.status_code == 422, future.text
    assert future.json()["code"] == "CURRENT_OR_HISTORY_TREE_ONLY"
    assert future.json()["message"] == "只支持查看当前与历史时点的组织架构"

    invalid_date = await business_client.get(
        "/api/v1/organizations/tree?as_of=2026-13-45",
        headers=_auth(admin_token),
    )
    assert invalid_date.status_code == 422, invalid_date.text
    assert invalid_date.json()["code"] == "REQUEST_VALIDATION_FAILED"

    not_a_date = await business_client.get(
        "/api/v1/organizations/tree?as_of=not-a-date",
        headers=_auth(admin_token),
    )
    assert not_a_date.status_code == 422, not_a_date.text
    assert not_a_date.json()["code"] == "REQUEST_VALIDATION_FAILED"


async def test_organization_tree_as_of_without_effective_organization_is_empty(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    """Requirement: D-103 — 该时点没有有效组织时返回空树，而不是报错。"""
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    group_type = await _create_type(business_client, admin_token, "GROUP", "集团")
    await _create_organization(
        business_client,
        admin_token,
        name="合成集团",
        organization_type_id=str(group_type["id"]),
        effective_from=today.isoformat(),
    )

    empty = await business_client.get(
        f"/api/v1/organizations/tree?as_of={(today - timedelta(days=30)).isoformat()}",
        headers=_auth(admin_token),
    )
    assert empty.status_code == 200, empty.text
    assert empty.json() == []
