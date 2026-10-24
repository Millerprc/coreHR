# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""审批动作语义、状态机与流转历史的集成测试。

Requirement: D-095 — 撤销 = 终止、驳回 = 终止、退回 = 回到上一节点，三者不混用。

Requirement: D-108 — Wave 2a 拆包：审批动作的执行依赖私有包
`corehr_enterprise`（公开仓模式下 Demo 引擎统一拒绝写操作）。
因此**写路径**用例按「私有包是否可导入」跳过，断言没有削弱；
**读路径**用例（动作目录）在两种模式下都要跑。
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from enterprise_support import requires_enterprise
from hris.contracts.workflow import WorkflowTaskStatus
from hris.modules.workflow.models import WorkflowTask, WorkflowTransition


pytestmark = pytest.mark.asyncio


def _scheduler_types():
    """取私有包里的调度器类型（模块级导入会让公开仓模式在收集期报错）。"""

    from corehr_enterprise.workflow.scheduler import (
        WorkflowScheduler,
        WorkflowSchedulerSettings,
    )

    return WorkflowScheduler, WorkflowSchedulerSettings


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _approval_node(code: str, assignee_ref: str) -> dict:
    return {
        "code": code,
        "name": code,
        "node_type": "approval",
        "sign_mode": "any",
        "assignees": [{"assignee_type": "role", "assignee_ref": assignee_ref}],
    }


async def _start_instance(
    client: AsyncClient,
    token: str,
    *,
    code: str,
    nodes: list[dict],
    edges: list[dict],
) -> dict:
    definition = await client.post(
        "/api/v1/workflows/definitions",
        headers=_auth(token),
        json={
            "code": code,
            "name": f"合成{code}流程",
            "category": "synthetic",
            "nodes": nodes,
            "edges": edges,
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
    return started.json()


async def _instance_detail(
    client: AsyncClient,
    token: str,
    instance_id: str,
) -> dict:
    detail = await client.get(
        f"/api/v1/lifecycle/workflow-instances/{instance_id}",
        headers=_auth(token),
    )
    assert detail.status_code == 200, detail.text
    return detail.json()


async def _pending_task(
    client: AsyncClient,
    token: str,
    instance_id: str,
) -> dict:
    detail = await _instance_detail(client, token, instance_id)
    pending = [task for task in detail["tasks"] if task["status"] == "pending"]
    assert pending, detail
    return pending[0]


async def _transitions(
    client: AsyncClient,
    token: str,
    instance_id: str,
) -> list[dict]:
    listed = await client.get(
        f"/api/v1/lifecycle/workflow-instances/{instance_id}/transitions",
        headers=_auth(token),
    )
    assert listed.status_code == 200, listed.text
    return listed.json()["items"]


async def test_action_catalog_is_the_single_source_of_labels(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    catalog = await business_client.get(
        "/api/v1/lifecycle/workflow-actions",
        headers=_auth(admin_token),
    )
    assert catalog.status_code == 200, catalog.text
    items = {item["action"]: item for item in catalog.json()["actions"]}
    assert items["approve"]["label"] == "同意"
    assert items["reject"]["label"] == "驳回"
    assert items["rollback"]["label"] == "撤销"
    assert items["cancel"]["label"] == "取消"
    assert items["transfer"]["label"] == "转办"
    assert items["add_sign"]["label"] == "加签"
    assert items["return"]["label"] == "退回"
    # 撤销、驳回都是终止，但落到不同的实例终态；退回是回到上一节点。
    assert items["reject"]["terminal"] is True
    assert items["reject"]["instance_status"] == "rejected"
    assert items["rollback"]["terminal"] is True
    assert items["rollback"]["instance_status"] == "withdrawn"
    assert items["return"]["terminal"] is False
    assert items["return"]["instance_status"] == "returned"
    assert items["return"]["node_movement"] == "previous"
    assert items["rollback"]["node_movement"] == "terminate"
    # 状态文案同样只有一份来源。
    statuses = {item["status"]: item["label"] for item in catalog.json()["statuses"]}
    assert statuses["pending"] == "待处理"
    assert statuses["approved"] == "已同意"
    assert statuses["rejected"] == "已驳回"
    assert statuses["rolled_back"] == "已撤销"
    assert statuses["withdrawn"] == "已撤销"
    assert statuses["returned"] == "已退回"


@requires_enterprise
async def test_rollback_and_reject_use_distinct_terminal_states(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    nodes = [
        {"code": "START", "name": "开始", "node_type": "start"},
        _approval_node("APPROVE", "HR_ADMIN"),
        {"code": "END", "name": "结束", "node_type": "end"},
    ]
    edges = [
        {"source": "START", "target": "APPROVE"},
        {"source": "APPROVE", "target": "END"},
    ]

    rolled_back = await _start_instance(
        business_client,
        admin_token,
        code="SYNTHETIC_ROLLBACK",
        nodes=nodes,
        edges=edges,
    )
    rollback_task = await _pending_task(
        business_client, admin_token, rolled_back["id"]
    )
    rollback = await business_client.post(
        f"/api/v1/lifecycle/workflow-tasks/{rollback_task['id']}/rollback",
        headers=_auth(admin_token),
        json={"comment": "撤销这次审批"},
    )
    assert rollback.status_code == 200, rollback.text
    assert rollback.json()["status"] == "rolled_back"
    assert rollback.json()["decision"] == "rollback"
    rollback_detail = await _instance_detail(
        business_client, admin_token, rolled_back["id"]
    )
    assert rollback_detail["instance"]["status"] == "withdrawn"
    rollback_history = await _transitions(
        business_client, admin_token, rolled_back["id"]
    )
    assert len(rollback_history) == 1
    assert rollback_history[0]["action"] == "rollback"
    assert rollback_history[0]["action_label"] == "撤销"
    assert rollback_history[0]["from_status"] == "running"
    assert rollback_history[0]["to_status"] == "withdrawn"
    assert rollback_history[0]["from_node_code"] == "APPROVE"
    assert rollback_history[0]["to_node_code"] is None

    rejected = await _start_instance(
        business_client,
        admin_token,
        code="SYNTHETIC_REJECT",
        nodes=nodes,
        edges=edges,
    )
    reject_task = await _pending_task(business_client, admin_token, rejected["id"])
    reject = await business_client.post(
        f"/api/v1/lifecycle/workflow-tasks/{reject_task['id']}/reject",
        headers=_auth(admin_token),
        json={"comment": "驳回这次审批"},
    )
    assert reject.status_code == 200, reject.text
    assert reject.json()["status"] == "rejected"
    reject_detail = await _instance_detail(business_client, admin_token, rejected["id"])
    assert reject_detail["instance"]["status"] == "rejected"
    reject_history = await _transitions(business_client, admin_token, rejected["id"])
    assert len(reject_history) == 1
    assert reject_history[0]["action"] == "reject"
    assert reject_history[0]["action_label"] == "驳回"
    assert reject_history[0]["to_status"] == "rejected"
    # 撤销与驳回的终态、审计动作、文案三者都不相同。
    assert rollback_detail["instance"]["status"] != reject_detail["instance"]["status"]
    assert rollback_history[0]["action"] != reject_history[0]["action"]


@requires_enterprise
async def test_return_moves_flow_back_to_previous_approval_node(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    nodes = [
        {"code": "START", "name": "开始", "node_type": "start"},
        _approval_node("FIRST", "HR_ADMIN"),
        _approval_node("SECOND", "SSC_ADMIN"),
        {"code": "END", "name": "结束", "node_type": "end"},
    ]
    edges = [
        {"source": "START", "target": "FIRST"},
        {"source": "FIRST", "target": "SECOND"},
        {"source": "SECOND", "target": "END"},
    ]
    instance = await _start_instance(
        business_client,
        admin_token,
        code="SYNTHETIC_RETURN",
        nodes=nodes,
        edges=edges,
    )
    first_task = await _pending_task(business_client, admin_token, instance["id"])
    approved = await business_client.post(
        f"/api/v1/lifecycle/workflow-tasks/{first_task['id']}/approve",
        headers=_auth(admin_token),
        json={"comment": "先过第一节点"},
    )
    assert approved.status_code == 200, approved.text
    second_task = await _pending_task(business_client, admin_token, instance["id"])
    assert second_task["node_code"] == "SECOND"

    returned = await business_client.post(
        f"/api/v1/lifecycle/workflow-tasks/{second_task['id']}/return",
        headers=_auth(admin_token),
        json={"comment": "材料不全，退回上一节点"},
    )
    assert returned.status_code == 200, returned.text
    assert returned.json()["status"] == "returned"
    detail = await _instance_detail(business_client, admin_token, instance["id"])
    assert detail["instance"]["status"] == "returned"
    assert detail["instance"]["current_node_code"] == "FIRST"
    assert {task["status"] for task in detail["tasks"]} == {
        "approved",
        "returned",
        "pending",
    }
    history = await _transitions(business_client, admin_token, instance["id"])
    assert [item["action"] for item in history] == ["approve", "return"]
    assert history[1]["from_node_code"] == "SECOND"
    assert history[1]["to_node_code"] == "FIRST"
    assert history[1]["from_status"] == "running"
    assert history[1]["to_status"] == "returned"

    # 退回后的待办在上一节点，重新同意后流程继续推进。
    back_task = await _pending_task(business_client, admin_token, instance["id"])
    assert back_task["node_code"] == "FIRST"
    reapproved = await business_client.post(
        f"/api/v1/lifecycle/workflow-tasks/{back_task['id']}/approve",
        headers=_auth(admin_token),
        json={"comment": "补齐材料后重新同意"},
    )
    assert reapproved.status_code == 200, reapproved.text
    after = await _instance_detail(business_client, admin_token, instance["id"])
    assert after["instance"]["status"] == "running"
    assert after["instance"]["current_node_code"] == "SECOND"


@requires_enterprise
async def test_return_without_previous_approval_node_is_rejected(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    nodes = [
        {"code": "START", "name": "开始", "node_type": "start"},
        _approval_node("ONLY", "HR_ADMIN"),
        {"code": "END", "name": "结束", "node_type": "end"},
    ]
    edges = [
        {"source": "START", "target": "ONLY"},
        {"source": "ONLY", "target": "END"},
    ]
    instance = await _start_instance(
        business_client,
        admin_token,
        code="SYNTHETIC_RETURN_NO_TARGET",
        nodes=nodes,
        edges=edges,
    )
    task = await _pending_task(business_client, admin_token, instance["id"])
    returned = await business_client.post(
        f"/api/v1/lifecycle/workflow-tasks/{task['id']}/return",
        headers=_auth(admin_token),
        json={"comment": "没有上一节点可退"},
    )
    assert returned.status_code == 409, returned.text
    assert returned.json()["code"] == "WORKFLOW_RETURN_TARGET_UNAVAILABLE"


@requires_enterprise
async def test_transfer_and_add_sign_keep_the_node(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    nodes = [
        {"code": "START", "name": "开始", "node_type": "start"},
        _approval_node("APPROVE", "HR_ADMIN"),
        {"code": "END", "name": "结束", "node_type": "end"},
    ]
    edges = [
        {"source": "START", "target": "APPROVE"},
        {"source": "APPROVE", "target": "END"},
    ]
    instance = await _start_instance(
        business_client,
        admin_token,
        code="SYNTHETIC_REASSIGN",
        nodes=nodes,
        edges=edges,
    )
    task = await _pending_task(business_client, admin_token, instance["id"])

    transferred = await business_client.post(
        f"/api/v1/lifecycle/workflow-tasks/{task['id']}/transfer",
        headers=_auth(admin_token),
        json={
            "assignee_type": "role",
            "assignee_ref": "SSC_ADMIN",
            "comment": "转给共享中心",
        },
    )
    assert transferred.status_code == 200, transferred.text
    assert transferred.json()["status"] == "transferred"
    detail = await _instance_detail(business_client, admin_token, instance["id"])
    assert detail["instance"]["status"] == "running"
    assert detail["instance"]["current_node_code"] == "APPROVE"
    assert {task["status"] for task in detail["tasks"]} == {"transferred", "pending"}
    new_task = await _pending_task(business_client, admin_token, instance["id"])
    assert new_task["assignee_ref"] == "SSC_ADMIN"
    assert new_task["node_code"] == "APPROVE"

    added = await business_client.post(
        f"/api/v1/lifecycle/workflow-tasks/{new_task['id']}/add-sign",
        headers=_auth(admin_token),
        json={
            "assignee_type": "role",
            "assignee_ref": "HR_ADMIN",
            "comment": "加签一位",
        },
    )
    assert added.status_code == 200, added.text
    assert added.json()["status"] == "added_sign"
    history = await _transitions(business_client, admin_token, instance["id"])
    assert [item["action"] for item in history] == ["transfer", "add_sign"]
    assert history[0]["from_node_code"] == "APPROVE"
    assert history[0]["to_node_code"] == "APPROVE"
    assert history[1]["from_node_code"] == "APPROVE"
    assert history[1]["to_node_code"] == "APPROVE"


@requires_enterprise
async def test_illegal_transitions_return_conflict(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    nodes = [
        {"code": "START", "name": "开始", "node_type": "start"},
        _approval_node("APPROVE", "HR_ADMIN"),
        {"code": "END", "name": "结束", "node_type": "end"},
    ]
    edges = [
        {"source": "START", "target": "APPROVE"},
        {"source": "APPROVE", "target": "END"},
    ]
    instance = await _start_instance(
        business_client,
        admin_token,
        code="SYNTHETIC_ILLEGAL",
        nodes=nodes,
        edges=edges,
    )
    task = await _pending_task(business_client, admin_token, instance["id"])
    rolled_back = await business_client.post(
        f"/api/v1/lifecycle/workflow-tasks/{task['id']}/rollback",
        headers=_auth(admin_token),
        json={"comment": "撤销"},
    )
    assert rolled_back.status_code == 200, rolled_back.text

    # 实例已终止，不能再对同一任务做审批动作。
    again = await business_client.post(
        f"/api/v1/lifecycle/workflow-tasks/{task['id']}/approve",
        headers=_auth(admin_token),
        json={"comment": "终止后还想同意"},
    )
    assert again.status_code == 409, again.text
    assert again.json()["code"] == "WORKFLOW_TASK_STATUS_TRANSITION_INVALID"

    missing = await business_client.post(
        "/api/v1/lifecycle/workflow-tasks/00000000-0000-0000-0000-000000000000/approve",
        headers=_auth(admin_token),
        json={"comment": "不存在的任务"},
    )
    assert missing.status_code == 404, missing.text
    assert missing.json()["code"] == "WORKFLOW_TASK_NOT_FOUND"


@requires_enterprise
async def test_node_dwell_statistics_come_from_transition_history(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    nodes = [
        {"code": "START", "name": "开始", "node_type": "start"},
        _approval_node("FIRST", "HR_ADMIN"),
        _approval_node("SECOND", "SSC_ADMIN"),
        {"code": "END", "name": "结束", "node_type": "end"},
    ]
    edges = [
        {"source": "START", "target": "FIRST"},
        {"source": "FIRST", "target": "SECOND"},
        {"source": "SECOND", "target": "END"},
    ]
    instance = await _start_instance(
        business_client,
        admin_token,
        code="SYNTHETIC_DWELL",
        nodes=nodes,
        edges=edges,
    )
    first_task = await _pending_task(business_client, admin_token, instance["id"])
    await business_client.post(
        f"/api/v1/lifecycle/workflow-tasks/{first_task['id']}/approve",
        headers=_auth(admin_token),
        json={"comment": "过第一节点"},
    )
    second_task = await _pending_task(business_client, admin_token, instance["id"])
    await business_client.post(
        f"/api/v1/lifecycle/workflow-tasks/{second_task['id']}/return",
        headers=_auth(admin_token),
        json={"comment": "退回"},
    )
    back_task = await _pending_task(business_client, admin_token, instance["id"])
    await business_client.post(
        f"/api/v1/lifecycle/workflow-tasks/{back_task['id']}/approve",
        headers=_auth(admin_token),
        json={"comment": "重新过第一节点"},
    )

    dwell = await business_client.get(
        f"/api/v1/lifecycle/workflow-instances/{instance['id']}/node-dwell",
        headers=_auth(admin_token),
    )
    assert dwell.status_code == 200, dwell.text
    items = {item["node_code"]: item for item in dwell.json()["items"]}
    # 第一节点：进入一次、退回后重新进入一次。
    assert items["FIRST"]["visit_count"] == 2
    assert items["SECOND"]["visit_count"] == 2
    assert items["FIRST"]["average_duration_seconds"] >= 0
    assert items["FIRST"]["max_duration_seconds"] >= items["FIRST"]["average_duration_seconds"]
    assert items["FIRST"]["current"] is False
    assert items["SECOND"]["current"] is True

    filtered = await business_client.get(
        f"/api/v1/lifecycle/workflow-instances/{instance['id']}/node-dwell?node_code=FIRST",
        headers=_auth(admin_token),
    )
    assert filtered.status_code == 200, filtered.text
    assert [item["node_code"] for item in filtered.json()["items"]] == ["FIRST"]


@requires_enterprise
async def test_transition_history_is_append_only(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    nodes = [
        {"code": "START", "name": "开始", "node_type": "start"},
        _approval_node("APPROVE", "HR_ADMIN"),
        {"code": "END", "name": "结束", "node_type": "end"},
    ]
    edges = [
        {"source": "START", "target": "APPROVE"},
        {"source": "APPROVE", "target": "END"},
    ]
    instance = await _start_instance(
        business_client,
        admin_token,
        code="SYNTHETIC_APPEND_ONLY",
        nodes=nodes,
        edges=edges,
    )
    task = await _pending_task(business_client, admin_token, instance["id"])
    await business_client.post(
        f"/api/v1/lifecycle/workflow-tasks/{task['id']}/approve",
        headers=_auth(admin_token),
        json={"comment": "同意"},
    )
    history = await _transitions(business_client, admin_token, instance["id"])
    assert len(history) == 1
    transition_id = history[0]["id"]

    with pytest.raises(DBAPIError):
        async with db_session.begin_nested():
            await db_session.execute(
                text("UPDATE workflow_transitions SET comment = 'x' WHERE id = :id"),
                {"id": transition_id},
            )
    with pytest.raises(DBAPIError):
        async with db_session.begin_nested():
            await db_session.execute(
                text("DELETE FROM workflow_transitions WHERE id = :id"),
                {"id": transition_id},
            )


@requires_enterprise
async def test_scheduler_reminds_overdue_task_without_deciding(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
    test_engine: AsyncEngine,
) -> None:
    nodes = [
        {"code": "START", "name": "开始", "node_type": "start"},
        _approval_node("APPROVE", "HR_ADMIN"),
        {"code": "END", "name": "结束", "node_type": "end"},
    ]
    edges = [
        {"source": "START", "target": "APPROVE"},
        {"source": "APPROVE", "target": "END"},
    ]
    instance = await _start_instance(
        business_client,
        admin_token,
        code="SYNTHETIC_OVERDUE",
        nodes=nodes,
        edges=edges,
    )
    task = await _pending_task(business_client, admin_token, instance["id"])

    stored = await db_session.scalar(
        select(WorkflowTask).where(WorkflowTask.id == UUID(task["id"]))
    )
    assert stored is not None
    stored.created_at = datetime.now(UTC) - timedelta(minutes=120)
    await db_session.flush()

    WorkflowScheduler, WorkflowSchedulerSettings = _scheduler_types()
    settings = WorkflowSchedulerSettings(
        enabled=True,
        overdue_threshold_minutes=60,
        poll_interval_seconds=60,
        batch_size=50,
    )
    scheduler = WorkflowScheduler(
        session_factory=async_sessionmaker(test_engine, expire_on_commit=False),
        settings=settings,
    )
    reminded = await scheduler.remind_overdue_tasks(db_session)
    assert reminded == 1

    # 提醒不代替人工审批：任务仍是待办，实例仍是运行中。
    await db_session.refresh(stored)
    assert stored.status == WorkflowTaskStatus.PENDING.value
    assert stored.overdue_reminded_at is not None
    instance_row = await db_session.scalar(
        select(WorkflowTransition).where(
            WorkflowTransition.instance_id == UUID(instance["id"])
        )
    )
    assert instance_row is not None
    assert instance_row.action == "timeout_reminder"
    assert instance_row.actor_id is None
    assert instance_row.from_status == "running"
    assert instance_row.to_status == "running"

    # 同一任务不重复提醒。
    assert await scheduler.remind_overdue_tasks(db_session) == 0


@requires_enterprise
async def test_scheduler_skips_when_another_instance_holds_the_lock(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
    test_engine: AsyncEngine,
) -> None:
    nodes = [
        {"code": "START", "name": "开始", "node_type": "start"},
        _approval_node("APPROVE", "HR_ADMIN"),
        {"code": "END", "name": "结束", "node_type": "end"},
    ]
    edges = [
        {"source": "START", "target": "APPROVE"},
        {"source": "APPROVE", "target": "END"},
    ]
    await _start_instance(
        business_client,
        admin_token,
        code="SYNTHETIC_LOCK",
        nodes=nodes,
        edges=edges,
    )
    WorkflowScheduler, WorkflowSchedulerSettings = _scheduler_types()
    settings = WorkflowSchedulerSettings(
        enabled=True,
        overdue_threshold_minutes=60,
        poll_interval_seconds=60,
        batch_size=50,
    )
    # 当前事务持有 advisory lock：另一个连接的调度轮次必须直接跳过。
    acquired = await db_session.scalar(
        text("SELECT pg_try_advisory_xact_lock(:key)"),
        {"key": settings.advisory_lock_key},
    )
    assert acquired is True
    scheduler = WorkflowScheduler(
        session_factory=async_sessionmaker(test_engine, expire_on_commit=False),
        settings=settings,
    )
    assert await scheduler.run_once() == 0
