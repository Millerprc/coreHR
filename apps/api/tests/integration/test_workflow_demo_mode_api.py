# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""公开仓模式（没装私有包）的流程域行为。

Requirement: D-108 — 计划 §7 Wave 2 验收标准第 1 条：
「只 clone 公开仓 → `docker compose up` 正常起、UI 完整、**读接口可用**、
**写接口返回 `LICENSE_REQUIRED`**。」

本文件断言的正是这两件事：

- **读**：流程定义 / 实例 / 待办 / 流转历史 / 动作目录照常返回**真实数据库行**
  （Demo 引擎直查数据库，不做规则求解，也不返回假数据）；
- **写**：发起流程与全部审批动作统一返回 `403 / code=LICENSE_REQUIRED`，
  且错误体只含 `module / required / tier / contact_hint` 四个键，
  不泄露任何业务策略细节（计划 §7.1）。

数据用 ORM 直接落库（不走写接口）——公开仓模式下写接口本来就拒绝，
用写接口造数据会自相矛盾。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.licensing.errors import LICENSE_DETAIL_KEYS
from hris.modules.workflow.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowTask,
    WorkflowVersion,
)
from enterprise_support import requires_public_only


pytestmark = [pytest.mark.asyncio, requires_public_only]


SYNTHETIC_CODE = "SYNTHETIC_PUBLIC_ONLY"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_workflow_rows(db_session: AsyncSession) -> dict[str, str]:
    """直接落库造出「一条流程定义 + 一个运行中的实例 + 一条待办」。"""

    definition = WorkflowDefinition(
        code=SYNTHETIC_CODE,
        name="合成公开仓模式流程",
        category="synthetic",
        status="active",
        active_version=1,
        description=None,
    )
    db_session.add(definition)
    await db_session.flush()

    version = WorkflowVersion(
        workflow_definition_id=definition.id,
        version=1,
        status="active",
        definition={
            "nodes": [
                {"code": "START", "name": "开始", "node_type": "start"},
                {
                    "code": "APPROVE",
                    "name": "审批",
                    "node_type": "approval",
                    "sign_mode": "any",
                    "assignees": [
                        {"assignee_type": "role", "assignee_ref": "HR_ADMIN"}
                    ],
                },
                {"code": "END", "name": "结束", "node_type": "end"},
            ],
            "edges": [
                {"source": "START", "target": "APPROVE"},
                {"source": "APPROVE", "target": "END"},
            ],
        },
        change_reason="合成公开仓模式数据",
    )
    db_session.add(version)
    await db_session.flush()

    instance = WorkflowInstance(
        instance_number="W-PUBLIC-ONLY-0001",
        workflow_version_id=version.id,
        business_object_type="synthetic",
        business_object_id=uuid4(),
        status="running",
        current_node_code="APPROVE",
        started_by=None,
        started_at=datetime.now(UTC),
        completed_at=None,
        context={},
    )
    db_session.add(instance)
    await db_session.flush()

    task = WorkflowTask(
        workflow_instance_id=instance.id,
        node_code="APPROVE",
        sign_mode="any",
        assignee_type="role",
        assignee_ref="HR_ADMIN",
        status="pending",
        decision=None,
        comment=None,
        decided_by=None,
        decided_at=None,
        overdue_reminded_at=None,
    )
    db_session.add(task)
    await db_session.flush()

    return {
        "definition_id": str(definition.id),
        "version_id": str(version.id),
        "instance_id": str(instance.id),
        "task_id": str(task.id),
    }


async def test_read_endpoints_return_real_rows_in_public_mode(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """读接口在公开仓模式下照常返回真实数据库行。"""

    ids = await _seed_workflow_rows(db_session)
    headers = _auth(admin_token)

    definitions = await business_client.get(
        "/api/v1/workflows/definitions",
        headers=headers,
    )
    assert definitions.status_code == 200, definitions.text
    assert SYNTHETIC_CODE in {item["code"] for item in definitions.json()["items"]}

    detail = await business_client.get(
        f"/api/v1/workflows/definitions/{ids['definition_id']}",
        headers=headers,
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["definition"]["code"] == SYNTHETIC_CODE
    assert [item["version"] for item in detail.json()["versions"]] == [1]

    instances = await business_client.get(
        "/api/v1/lifecycle/workflow-instances",
        headers=headers,
    )
    assert instances.status_code == 200, instances.text
    assert ids["instance_id"] in {item["id"] for item in instances.json()["items"]}

    instance_detail = await business_client.get(
        f"/api/v1/lifecycle/workflow-instances/{ids['instance_id']}",
        headers=headers,
    )
    assert instance_detail.status_code == 200, instance_detail.text
    assert instance_detail.json()["instance"]["status"] == "running"
    assert [item["id"] for item in instance_detail.json()["tasks"]] == [ids["task_id"]]

    tasks = await business_client.get(
        "/api/v1/lifecycle/workflow-tasks?status=pending",
        headers=headers,
    )
    assert tasks.status_code == 200, tasks.text
    assert ids["task_id"] in {item["id"] for item in tasks.json()["items"]}

    transitions = await business_client.get(
        f"/api/v1/lifecycle/workflow-instances/{ids['instance_id']}/transitions",
        headers=headers,
    )
    assert transitions.status_code == 200, transitions.text
    assert transitions.json()["items"] == []

    dwell = await business_client.get(
        f"/api/v1/lifecycle/workflow-instances/{ids['instance_id']}/node-dwell",
        headers=headers,
    )
    assert dwell.status_code == 200, dwell.text
    assert dwell.json()["instance_id"] == ids["instance_id"]

    catalog = await business_client.get(
        "/api/v1/lifecycle/workflow-actions",
        headers=headers,
    )
    assert catalog.status_code == 200, catalog.text
    labels = {item["action"]: item["label"] for item in catalog.json()["actions"]}
    assert labels["approve"] == "同意"
    assert labels["reject"] == "驳回"


async def test_start_workflow_is_rejected_without_private_package(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """发起流程在公开仓模式下返回 LICENSE_REQUIRED。"""

    ids = await _seed_workflow_rows(db_session)
    response = await business_client.post(
        "/api/v1/lifecycle/workflow-instances",
        headers=_auth(admin_token),
        json={
            "workflow_definition_id": ids["definition_id"],
            "business_object_type": "synthetic",
            "business_object_id": str(uuid4()),
            "context": {},
        },
    )
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "LICENSE_REQUIRED"
    details = response.json()["details"]
    assert set(details) == set(LICENSE_DETAIL_KEYS)
    assert details["module"] == "workflow"
    assert details["required"] == "write"


async def test_all_workflow_task_actions_are_rejected_without_private_package(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """全部审批动作在公开仓模式下统一返回 LICENSE_REQUIRED。"""

    ids = await _seed_workflow_rows(db_session)
    task_id = ids["task_id"]
    headers = _auth(admin_token)

    cases = [
        ("approve", {"comment": "同意"}),
        ("reject", {"comment": "驳回"}),
        ("rollback", {"comment": "撤销"}),
        ("cancel", {"comment": "取消"}),
        ("transfer", {"assignee_type": "role", "assignee_ref": "SSC_ADMIN"}),
        ("add-sign", {"assignee_type": "role", "assignee_ref": "HR_ADMIN"}),
        ("return", {"comment": "退回"}),
        ("decision", {"decision": "approve", "comment": "兼容入口"}),
    ]
    for action, payload in cases:
        response = await business_client.post(
            f"/api/v1/lifecycle/workflow-tasks/{task_id}/{action}",
            headers=headers,
            json=payload,
        )
        assert response.status_code == 403, (action, response.text)
        body = response.json()
        assert body["code"] == "LICENSE_REQUIRED", (action, body)
        assert body["details"]["module"] == "workflow", (action, body)
        # 错误体不得泄露业务策略细节（计划 §7.1）。
        leaked = f"{body['message']} {body['details']}"
        for keyword in ("状态机", "选路", "条件", "迁移", "会签"):
            assert keyword not in leaked, (action, leaked)


async def test_publish_definition_stays_available_in_public_mode(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """流程定义的创作与发布属于配置面，公开仓模式仍然可用。

    Requirement: D-108 — 只读演示模式要让人「看得见全部功能」（D-108.4），
    因此定义创作 / 发布留在公开侧；被拒绝的是**执行审批流程**这一项能力。
    """

    ids = await _seed_workflow_rows(db_session)
    response = await business_client.post(
        f"/api/v1/lifecycle/workflows/{ids['definition_id']}/publish",
        headers=_auth(admin_token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "active"
