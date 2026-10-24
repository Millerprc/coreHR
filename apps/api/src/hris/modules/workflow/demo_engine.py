# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""流程引擎的**公开 Demo 实现**（社区版外壳）。

Requirement: D-108 — 计划 §7 拆包机制：
> `DemoWorkflowEngine` 的写方法统一抛 `LicenseRequiredError`；
> 读方法**直接查数据库**返回真实行，不做规则求解。

两条纪律：

1. **读路径与私有实现共用同一份查询代码**（`hris.modules.workflow.queries`），
   社区版与商业版读出来的数必须一致 —— 这是计划里被标为最高风险的一条。
   本文件因此**不自己写查询**，全部委托给 `queries`。
2. **写方法一律拒绝**，且只说「需要授权」，不泄露任何业务策略细节
   （错误文案边界见 `hris.core.licensing.errors` 与计划 §7.1）。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from hris.contracts.workflow import (
    NodeDwellStat,
    WorkflowActionDescriptor,
    WorkflowDecisionCommand,
    WorkflowStartCommand,
    WorkflowStatusDescriptor,
)
from hris.core.licensing.errors import LicenseRequiredError
from hris.modules.workflow import queries
from hris.modules.workflow.catalog import action_catalog, status_catalog
from hris.modules.workflow.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowTask,
    WorkflowTransition,
    WorkflowVersion,
)


#: 授权模块名（与 `hris.core.licensing.types.LICENSED_MODULES` 里的键一致）。
WORKFLOW_LICENSE_MODULE = "workflow"


class DemoWorkflowEngine:
    """只读演示模式的流程引擎外壳。

    - **读**：直通数据库，返回真实行（与商业版共用同一份查询代码）。
    - **写**：统一拒绝，抛 `LicenseRequiredError`（403 / `code=LICENSE_REQUIRED`）。

    公开仓里**不存在**任何能独立算出流程结果的代码：状态机判定、选路、
    任务分派都在私有包里，本类一个都没有。
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # 写：统一拒绝
    # ------------------------------------------------------------------

    def _reject_write(self, operation: str) -> LicenseRequiredError:
        """构造统一的拒绝错误。

        `operation` 只用于内部排查，**不进入响应体**（响应体只有
        module / required / tier / contact_hint 四个键，见 `LICENSE_DETAIL_KEYS`）。
        """

        del operation
        return LicenseRequiredError(
            module=WORKFLOW_LICENSE_MODULE,
            required="write",
        )

    async def start_workflow(
        self,
        command: WorkflowStartCommand,
    ) -> WorkflowInstance:
        del command
        raise self._reject_write("start_workflow")

    async def decide_task(
        self,
        task_id: UUID,
        command: WorkflowDecisionCommand,
    ) -> WorkflowTask:
        del task_id, command
        raise self._reject_write("decide_task")

    async def approve_task(
        self,
        task_id: UUID,
        comment: str | None = None,
    ) -> WorkflowTask:
        del task_id, comment
        raise self._reject_write("approve_task")

    async def reject_task(
        self,
        task_id: UUID,
        comment: str | None = None,
    ) -> WorkflowTask:
        del task_id, comment
        raise self._reject_write("reject_task")

    async def rollback_task(
        self,
        task_id: UUID,
        comment: str | None = None,
    ) -> WorkflowTask:
        del task_id, comment
        raise self._reject_write("rollback_task")

    async def cancel_task(
        self,
        task_id: UUID,
        comment: str | None = None,
    ) -> WorkflowTask:
        del task_id, comment
        raise self._reject_write("cancel_task")

    async def transfer_task(
        self,
        task_id: UUID,
        *,
        assignee_type: str,
        assignee_ref: str,
        comment: str | None = None,
    ) -> WorkflowTask:
        del task_id, assignee_type, assignee_ref, comment
        raise self._reject_write("transfer_task")

    async def add_sign_task(
        self,
        task_id: UUID,
        *,
        assignee_type: str,
        assignee_ref: str,
        comment: str | None = None,
    ) -> WorkflowTask:
        del task_id, assignee_type, assignee_ref, comment
        raise self._reject_write("add_sign_task")

    async def return_task(
        self,
        task_id: UUID,
        comment: str | None = None,
    ) -> WorkflowTask:
        del task_id, comment
        raise self._reject_write("return_task")

    # ------------------------------------------------------------------
    # 读：直通数据库（与商业版共用同一份查询代码）
    # ------------------------------------------------------------------

    async def list_definitions(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[WorkflowDefinition], int]:
        return await queries.list_definitions(
            self._session,
            limit=limit,
            offset=offset,
        )

    async def get_definition_detail(
        self,
        definition_id: UUID,
    ) -> tuple[WorkflowDefinition, list[WorkflowVersion]]:
        return await queries.get_definition_detail(self._session, definition_id)

    async def list_instances(
        self,
        *,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[WorkflowInstance], int]:
        return await queries.list_instances(
            self._session,
            status=status,
            limit=limit,
            offset=offset,
        )

    async def get_instance_detail(
        self,
        instance_id: UUID,
    ) -> tuple[WorkflowInstance, list[WorkflowTask]]:
        return await queries.get_instance_detail(self._session, instance_id)

    async def list_tasks(
        self,
        *,
        status: str | None,
        assignee_ref: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[WorkflowTask], int]:
        return await queries.list_tasks(
            self._session,
            status=status,
            assignee_ref=assignee_ref,
            limit=limit,
            offset=offset,
        )

    async def list_transitions(
        self,
        instance_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[WorkflowTransition], int]:
        return await queries.list_transitions(
            self._session,
            instance_id,
            limit=limit,
            offset=offset,
        )

    async def get_node_dwell(
        self,
        instance_id: UUID,
        *,
        node_code: str | None = None,
    ) -> tuple[WorkflowInstance, list[NodeDwellStat]]:
        return await queries.get_node_dwell(
            self._session,
            instance_id,
            node_code=node_code,
        )

    def action_catalog(self) -> list[WorkflowActionDescriptor]:
        return action_catalog()

    def status_catalog(self) -> list[WorkflowStatusDescriptor]:
        return status_catalog()
