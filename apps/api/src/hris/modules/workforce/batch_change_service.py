# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""批量异动（方案制）的服务层。

方案头是 ``hr_event_batches`` 行，方案明细是挂在方案头上的 ``hr_events`` 行。
明细的校验口径、事件号与审批挂载全部复用现有人事事件能力，
差异只在于：明细先以草稿态存在，整批提交时才挂上同一个流程实例。
"""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.errors import ApiError
from hris.modules.platform.numbering import next_number
from hris.modules.workflow.extended_schemas import HrEventCreate, WorkflowInstanceCreate
from hris.modules.workflow.extended_service import LifecycleService
from hris.modules.workflow.models import WorkflowDefinition
from hris.modules.workforce.batch_change_models import (
    BATCH_CHANGE_BUSINESS_OBJECT_TYPE,
    BATCH_CHANGE_LINE_STATUS_DRAFT,
    BATCH_CHANGE_LINE_STATUS_PENDING_APPROVAL,
    BATCH_CHANGE_LINE_STATUS_READY,
    BATCH_CHANGE_LINE_STATUS_REJECTED,
    BATCH_CHANGE_MAX_LINES,
    BATCH_CHANGE_STATUS_APPROVED,
    BATCH_CHANGE_STATUS_DRAFT,
    BATCH_CHANGE_STATUS_REJECTED,
    BATCH_CHANGE_STATUS_SUBMITTED,
    BATCH_CHANGE_WORKFLOW_CODE,
    HrEventBatch,
)
from hris.modules.workforce.batch_change_schemas import (
    BatchChangeCreate,
    BatchChangeLineCreate,
    BatchChangeLinesCreate,
    BatchChangeSubmit,
)
from hris.modules.workforce.models import AuditLog, HrEvent


class BatchChangeService:
    """批量异动方案的创建、明细维护与整批提交审批。"""

    def __init__(self, session: AsyncSession, *, actor_id: UUID, trace_id: str) -> None:
        self._session = session
        self._actor_id = actor_id
        self._trace_id = trace_id
        self._lifecycle = LifecycleService(session, actor_id=actor_id, trace_id=trace_id)

    async def create_batch(self, payload: BatchChangeCreate) -> HrEventBatch:
        # Requirement: HR-BATCH-010 — 方案号沿用系统统一流水号规则；
        # 上限取 PostgreSQL 整数边界内的值，与既有长流水号序列保持一致。
        number = await next_number(
            self._session,
            sequence_code="HR_EVENT_BATCH_NUMBER",
            width=10,
            max_value=2_000_000_000,
            prefix="B",
        )
        batch = HrEventBatch(
            batch_number=number,
            title=payload.title,
            status=BATCH_CHANGE_STATUS_DRAFT,
            line_count=0,
            reason=payload.reason,
            created_by=self._actor_id,
        )
        self._session.add(batch)
        await self._session.flush()
        await self._session.refresh(batch)
        await self._audit(
            action="batch_change.create",
            object_id=batch.id,
            reason="创建批量异动方案",
            before={},
            after=self._batch_payload(batch),
        )
        return batch

    async def list_batches(
        self,
        *,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[HrEventBatch], int]:
        filters = []
        if status is not None:
            filters.append(HrEventBatch.status == status)
        total = await self._session.scalar(
            select(func.count()).select_from(HrEventBatch).where(*filters)
        )
        items = list(
            (
                await self._session.scalars(
                    select(HrEventBatch)
                    .where(*filters)
                    .order_by(HrEventBatch.created_at.desc(), HrEventBatch.id)
                    .limit(page_size)
                    .offset((page - 1) * page_size)
                )
            ).all()
        )
        return items, total or 0

    async def get_batch(self, batch_id: UUID) -> HrEventBatch:
        batch = await self._session.get(HrEventBatch, batch_id)
        if batch is None:
            raise ApiError(
                status_code=404,
                code="BATCH_CHANGE_NOT_FOUND",
                message="批量异动方案不存在",
            )
        return batch

    async def list_lines(self, batch_id: UUID) -> list[HrEvent]:
        # Requirement: HR-BATCH-004 — 明细按事件号排序，事件号沿用全局流水号，
        # 因此同一方案内的明细顺序与录入顺序一致。
        return list(
            (
                await self._session.scalars(
                    select(HrEvent)
                    .where(HrEvent.batch_id == batch_id)
                    .order_by(HrEvent.event_number)
                )
            ).all()
        )

    async def append_lines(
        self,
        batch_id: UUID,
        payload: BatchChangeLinesCreate,
    ) -> tuple[HrEventBatch, list[HrEvent], list[HrEvent]]:
        """追加明细，返回（方案、新建明细、幂等命中的既有明细）。"""
        batch = await self._get_draft_batch(batch_id)
        if not payload.lines:
            raise ApiError(
                status_code=422,
                code="BATCH_CHANGE_LINES_REQUIRED",
                message="至少需要一条异动明细",
            )
        current = await self._count_lines(batch.id)
        # Requirement: HR-BATCH-001 — 单个方案最多 1000 条明细，超限整批拒绝。
        if current + len(payload.lines) > BATCH_CHANGE_MAX_LINES:
            raise ApiError(
                status_code=422,
                code="BATCH_CHANGE_LINE_LIMIT_EXCEEDED",
                message=f"单个批量异动方案最多 {BATCH_CHANGE_MAX_LINES} 条明细",
                details=[
                    {
                        "field": "lines",
                        "message": (
                            f"当前方案已有 {current} 条明细，"
                            f"本次追加 {len(payload.lines)} 条，超过上限 {BATCH_CHANGE_MAX_LINES}"
                        ),
                    }
                ],
            )
        created: list[HrEvent] = []
        skipped: list[HrEvent] = []
        for line in payload.lines:
            existing = await self._resolve_existing_line(batch, line)
            if existing is not None:
                skipped.append(existing)
                continue
            created.append(await self._create_line(batch, line))
        await self._refresh_line_count(batch)
        await self._audit(
            action="batch_change.append_lines",
            object_id=batch.id,
            reason="追加批量异动明细",
            before={},
            after=self._batch_payload(batch)
            | {
                "created_count": len(created),
                "skipped_count": len(skipped),
            },
        )
        return batch, created, skipped

    async def remove_line(self, batch_id: UUID, line_id: UUID) -> None:
        """移除一条明细，只允许在草稿态操作。"""
        batch = await self._get_draft_batch(batch_id)
        line = await self._session.get(HrEvent, line_id)
        if line is None or line.batch_id != batch.id:
            raise ApiError(
                status_code=404,
                code="BATCH_CHANGE_LINE_NOT_FOUND",
                message="批量异动明细不存在",
            )
        before = self._line_payload(line)
        # Requirement: HR-BATCH-002 — 明细只在草稿态可删，删除后方案行数同步回落。
        await self._session.delete(line)
        await self._session.flush()
        await self._refresh_line_count(batch)
        await self._audit(
            action="batch_change.remove_line",
            object_id=batch.id,
            reason="移除批量异动明细",
            before=before,
            after=self._batch_payload(batch),
        )

    async def submit_batch(
        self,
        batch_id: UUID,
        payload: BatchChangeSubmit,
    ) -> HrEventBatch:
        """整批提交审批：只产生一个流程实例，全部明细共享它。"""
        batch = await self._get_draft_batch(batch_id)
        lines = await self.list_lines(batch.id)
        if not lines:
            raise ApiError(
                status_code=422,
                code="BATCH_CHANGE_EMPTY",
                message="批量异动方案没有明细，无法提交审批",
            )
        definition = await self._resolve_workflow_definition(payload.workflow_definition_id)
        # Requirement: HR-BATCH-003 — 整批只启动一个流程实例，业务对象是方案本身。
        instance = await self._lifecycle.start_workflow(
            WorkflowInstanceCreate(
                workflow_definition_id=definition.id,
                business_object_type=BATCH_CHANGE_BUSINESS_OBJECT_TYPE,
                business_object_id=batch.id,
                context={
                    "batch_number": batch.batch_number,
                    "line_count": len(lines),
                },
            )
        )
        batch.workflow_instance_id = instance.id
        batch.status = BATCH_CHANGE_STATUS_SUBMITTED
        batch.submitted_at = datetime.now(UTC)
        for line in lines:
            line.workflow_instance_id = instance.id
            line.status = BATCH_CHANGE_LINE_STATUS_PENDING_APPROVAL
        await self._session.flush()
        await self._session.refresh(batch)
        await self._audit(
            action="batch_change.submit",
            object_id=batch.id,
            reason="提交批量异动方案审批",
            before={"status": BATCH_CHANGE_STATUS_DRAFT},
            after=self._batch_payload(batch),
        )
        return batch

    async def mark_approved(self, batch_id: UUID) -> HrEventBatch:
        """审批通过回调：整批明细转就绪，交给现有 hr_event 执行器按生效日执行。

        Requirement: HR-BATCH-008 — 明细只切换到就绪态，实际执行仍由现有执行器完成。
        """
        batch = await self._session.get(HrEventBatch, batch_id, with_for_update=True)
        if batch is None:
            raise ApiError(
                status_code=404,
                code="BATCH_CHANGE_NOT_FOUND",
                message="批量异动方案不存在",
            )
        if batch.status == BATCH_CHANGE_STATUS_APPROVED:
            return batch
        if batch.status != BATCH_CHANGE_STATUS_SUBMITTED:
            raise ApiError(
                status_code=409,
                code="BATCH_CHANGE_NOT_SUBMITTED",
                message="只有已提交审批的批量异动方案可以通过审批",
            )
        batch.status = BATCH_CHANGE_STATUS_APPROVED
        batch.approved_at = datetime.now(UTC)
        for line in await self.list_lines(batch.id):
            line.status = BATCH_CHANGE_LINE_STATUS_READY
        await self._session.flush()
        await self._session.refresh(batch)
        await self._audit(
            action="batch_change.approve",
            object_id=batch.id,
            reason="批量异动方案审批通过",
            before={"status": BATCH_CHANGE_STATUS_SUBMITTED},
            after=self._batch_payload(batch),
        )
        return batch

    async def mark_rejected(self, batch_id: UUID) -> HrEventBatch:
        """审批驳回回调：整批明细标记为驳回，不再进入执行器。"""
        batch = await self._session.get(HrEventBatch, batch_id, with_for_update=True)
        if batch is None:
            raise ApiError(
                status_code=404,
                code="BATCH_CHANGE_NOT_FOUND",
                message="批量异动方案不存在",
            )
        if batch.status == BATCH_CHANGE_STATUS_REJECTED:
            return batch
        if batch.status != BATCH_CHANGE_STATUS_SUBMITTED:
            raise ApiError(
                status_code=409,
                code="BATCH_CHANGE_NOT_SUBMITTED",
                message="只有已提交审批的批量异动方案可以驳回",
            )
        batch.status = BATCH_CHANGE_STATUS_REJECTED
        for line in await self.list_lines(batch.id):
            line.status = BATCH_CHANGE_LINE_STATUS_REJECTED
        await self._session.flush()
        await self._session.refresh(batch)
        await self._audit(
            action="batch_change.reject",
            object_id=batch.id,
            reason="批量异动方案审批驳回",
            before={"status": BATCH_CHANGE_STATUS_SUBMITTED},
            after=self._batch_payload(batch),
        )
        return batch

    async def _get_draft_batch(self, batch_id: UUID) -> HrEventBatch:
        batch = await self._session.get(HrEventBatch, batch_id, with_for_update=True)
        if batch is None:
            raise ApiError(
                status_code=404,
                code="BATCH_CHANGE_NOT_FOUND",
                message="批量异动方案不存在",
            )
        # Requirement: HR-BATCH-002 — 只有草稿态方案可以追加、移除明细与提交审批。
        if batch.status != BATCH_CHANGE_STATUS_DRAFT:
            raise ApiError(
                status_code=409,
                code="BATCH_CHANGE_NOT_DRAFT",
                message="只有草稿状态的批量异动方案可以修改或提交",
                details=[
                    {"field": "status", "message": f"当前方案状态为 {batch.status}"}
                ],
            )
        return batch

    async def _resolve_existing_line(
        self,
        batch: HrEventBatch,
        line: BatchChangeLineCreate,
    ) -> HrEvent | None:
        """按幂等键查找既有明细；命中同一方案且内容一致时视为重复追加。"""
        if line.idempotency_key is None:
            return None
        await self._lock_idempotency(line.idempotency_key)
        existing = await self._session.scalar(
            select(HrEvent).where(HrEvent.idempotency_key == line.idempotency_key)
        )
        if existing is None:
            return None
        checksum = self._line_checksum(line)
        if existing.request_checksum != checksum or existing.batch_id != batch.id:
            # Requirement: HR-BATCH-005 — 幂等键复用既有明细（全局唯一）时直接冲突。
            raise ApiError(
                status_code=409,
                code="BATCH_CHANGE_IDEMPOTENCY_CONFLICT",
                message="idempotency key 已被其它异动明细占用",
            )
        return existing

    async def _create_line(self, batch: HrEventBatch, line: BatchChangeLineCreate) -> HrEvent:
        event_payload = HrEventCreate(
            idempotency_key=line.idempotency_key,
            event_type=line.event_type,
            object_type=line.object_type,
            object_id=line.object_id,
            effective_date=line.effective_date,
            execution_mode="approval",
            reason=line.reason,
            before_payload=line.before_payload,
            planned_payload=line.planned_payload,
        )
        # Requirement: HR-BATCH-010 — 明细沿用现有人事事件的校验口径，
        # 避免批量方案出现单条异动接口不接受的异动类型。
        await self._lifecycle._validate_hr_event(event_payload)
        # Requirement: HR-BATCH-010 — 明细事件号与单条异动共用同一流水号。
        number = await next_number(
            self._session,
            sequence_code="HR_EVENT_NUMBER",
            width=10,
            max_value=9999999999,
            prefix="E",
        )
        event = HrEvent(
            event_number=number,
            idempotency_key=line.idempotency_key,
            request_checksum=self._line_checksum(line),
            event_type=line.event_type,
            object_type=line.object_type,
            object_id=line.object_id,
            effective_date=line.effective_date,
            # Requirement: HR-BATCH-002 — 明细在方案草稿阶段保持草稿态，
            # 不会被现有 hr_event 执行器捞起执行。
            status=BATCH_CHANGE_LINE_STATUS_DRAFT,
            source="api",
            reason=line.reason,
            before_payload=line.before_payload,
            planned_payload=line.planned_payload,
            actual_payload={},
            workflow_instance_id=None,
            attempts=0,
            version=1,
            batch_id=batch.id,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(event)
                await self._session.flush()
        except IntegrityError as exc:
            # Requirement: HR-BATCH-005 — 幂等键唯一约束兜底，重复追加不产生新行。
            raise ApiError(
                status_code=409,
                code="BATCH_CHANGE_IDEMPOTENCY_CONFLICT",
                message="idempotency key 已被其它异动明细占用",
            ) from exc
        return event

    async def _resolve_workflow_definition(
        self,
        workflow_definition_id: UUID | None,
    ) -> WorkflowDefinition:
        if workflow_definition_id is None:
            # Requirement: HR-BATCH-009 — 未指定流程定义时使用默认批量异动审批流程。
            definition = await self._session.scalar(
                select(WorkflowDefinition).where(
                    WorkflowDefinition.code == BATCH_CHANGE_WORKFLOW_CODE
                )
            )
            if definition is None:
                raise ApiError(
                    status_code=422,
                    code="BATCH_CHANGE_WORKFLOW_NOT_CONFIGURED",
                    message="未配置批量异动审批流程，无法提交审批",
                )
        else:
            definition = await self._session.get(WorkflowDefinition, workflow_definition_id)
            if definition is None:
                raise ApiError(
                    status_code=404,
                    code="BATCH_CHANGE_WORKFLOW_NOT_FOUND",
                    message="审批流程定义不存在",
                )
        if definition.status != "active" or definition.active_version is None:
            raise ApiError(
                status_code=422,
                code="BATCH_CHANGE_WORKFLOW_NOT_ACTIVE",
                message="审批流程尚未发布，不能提交审批",
            )
        return definition

    async def _count_lines(self, batch_id: UUID) -> int:
        total = await self._session.scalar(
            select(func.count()).select_from(HrEvent).where(HrEvent.batch_id == batch_id)
        )
        return int(total or 0)

    async def _refresh_line_count(self, batch: HrEventBatch) -> int:
        batch.line_count = await self._count_lines(batch.id)
        await self._session.flush()
        # 方案行数变更会触发 updated_at 的服务端刷新，回读一次避免响应读到过期属性。
        await self._session.refresh(batch)
        return batch.line_count

    async def _lock_idempotency(self, key: UUID) -> None:
        lock_key = key.int & ((1 << 63) - 1)
        await self._session.execute(select(func.pg_advisory_xact_lock(lock_key)))

    @staticmethod
    def _line_checksum(line: BatchChangeLineCreate) -> str:
        canonical = json.dumps(
            line.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def _audit(
        self,
        *,
        action: str,
        object_id: UUID,
        reason: str,
        before: dict[str, Any],
        after: dict[str, Any],
    ) -> None:
        self._session.add(
            AuditLog(
                occurred_at=datetime.now(UTC),
                actor_id=self._actor_id,
                trace_id=self._trace_id,
                action=action,
                object_type="hr_event_batch",
                object_id=object_id,
                reason=reason,
                before_payload=before,
                after_payload=after,
                source="api",
            )
        )
        await self._session.flush()

    @staticmethod
    def _batch_payload(batch: HrEventBatch) -> dict[str, Any]:
        # Requirement: HR-BATCH-007 — 审计负载只写业务标识与计数，
        # 不写方案标题、明细原因等可能包含员工姓名等个人信息的自由文本。
        return {
            "batch_number": batch.batch_number,
            "status": batch.status,
            "line_count": batch.line_count,
            "workflow_instance_id": (
                str(batch.workflow_instance_id) if batch.workflow_instance_id else None
            ),
        }

    @staticmethod
    def _line_payload(line: HrEvent) -> dict[str, Any]:
        return {
            "event_number": line.event_number,
            "event_type": line.event_type,
            "object_type": line.object_type,
            "object_id": str(line.object_id),
            "effective_date": line.effective_date.isoformat(),
            "status": line.status,
        }
