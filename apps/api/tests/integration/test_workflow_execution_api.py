from uuid import uuid4

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_and_start(
    client: AsyncClient,
    token: str,
    *,
    code: str,
    sign_mode: str,
) -> dict:
    definition = await client.post(
        "/api/v1/workflows/definitions",
        headers=_auth(token),
        json={
            "code": code,
            "name": f"合成{sign_mode}流程",
            "category": "synthetic",
            "nodes": [
                {"code": "START", "name": "开始", "node_type": "start"},
                {
                    "code": "APPROVE",
                    "name": "审批",
                    "node_type": "approval",
                    "sign_mode": sign_mode,
                    "assignees": [
                        {"assignee_type": "role", "assignee_ref": "HR_ADMIN"},
                        {"assignee_type": "role", "assignee_ref": "SSC_ADMIN"},
                    ],
                },
                {"code": "END", "name": "结束", "node_type": "end"},
            ],
            "edges": [
                {"source": "START", "target": "APPROVE"},
                {"source": "APPROVE", "target": "END"},
            ],
            "change_reason": "合成流程测试",
        },
    )
    assert definition.status_code == 201, definition.text
    published = await client.post(
        f"/api/v1/lifecycle/workflows/{definition.json()['id']}/publish",
        headers=_auth(token),
    )
    assert published.status_code == 200, published.text
    started = await client.post(
        "/api/v1/lifecycle/workflow-instances",
        headers=_auth(token),
        json={
            "workflow_definition_id": definition.json()["id"],
            "business_object_type": "synthetic",
            "business_object_id": str(uuid4()),
            "context": {},
        },
    )
    assert started.status_code == 201, started.text
    assert started.json()["status"] == "running"
    assert started.json()["current_node_code"] == "APPROVE"
    detail = await client.get(
        f"/api/v1/lifecycle/workflow-instances/{started.json()['id']}",
        headers=_auth(token),
    )
    assert detail.status_code == 200
    assert len(detail.json()["tasks"]) == 2
    return detail.json()


async def test_any_and_all_sign_modes_advance_deterministically(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    any_detail = await _create_and_start(
        business_client,
        admin_token,
        code="SYNTHETIC_ANY",
        sign_mode="any",
    )
    first_any_task = any_detail["tasks"][0]
    any_decision = await business_client.post(
        f"/api/v1/lifecycle/workflow-tasks/{first_any_task['id']}/decision",
        headers=_auth(admin_token),
        json={"decision": "approve", "comment": "任一通过"},
    )
    assert any_decision.status_code == 200, any_decision.text
    any_after = await business_client.get(
        f"/api/v1/lifecycle/workflow-instances/{any_detail['instance']['id']}",
        headers=_auth(admin_token),
    )
    assert any_after.json()["instance"]["status"] == "completed"
    assert {task["status"] for task in any_after.json()["tasks"]} == {"completed", "cancelled"}

    all_detail = await _create_and_start(
        business_client,
        admin_token,
        code="SYNTHETIC_ALL",
        sign_mode="all",
    )
    for index, task in enumerate(all_detail["tasks"]):
        decision = await business_client.post(
            f"/api/v1/lifecycle/workflow-tasks/{task['id']}/decision",
            headers=_auth(admin_token),
            json={"decision": "approve", "comment": f"会签{index + 1}"},
        )
        assert decision.status_code == 200, decision.text
        detail = await business_client.get(
            f"/api/v1/lifecycle/workflow-instances/{all_detail['instance']['id']}",
            headers=_auth(admin_token),
        )
        expected = "running" if index == 0 else "completed"
        assert detail.json()["instance"]["status"] == expected


async def test_context_conditions_select_one_route_or_default(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    definition = await business_client.post(
        "/api/v1/workflows/definitions",
        headers=_auth(admin_token),
        json={
            "code": "SYNTHETIC_CONDITIONAL",
            "name": "合成条件分支流程",
            "category": "synthetic",
            "nodes": [
                {"code": "START", "name": "开始", "node_type": "start"},
                {
                    "code": "HIGH_APPROVE",
                    "name": "高额审批",
                    "node_type": "approval",
                    "sign_mode": "any",
                    "assignees": [{"assignee_type": "role", "assignee_ref": "HR_ADMIN"}],
                },
                {
                    "code": "STANDARD_APPROVE",
                    "name": "标准审批",
                    "node_type": "approval",
                    "sign_mode": "any",
                    "assignees": [{"assignee_type": "role", "assignee_ref": "SSC_ADMIN"}],
                },
                {"code": "END", "name": "结束", "node_type": "end"},
            ],
            "edges": [
                {
                    "source": "START",
                    "target": "HIGH_APPROVE",
                    "condition": {
                        "mode": "all",
                        "rules": [
                            {"path": "amount", "operator": "gte", "value": 10000},
                            {"path": "country_code", "operator": "in", "value": ["CN", "SG"]},
                        ],
                    },
                },
                {"source": "START", "target": "STANDARD_APPROVE"},
                {"source": "HIGH_APPROVE", "target": "END"},
                {"source": "STANDARD_APPROVE", "target": "END"},
            ],
            "change_reason": "验证条件路由",
        },
    )
    assert definition.status_code == 201, definition.text
    published = await business_client.post(
        f"/api/v1/lifecycle/workflows/{definition.json()['id']}/publish",
        headers=_auth(admin_token),
    )
    assert published.status_code == 200, published.text

    high = await business_client.post(
        "/api/v1/lifecycle/workflow-instances",
        headers=_auth(admin_token),
        json={
            "workflow_definition_id": definition.json()["id"],
            "business_object_type": "synthetic",
            "business_object_id": str(uuid4()),
            "context": {"amount": 20000, "country_code": "CN"},
        },
    )
    assert high.status_code == 201, high.text
    assert high.json()["current_node_code"] == "HIGH_APPROVE"
    assert high.json()["context"]["_workflow_route_history"][0] == {
        "source": "START",
        "target": "HIGH_APPROVE",
        "strategy": "condition",
    }

    standard = await business_client.post(
        "/api/v1/lifecycle/workflow-instances",
        headers=_auth(admin_token),
        json={
            "workflow_definition_id": definition.json()["id"],
            "business_object_type": "synthetic",
            "business_object_id": str(uuid4()),
            "context": {"amount": 5000, "country_code": "CN"},
        },
    )
    assert standard.status_code == 201, standard.text
    assert standard.json()["current_node_code"] == "STANDARD_APPROVE"
    assert standard.json()["context"]["_workflow_route_history"][0]["strategy"] == "default"


async def test_condition_routes_fail_closed_when_multiple_edges_match(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    definition = await business_client.post(
        "/api/v1/workflows/definitions",
        headers=_auth(admin_token),
        json={
            "code": "SYNTHETIC_AMBIGUOUS",
            "name": "合成歧义条件流程",
            "category": "synthetic",
            "nodes": [
                {"code": "START", "name": "开始", "node_type": "start"},
                {"code": "A", "name": "审批A", "node_type": "approval", "sign_mode": "any"},
                {"code": "B", "name": "审批B", "node_type": "approval", "sign_mode": "any"},
                {"code": "END", "name": "结束", "node_type": "end"},
            ],
            "edges": [
                {
                    "source": "START",
                    "target": "A",
                    "condition": {"mode": "all", "rules": [{"path": "amount", "operator": "gte", "value": 10}]},
                },
                {
                    "source": "START",
                    "target": "B",
                    "condition": {"mode": "all", "rules": [{"path": "amount", "operator": "gt", "value": 5}]},
                },
                {"source": "A", "target": "END"},
                {"source": "B", "target": "END"},
            ],
            "change_reason": "验证歧义条件关闭",
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
            "business_object_type": "synthetic",
            "business_object_id": str(uuid4()),
            "context": {"amount": 20},
        },
    )
    assert started.status_code == 422, started.text
    assert started.json()["code"] == "WORKFLOW_ROUTE_AMBIGUOUS"
