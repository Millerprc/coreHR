# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""流程域的公开契约（Protocol + 契约 DTO）。

Requirement: D-108 — Wave 2a 拆包：公开仓只保留**契约**与**调用侧**，
流程引擎的规则求解实现（状态机判定 / 选路 / 任务分派 / 调度 / 通知）迁到私有包
`corehr_enterprise`。本文件是两侧唯一约定的接口形状。

拆包守则（计划 §7「拆包守则」）在本文件的落法：

1. **公开仓不得残留可独立算出业务结果的代码** → 本文件只有词表（动作取值、
   中文标签、状态取值）与接口签名，没有迁移表、没有条件求值、没有选路规则。
   这些判定规则在私有包 `corehr_enterprise.workflow` 里。
2. **Demo 读路径与私有实现读路径共用同一查询代码** → 读方法由两侧引擎共同调用
   `hris.modules.workflow.queries` 里的同一份查询函数；社区版与商业版读出来的
   数必然一致。
3. **不按目录切，按能力切** → 契约暴露的是「执行审批流程」这一项能力，
   不是整个目录。
4. **私有包走 pip 私有源** → 公开仓的 CI 不依赖私有源，只跑壳的测试。

**本文件不得引用私有包**（`corehr_enterprise`）：契约是公开的，实现是私有的。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from hris.modules.workflow.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowTask,
    WorkflowTransition,
    WorkflowVersion,
)


# --------------------------------------------------------------------------
# 词表：审批动作
# --------------------------------------------------------------------------
#
# 说明：动作取值、中文标签与语义属于**公开词表**（前端文案只有这一份来源），
# 与「动作会落到哪个状态」这类**规则**不是一回事——后者在私有包里。
# 公开词表不构成可独立算出业务结果的能力：没有迁移表、没有条件求值、
# 没有选路规则，拿到词表也推不出任何流程结果。


class WorkflowAction(str, Enum):
    """审批动作。

    终止类动作（驳回 / 撤销 / 取消）结束流程实例；退回把流程送回上一个审批节点；
    转办与加签只改变当前节点的办理人，不改变节点本身。
    `timeout_reminder` 是系统动作，只写提醒，不代替人工给出审批结论。
    """

    APPROVE = "approve"
    REJECT = "reject"
    ROLLBACK = "rollback"
    CANCEL = "cancel"
    TRANSFER = "transfer"
    ADD_SIGN = "add_sign"
    RETURN = "return"
    TIMEOUT_REMINDER = "timeout_reminder"


WORKFLOW_ACTION_LABELS: dict[str, str] = {
    WorkflowAction.APPROVE.value: "同意",
    WorkflowAction.REJECT.value: "驳回",
    WorkflowAction.ROLLBACK.value: "撤销",
    WorkflowAction.CANCEL.value: "取消",
    WorkflowAction.TRANSFER.value: "转办",
    WorkflowAction.ADD_SIGN.value: "加签",
    WorkflowAction.RETURN.value: "退回",
    WorkflowAction.TIMEOUT_REMINDER.value: "超时提醒",
}

WORKFLOW_ACTION_SEMANTICS: dict[str, str] = {
    WorkflowAction.APPROVE.value: "同意：当前任务通过，流程按连线推进到下一节点",
    WorkflowAction.REJECT.value: "驳回：终止流程，实例置为已驳回",
    WorkflowAction.ROLLBACK.value: "撤销：终止流程，实例置为已撤销",
    WorkflowAction.CANCEL.value: "取消：终止流程，实例置为已取消",
    WorkflowAction.TRANSFER.value: "转办：把当前任务改派给其他办理人，节点不变",
    WorkflowAction.ADD_SIGN.value: "加签：在当前节点追加审批人，节点不变",
    WorkflowAction.RETURN.value: "退回：回到上一个审批节点重新办理，实例置为已退回",
    WorkflowAction.TIMEOUT_REMINDER.value: "超时提醒：系统提示任务超时，不代替人工审批结论",
}

# Requirement: D-095 — 终止类动作各自落到不同的实例终态，撤销与驳回不可互相顶替。
TERMINAL_WORKFLOW_ACTIONS: frozenset[WorkflowAction] = frozenset(
    {
        WorkflowAction.REJECT,
        WorkflowAction.ROLLBACK,
        WorkflowAction.CANCEL,
    }
)

# 系统动作：由调度器产生，不代表任何人工审批结论。
SYSTEM_WORKFLOW_ACTIONS: frozenset[WorkflowAction] = frozenset(
    {WorkflowAction.TIMEOUT_REMINDER}
)


def workflow_action_label(action: str) -> str:
    """返回动作的中文标签；未知取值原样返回，避免静默吞掉脏数据。"""

    return WORKFLOW_ACTION_LABELS.get(action, action)


def workflow_action_semantics(action: str) -> str:
    """返回动作的语义说明；未知取值原样返回。"""

    return WORKFLOW_ACTION_SEMANTICS.get(action, action)


# 节点位移语义：实例带 current_node_code 的流转规则由动作规格里的 node_movement 决定。
NODE_MOVEMENT_ADVANCE = "advance"
NODE_MOVEMENT_STAY = "stay"
NODE_MOVEMENT_PREVIOUS = "previous"
NODE_MOVEMENT_TERMINATE = "terminate"


# --------------------------------------------------------------------------
# 词表：流程状态
# --------------------------------------------------------------------------


class WorkflowInstanceStatus(str, Enum):
    """流程实例状态。"""

    RUNNING = "running"
    RETURNED = "returned"
    COMPLETED = "completed"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    CANCELLED = "cancelled"


class WorkflowTaskStatus(str, Enum):
    """审批任务状态。"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"
    TRANSFERRED = "transferred"
    ADDED_SIGN = "added_sign"
    RETURNED = "returned"


# 中文标签同样只有一份来源，前端不在本地另写一套映射。
WORKFLOW_INSTANCE_STATUS_LABELS: dict[str, str] = {
    WorkflowInstanceStatus.RUNNING.value: "运行中",
    WorkflowInstanceStatus.RETURNED.value: "已退回",
    WorkflowInstanceStatus.COMPLETED.value: "已完成",
    WorkflowInstanceStatus.REJECTED.value: "已驳回",
    WorkflowInstanceStatus.WITHDRAWN.value: "已撤销",
    WorkflowInstanceStatus.CANCELLED.value: "已取消",
}

WORKFLOW_TASK_STATUS_LABELS: dict[str, str] = {
    WorkflowTaskStatus.PENDING.value: "待处理",
    WorkflowTaskStatus.APPROVED.value: "已同意",
    WorkflowTaskStatus.REJECTED.value: "已驳回",
    WorkflowTaskStatus.ROLLED_BACK.value: "已撤销",
    WorkflowTaskStatus.CANCELLED.value: "已取消",
    WorkflowTaskStatus.TRANSFERRED.value: "已转办",
    WorkflowTaskStatus.ADDED_SIGN.value: "已加签",
    WorkflowTaskStatus.RETURNED.value: "已退回",
}


def workflow_instance_status_label(status: str) -> str:
    """实例状态的中文标签；未知取值原样返回。"""

    return WORKFLOW_INSTANCE_STATUS_LABELS.get(status, status)


def workflow_task_status_label(status: str) -> str:
    """任务状态的中文标签；未知取值原样返回。"""

    return WORKFLOW_TASK_STATUS_LABELS.get(status, status)


# --------------------------------------------------------------------------
# 契约 DTO
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkflowActionDescriptor:
    """一个审批动作的**公开描述**（词表，不是规则）。

    字段与公开接口 `GET /api/v1/lifecycle/workflow-actions` 的返回项一一对应，
    保证拆包前后 API 契约不变（计划 §2.2：API 契约整体保持公开可读）。
    """

    action: str
    label: str
    semantics: str
    terminal: bool
    system: bool
    node_movement: str
    task_status: str | None
    instance_status: str | None


@dataclass(frozen=True)
class WorkflowStatusDescriptor:
    """一个流程状态的**公开描述**（词表）。"""

    status: str
    label: str


@dataclass(frozen=True)
class NodeDwellStat:
    """单个节点的停留统计（由流转历史推导，不另建统计表）。"""

    node_code: str
    visit_count: int
    total_duration_seconds: float
    average_duration_seconds: float
    max_duration_seconds: float
    current: bool


@dataclass(frozen=True)
class WorkflowStartCommand:
    """发起流程实例的命令（契约层不依赖任何 pydantic schema）。"""

    workflow_definition_id: UUID
    business_object_type: str
    business_object_id: UUID
    context: dict[str, Any]


@dataclass(frozen=True)
class WorkflowDecisionCommand:
    """兼容入口的审批决定（只接受同意 / 驳回）。"""

    decision: str
    comment: str | None = None


@runtime_checkable
class WorkflowBusinessObjectHandler(Protocol):
    """流程终态回写业务对象的回调。

    Requirement: D-108 — 引擎（可能在私有包里）负责流程语义，业务对象的落地
    仍在公开侧（人事事件 / 批量异动方案）。两侧用这一个回调衔接。
    """

    async def on_workflow_finished(
        self,
        instance: WorkflowInstance,
        *,
        approved: bool,
    ) -> None:
        """流程实例终止时回写业务对象。"""
        ...


# --------------------------------------------------------------------------
# 引擎契约
# --------------------------------------------------------------------------


@runtime_checkable
class WorkflowEngine(Protocol):
    """流程引擎契约。

    Requirement: D-108 — 公开仓的调用侧只认这一个接口：
    - **读方法**在两侧都必须返回**真实数据库行**（Demo 侧直查数据库，不做规则求解），
      并且两侧走**同一份查询代码**，保证社区版与商业版读出来的数一致；
    - **写方法**在 Demo 实现里一律抛 `LicenseRequiredError`（403 /
      `code=LICENSE_REQUIRED`），私有实现里才真正执行审批语义。
    """

    # ---- 读：流程定义 ----
    async def list_definitions(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[WorkflowDefinition], int]:
        """流程定义列表（分页 + 总数）。"""
        ...

    async def get_definition_detail(
        self,
        definition_id: UUID,
    ) -> tuple[WorkflowDefinition, list[WorkflowVersion]]:
        """流程定义详情（含版本列表）。"""
        ...

    # ---- 读：流程实例与任务 ----
    async def list_instances(
        self,
        *,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[WorkflowInstance], int]:
        """流程实例列表（分页 + 总数）。"""
        ...

    async def get_instance_detail(
        self,
        instance_id: UUID,
    ) -> tuple[WorkflowInstance, list[WorkflowTask]]:
        """流程实例详情（含任务列表）。"""
        ...

    async def list_tasks(
        self,
        *,
        status: str | None,
        assignee_ref: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[WorkflowTask], int]:
        """审批任务（待办）列表（分页 + 总数）。"""
        ...

    async def list_transitions(
        self,
        instance_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[WorkflowTransition], int]:
        """流转历史（只追加）。"""
        ...

    async def get_node_dwell(
        self,
        instance_id: UUID,
        *,
        node_code: str | None = None,
    ) -> tuple[WorkflowInstance, list[NodeDwellStat]]:
        """节点停留统计（由流转历史推导）。"""
        ...

    def action_catalog(self) -> list[WorkflowActionDescriptor]:
        """审批动作目录（公开词表）。"""
        ...

    def status_catalog(self) -> list[WorkflowStatusDescriptor]:
        """流程状态目录（公开词表）。"""
        ...

    # ---- 写：发起与审批动作 ----
    async def start_workflow(
        self,
        command: WorkflowStartCommand,
    ) -> WorkflowInstance:
        """发起流程实例。"""
        ...

    async def decide_task(
        self,
        task_id: UUID,
        command: WorkflowDecisionCommand,
    ) -> WorkflowTask:
        """兼容入口：只接受同意 / 驳回。"""
        ...

    async def approve_task(
        self,
        task_id: UUID,
        comment: str | None = None,
    ) -> WorkflowTask:
        """同意：当前任务通过，流程按连线推进到下一节点。"""
        ...

    async def reject_task(
        self,
        task_id: UUID,
        comment: str | None = None,
    ) -> WorkflowTask:
        """驳回：终止流程，实例落到「已驳回」。"""
        ...

    async def rollback_task(
        self,
        task_id: UUID,
        comment: str | None = None,
    ) -> WorkflowTask:
        """撤销：终止流程，实例落到「已撤销」。"""
        ...

    async def cancel_task(
        self,
        task_id: UUID,
        comment: str | None = None,
    ) -> WorkflowTask:
        """取消：终止流程，实例落到「已取消」。"""
        ...

    async def transfer_task(
        self,
        task_id: UUID,
        *,
        assignee_type: str,
        assignee_ref: str,
        comment: str | None = None,
    ) -> WorkflowTask:
        """转办：把当前任务改派给其他办理人，节点不变。"""
        ...

    async def add_sign_task(
        self,
        task_id: UUID,
        *,
        assignee_type: str,
        assignee_ref: str,
        comment: str | None = None,
    ) -> WorkflowTask:
        """加签：在当前节点追加审批人，节点不变。"""
        ...

    async def return_task(
        self,
        task_id: UUID,
        comment: str | None = None,
    ) -> WorkflowTask:
        """退回：回到上一个审批节点，实例落到「已退回」。"""
        ...
