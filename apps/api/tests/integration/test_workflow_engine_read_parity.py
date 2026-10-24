# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""Demo 引擎与商业引擎的**读结果一致性**对比测试。

Requirement: D-108 — 计划 §3.2 第 3 条 / §7 拆包守则 2（被标为最高风险项）：
「Demo 读路径与私有实现读路径**共用同一查询代码**，只把『规则求解』抽走。
否则社区版读出来的数和商业版不一样，直接摧毁信任。」

ADR-0008 风险 2 的处置要求：「每个拆包波次加对比测试（同一数据集，
Demo 与 Enterprise 读出的行必须一致）」——本文件就是这个对比测试。

做法：同一批数据、同一个会话，分别用两个引擎读，逐项比对。
装上私有包时跑完整对比；没装私有包时只跑 Demo 侧（另一半由
`test_workflow_demo_mode_api.py` 覆盖）。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.workflow.demo_engine import DemoWorkflowEngine
from hris.modules.workflow.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowTask,
    WorkflowTransition,
    WorkflowVersion,
)


pytestmark = pytest.mark.asyncio


SYNTHETIC_CODE = "SYNTHETIC_READ_PARITY"


async def _seed(db_session: AsyncSession) -> dict[str, str]:
    definition = WorkflowDefinition(
        code=SYNTHETIC_CODE,
        name="合成读一致性流程",
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
        change_reason="合成读一致性数据",
    )
    db_session.add(version)
    await db_session.flush()

    instance = WorkflowInstance(
        instance_number="W-READ-PARITY-0001",
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

    transition = WorkflowTransition(
        instance_id=instance.id,
        from_node_code="START",
        to_node_code="APPROVE",
        action="approve",
        from_status="running",
        to_status="running",
        actor_id=None,
        comment=None,
        created_at=datetime.now(UTC),
    )
    db_session.add(transition)
    await db_session.flush()

    return {
        "definition_id": str(definition.id),
        "instance_id": str(instance.id),
        "task_id": str(task.id),
    }


def _rows(items: list) -> list[dict]:
    """把 ORM 行折成可比较的字典（只取对外可见字段）。"""

    return [
        {
            "id": str(item.id),
            "status": getattr(item, "status", None),
            "from_status": getattr(item, "from_status", None),
            "to_status": getattr(item, "to_status", None),
            "node_code": getattr(item, "node_code", None),
            "code": getattr(item, "code", None),
            "action": getattr(item, "action", None),
        }
        for item in items
    ]


def _dwell_shape(stats: list) -> list[tuple]:
    """节点停留统计的稳定字段（时长按统计时刻计算，两次取值必然不同，不参与比对）。"""

    return [(item.node_code, item.visit_count, item.current) for item in stats]


async def test_demo_engine_satisfies_the_public_contract() -> None:
    """公开壳必须满足公开契约（方法集合与契约一致）。"""

    from hris.contracts.workflow import WorkflowEngine

    assert isinstance(DemoWorkflowEngine(None), WorkflowEngine)


async def test_demo_engine_reads_real_rows(db_session: AsyncSession) -> None:
    """公开壳的读方法返回真实数据库行（不做规则求解，也不返回假数据）。"""

    ids = await _seed(db_session)
    instance_id = UUID(ids["instance_id"])
    engine = DemoWorkflowEngine(db_session)

    definitions, total = await engine.list_definitions(limit=50, offset=0)
    assert total >= 1
    assert SYNTHETIC_CODE in {item.code for item in definitions}

    definition, versions = await engine.get_definition_detail(
        UUID(ids["definition_id"])
    )
    assert definition.code == SYNTHETIC_CODE
    assert [item.version for item in versions] == [1]

    instances, _ = await engine.list_instances(status=None, limit=50, offset=0)
    assert ids["instance_id"] in {str(item.id) for item in instances}

    instance, tasks = await engine.get_instance_detail(instance_id)
    assert instance.status == "running"
    assert [str(item.id) for item in tasks] == [ids["task_id"]]

    task_items, _ = await engine.list_tasks(
        status="pending",
        assignee_ref=None,
        limit=50,
        offset=0,
    )
    assert ids["task_id"] in {str(item.id) for item in task_items}

    transitions, _ = await engine.list_transitions(
        instance_id,
        limit=50,
        offset=0,
    )
    assert [item.action for item in transitions] == ["approve"]

    _, dwell = await engine.get_node_dwell(instance_id)
    assert {item.node_code for item in dwell} == {"START", "APPROVE"}


async def test_demo_and_enterprise_engines_read_identical_rows(
    db_session: AsyncSession,
) -> None:
    """同一批数据，两个引擎读出的行必须完全一致。"""

    enterprise_module = pytest.importorskip(
        "corehr_enterprise.workflow",
        reason="需要私有包 corehr_enterprise 才能做两侧读结果对比",
    )
    enterprise_engine = enterprise_module.EnterpriseWorkflowEngine

    from hris.contracts.workflow import WorkflowEngine

    ids = await _seed(db_session)
    instance_id = UUID(ids["instance_id"])
    demo = DemoWorkflowEngine(db_session)
    enterprise = enterprise_engine(db_session)
    assert isinstance(enterprise, WorkflowEngine)

    demo_definitions, demo_total = await demo.list_definitions(limit=50, offset=0)
    enterprise_definitions, enterprise_total = await enterprise.list_definitions(
        limit=50,
        offset=0,
    )
    assert demo_total == enterprise_total
    assert _rows(demo_definitions) == _rows(enterprise_definitions)

    demo_instances, demo_instances_total = await demo.list_instances(
        status=None,
        limit=50,
        offset=0,
    )
    enterprise_instances, enterprise_instances_total = await enterprise.list_instances(
        status=None,
        limit=50,
        offset=0,
    )
    assert demo_instances_total == enterprise_instances_total
    assert _rows(demo_instances) == _rows(enterprise_instances)

    demo_tasks, demo_tasks_total = await demo.list_tasks(
        status="pending",
        assignee_ref=None,
        limit=50,
        offset=0,
    )
    enterprise_tasks, enterprise_tasks_total = await enterprise.list_tasks(
        status="pending",
        assignee_ref=None,
        limit=50,
        offset=0,
    )
    assert demo_tasks_total == enterprise_tasks_total
    assert _rows(demo_tasks) == _rows(enterprise_tasks)

    demo_transitions, demo_transitions_total = await demo.list_transitions(
        instance_id,
        limit=50,
        offset=0,
    )
    enterprise_transitions, enterprise_transitions_total = await (
        enterprise.list_transitions(
            instance_id,
            limit=50,
            offset=0,
        )
    )
    assert demo_transitions_total == enterprise_transitions_total
    assert _rows(demo_transitions) == _rows(enterprise_transitions)

    demo_instance, demo_dwell = await demo.get_node_dwell(instance_id)
    enterprise_instance, enterprise_dwell = await enterprise.get_node_dwell(instance_id)
    assert demo_instance.status == enterprise_instance.status
    assert _dwell_shape(demo_dwell) == _dwell_shape(enterprise_dwell)
