# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""审批动作与流程状态的**公开词表目录**。

Requirement: D-108 — 拆包后公开接口 `GET /api/v1/lifecycle/workflow-actions`
的返回形状必须保持不变（计划 §2.2：API 契约整体保持公开可读），
因此动作的中文标签、语义与「动作会落到哪个状态」的**描述**留在公开侧，
由这一份目录统一提供；前端不在本地另写一套映射。

这里的每一项都是**描述**（这份动作长什么样），不是**规则**
（这次流转到底允不允许、该走哪条线）。判定规则在私有包
`corehr_enterprise.workflow` 里，公开仓不留可独立算出业务结果的代码。
"""

from __future__ import annotations

from hris.contracts.workflow import (
    NODE_MOVEMENT_ADVANCE,
    NODE_MOVEMENT_PREVIOUS,
    NODE_MOVEMENT_STAY,
    NODE_MOVEMENT_TERMINATE,
    SYSTEM_WORKFLOW_ACTIONS,
    TERMINAL_WORKFLOW_ACTIONS,
    WORKFLOW_ACTION_LABELS,
    WORKFLOW_ACTION_SEMANTICS,
    WORKFLOW_INSTANCE_STATUS_LABELS,
    WORKFLOW_TASK_STATUS_LABELS,
    WorkflowAction,
    WorkflowActionDescriptor,
    WorkflowStatusDescriptor,
)


#: 每个动作的公开描述：`动作 → 任务终态 / 实例终态 / 节点位移`。
#:
#: 注意与私有包 `state_machine` 的分工：这里给的是**动作的对外语义描述**
#: （公开接口本来就返回它），私有包额外持有「允许的前置状态」与迁移表
#: （那才是判定规则）。
WORKFLOW_ACTION_DESCRIPTORS: dict[str, WorkflowActionDescriptor] = {
    WorkflowAction.APPROVE.value: WorkflowActionDescriptor(
        action=WorkflowAction.APPROVE.value,
        label=WORKFLOW_ACTION_LABELS[WorkflowAction.APPROVE.value],
        semantics=WORKFLOW_ACTION_SEMANTICS[WorkflowAction.APPROVE.value],
        terminal=WorkflowAction.APPROVE in TERMINAL_WORKFLOW_ACTIONS,
        system=WorkflowAction.APPROVE in SYSTEM_WORKFLOW_ACTIONS,
        node_movement=NODE_MOVEMENT_ADVANCE,
        task_status="approved",
        instance_status=None,
    ),
    WorkflowAction.REJECT.value: WorkflowActionDescriptor(
        action=WorkflowAction.REJECT.value,
        label=WORKFLOW_ACTION_LABELS[WorkflowAction.REJECT.value],
        semantics=WORKFLOW_ACTION_SEMANTICS[WorkflowAction.REJECT.value],
        terminal=WorkflowAction.REJECT in TERMINAL_WORKFLOW_ACTIONS,
        system=WorkflowAction.REJECT in SYSTEM_WORKFLOW_ACTIONS,
        node_movement=NODE_MOVEMENT_TERMINATE,
        task_status="rejected",
        instance_status="rejected",
    ),
    WorkflowAction.ROLLBACK.value: WorkflowActionDescriptor(
        action=WorkflowAction.ROLLBACK.value,
        label=WORKFLOW_ACTION_LABELS[WorkflowAction.ROLLBACK.value],
        semantics=WORKFLOW_ACTION_SEMANTICS[WorkflowAction.ROLLBACK.value],
        terminal=WorkflowAction.ROLLBACK in TERMINAL_WORKFLOW_ACTIONS,
        system=WorkflowAction.ROLLBACK in SYSTEM_WORKFLOW_ACTIONS,
        node_movement=NODE_MOVEMENT_TERMINATE,
        task_status="rolled_back",
        instance_status="withdrawn",
    ),
    WorkflowAction.CANCEL.value: WorkflowActionDescriptor(
        action=WorkflowAction.CANCEL.value,
        label=WORKFLOW_ACTION_LABELS[WorkflowAction.CANCEL.value],
        semantics=WORKFLOW_ACTION_SEMANTICS[WorkflowAction.CANCEL.value],
        terminal=WorkflowAction.CANCEL in TERMINAL_WORKFLOW_ACTIONS,
        system=WorkflowAction.CANCEL in SYSTEM_WORKFLOW_ACTIONS,
        node_movement=NODE_MOVEMENT_TERMINATE,
        task_status="cancelled",
        instance_status="cancelled",
    ),
    WorkflowAction.TRANSFER.value: WorkflowActionDescriptor(
        action=WorkflowAction.TRANSFER.value,
        label=WORKFLOW_ACTION_LABELS[WorkflowAction.TRANSFER.value],
        semantics=WORKFLOW_ACTION_SEMANTICS[WorkflowAction.TRANSFER.value],
        terminal=WorkflowAction.TRANSFER in TERMINAL_WORKFLOW_ACTIONS,
        system=WorkflowAction.TRANSFER in SYSTEM_WORKFLOW_ACTIONS,
        node_movement=NODE_MOVEMENT_STAY,
        task_status="transferred",
        instance_status=None,
    ),
    WorkflowAction.ADD_SIGN.value: WorkflowActionDescriptor(
        action=WorkflowAction.ADD_SIGN.value,
        label=WORKFLOW_ACTION_LABELS[WorkflowAction.ADD_SIGN.value],
        semantics=WORKFLOW_ACTION_SEMANTICS[WorkflowAction.ADD_SIGN.value],
        terminal=WorkflowAction.ADD_SIGN in TERMINAL_WORKFLOW_ACTIONS,
        system=WorkflowAction.ADD_SIGN in SYSTEM_WORKFLOW_ACTIONS,
        node_movement=NODE_MOVEMENT_STAY,
        task_status="added_sign",
        instance_status=None,
    ),
    WorkflowAction.RETURN.value: WorkflowActionDescriptor(
        action=WorkflowAction.RETURN.value,
        label=WORKFLOW_ACTION_LABELS[WorkflowAction.RETURN.value],
        semantics=WORKFLOW_ACTION_SEMANTICS[WorkflowAction.RETURN.value],
        terminal=WorkflowAction.RETURN in TERMINAL_WORKFLOW_ACTIONS,
        system=WorkflowAction.RETURN in SYSTEM_WORKFLOW_ACTIONS,
        node_movement=NODE_MOVEMENT_PREVIOUS,
        task_status="returned",
        instance_status="returned",
    ),
    WorkflowAction.TIMEOUT_REMINDER.value: WorkflowActionDescriptor(
        action=WorkflowAction.TIMEOUT_REMINDER.value,
        label=WORKFLOW_ACTION_LABELS[WorkflowAction.TIMEOUT_REMINDER.value],
        semantics=WORKFLOW_ACTION_SEMANTICS[WorkflowAction.TIMEOUT_REMINDER.value],
        terminal=WorkflowAction.TIMEOUT_REMINDER in TERMINAL_WORKFLOW_ACTIONS,
        system=WorkflowAction.TIMEOUT_REMINDER in SYSTEM_WORKFLOW_ACTIONS,
        node_movement=NODE_MOVEMENT_STAY,
        task_status=None,
        instance_status=None,
    ),
}


def action_catalog() -> list[WorkflowActionDescriptor]:
    """动作目录：动作取值、中文标签、语义与状态机落点（公开描述）。"""

    return list(WORKFLOW_ACTION_DESCRIPTORS.values())


def status_catalog() -> list[WorkflowStatusDescriptor]:
    """实例状态与任务状态的中文标签目录。"""

    return [
        WorkflowStatusDescriptor(status=status, label=label)
        for status, label in WORKFLOW_INSTANCE_STATUS_LABELS.items()
    ] + [
        WorkflowStatusDescriptor(status=status, label=label)
        for status, label in WORKFLOW_TASK_STATUS_LABELS.items()
    ]
