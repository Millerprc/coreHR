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
