# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""流程域的**共用查询代码**（公开仓侧）。

Requirement: D-108 — 计划 §3.2 第 3 条 / §7 拆包守则 2：
「Demo 读路径与私有实现读路径**共用同一查询代码**，只把『规则求解』抽走。
否则社区版读出来的数和商业版不一样，直接摧毁信任。」

因此本文件是**读路径的唯一来源**：
- 公开的 Demo 引擎（`hris.modules.workflow.demo_engine`）直接调用它；
- 私有包的企业引擎（`corehr_enterprise.workflow`）同样调用它。

两侧读出来的数必然一致——这不是巧合，是同一段代码。

本文件只做**取数**与**由历史推导统计**，不含任何规则判定
（迁移是否合法、条件是否满足、该走哪条线都不在这里）。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.contracts.workflow import NodeDwellStat
from hris.core.errors import ApiError
from hris.modules.workflow.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowTask,
    WorkflowTransition,
    WorkflowVersion,
)


async def list_definitions(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
) -> tuple[list[WorkflowDefinition], int]:
    """流程定义列表（分页 + 总数）。"""

    total = await session.scalar(select(func.count()).select_from(WorkflowDefinition))
    items = list(
        (
            await session.scalars(
                select(WorkflowDefinition)
                .order_by(WorkflowDefinition.code)
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )
    return items, total or 0


async def get_definition_detail(
    session: AsyncSession,
    definition_id: UUID,
) -> tuple[WorkflowDefinition, list[WorkflowVersion]]:
    """流程定义详情（含版本列表）。"""

    definition = await session.get(WorkflowDefinition, definition_id)
    if definition is None:
        raise ApiError(
            status_code=404,
            code="WORKFLOW_NOT_FOUND",
            message="workflow definition not found",
        )
    versions = list(
        (
            await session.scalars(
                select(WorkflowVersion)
                .where(WorkflowVersion.workflow_definition_id == definition_id)
                .order_by(WorkflowVersion.version.desc())
            )
        ).all()
    )
    return definition, versions


async def list_instances(
    session: AsyncSession,
    *,
    status: str | None,
    limit: int,
    offset: int,
) -> tuple[list[WorkflowInstance], int]:
    """流程实例列表（分页 + 总数）。"""

    filters = [WorkflowInstance.status == status] if status else []
    total = await session.scalar(
        select(func.count()).select_from(WorkflowInstance).where(*filters)
    )
    items = list(
        (
            await session.scalars(
                select(WorkflowInstance)
                .where(*filters)
                .order_by(WorkflowInstance.started_at.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )
    return items, total or 0


async def get_instance_detail(
    session: AsyncSession,
    instance_id: UUID,
) -> tuple[WorkflowInstance, list[WorkflowTask]]:
    """流程实例详情（含任务列表）。"""

    instance = await session.get(WorkflowInstance, instance_id)
    if instance is None:
        raise ApiError(
            status_code=404,
            code="WORKFLOW_INSTANCE_NOT_FOUND",
            message="流程实例不存在",
        )
    tasks = list(
        (
            await session.scalars(
                select(WorkflowTask)
                .where(WorkflowTask.workflow_instance_id == instance_id)
                .order_by(WorkflowTask.created_at, WorkflowTask.id)
            )
        ).all()
    )
    return instance, tasks


async def list_tasks(
    session: AsyncSession,
    *,
    status: str | None,
    assignee_ref: str | None,
    limit: int,
    offset: int,
) -> tuple[list[WorkflowTask], int]:
    """审批任务（待办）列表（分页 + 总数）。"""

    filters = []
    if status is not None:
        filters.append(WorkflowTask.status == status)
    if assignee_ref is not None:
        filters.append(WorkflowTask.assignee_ref == assignee_ref)
    total = await session.scalar(
        select(func.count()).select_from(WorkflowTask).where(*filters)
    )
    items = list(
        (
            await session.scalars(
                select(WorkflowTask)
                .where(*filters)
                .order_by(WorkflowTask.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )
    return items, total or 0


async def list_transitions(
    session: AsyncSession,
    instance_id: UUID,
    *,
    limit: int,
    offset: int,
) -> tuple[list[WorkflowTransition], int]:
    """流转历史（只追加）。"""

    instance = await session.get(WorkflowInstance, instance_id)
    if instance is None:
        raise ApiError(
            status_code=404,
            code="WORKFLOW_INSTANCE_NOT_FOUND",
            message="流程实例不存在",
        )
    filters = [WorkflowTransition.instance_id == instance_id]
    total = await session.scalar(
        select(func.count()).select_from(WorkflowTransition).where(*filters)
    )
    items = list(
        (
            await session.scalars(
                select(WorkflowTransition)
                .where(*filters)
                .order_by(WorkflowTransition.created_at, WorkflowTransition.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )
    return items, total or 0


async def list_instance_transitions(
    session: AsyncSession,
    instance_id: UUID,
) -> list[WorkflowTransition]:
    """某个实例的完整流转历史（节点停留统计用，不分页）。"""

    return list(
        (
            await session.scalars(
                select(WorkflowTransition)
                .where(WorkflowTransition.instance_id == instance_id)
                .order_by(WorkflowTransition.created_at, WorkflowTransition.id)
            )
        ).all()
    )


def compute_node_dwell(
    transitions: list[WorkflowTransition],
    *,
    started_at: datetime,
    current_node_code: str | None,
    now: datetime,
) -> list[NodeDwellStat]:
    """从流转历史推导每个节点的停留次数与停留时长。

    口径：
    - 进入节点 = 该流转的 `to_node_code`；离开节点 = 下一条 `from_node_code` 为该节点的流转。
    - 流程刚开始时进入的第一个节点，用实例创建时间作为进入时间。
    - 节点没被离开（流程仍停在该节点）时，按统计时刻计算时长，并标记 `current=True`。
    - 终止类流转（驳回 / 撤销 / 取消）的 `to_node_code` 为空，表示流程不再前进。

    这是**读路径的统计推导**，不是规则判定：它只解释「已经在数据库里的流转历史
    意味着什么」，不决定流程该怎么走。两侧引擎共用这一份实现。
    """

    durations: dict[str, list[float]] = {}
    open_entry: dict[str, datetime] = {}
    visit_count: dict[str, int] = {}

    def _enter(node_code: str, at: datetime) -> None:
        open_entry[node_code] = at
        visit_count[node_code] = visit_count.get(node_code, 0) + 1

    def _leave(node_code: str, at: datetime) -> None:
        entry = open_entry.pop(node_code, None)
        if entry is None:
            return
        durations.setdefault(node_code, []).append((at - entry).total_seconds())

    first_node = transitions[0].from_node_code if transitions else current_node_code
    if first_node:
        _enter(first_node, started_at)

    for transition in transitions:
        from_node = transition.from_node_code
        to_node = transition.to_node_code
        if from_node and from_node != to_node:
            _leave(from_node, transition.created_at)
        if to_node and to_node != from_node:
            _enter(to_node, transition.created_at)

    stats: list[NodeDwellStat] = []
    for node_code in sorted(visit_count):
        node_durations = list(durations.get(node_code, []))
        if node_code in open_entry:
            node_durations.append((now - open_entry[node_code]).total_seconds())
        total = sum(node_durations)
        count = len(node_durations)
        stats.append(
            NodeDwellStat(
                node_code=node_code,
                visit_count=visit_count[node_code],
                total_duration_seconds=round(total, 3),
                average_duration_seconds=round(total / count, 3) if count else 0.0,
                max_duration_seconds=round(max(node_durations), 3) if count else 0.0,
                current=node_code in open_entry,
            )
        )
    return stats


async def get_node_dwell(
    session: AsyncSession,
    instance_id: UUID,
    *,
    node_code: str | None = None,
) -> tuple[WorkflowInstance, list[NodeDwellStat]]:
    """节点停留统计（读路径）。"""

    instance = await session.get(WorkflowInstance, instance_id)
    if instance is None:
        raise ApiError(
            status_code=404,
            code="WORKFLOW_INSTANCE_NOT_FOUND",
            message="流程实例不存在",
        )
    transitions = await list_instance_transitions(session, instance_id)
    stats = compute_node_dwell(
        transitions,
        started_at=instance.started_at,
        current_node_code=instance.current_node_code,
        now=datetime.now(UTC),
    )
    if node_code:
        stats = [item for item in stats if item.node_code == node_code]
    return instance, stats
