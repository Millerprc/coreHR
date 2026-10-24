# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""排班管理服务：排班类型、轮班周期、弹性窗口、草稿生成、发布批次与换班记录。

Requirement: D-107 —— 轮班周期、弹性窗口、同日多班次只建规则容器与占位约束，
取值语义待企业输入（`docs/input-packs/07-attendance-rule-input.md` §4.2）。

Requirement: D-097 —— 批量排班单次最多 1000 条明细，超限整批拒绝。
Requirement: D-052 —— 批量维护允许部分成功并返回失败明细，逐条给出失败原因。
"""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from hris.core.errors import ApiError
from hris.modules.attendance.extended_service import ExtendedAttendanceService
from hris.modules.attendance.models import (
    ScheduleAssignment,
    SchedulePublishBatch,
    ScheduleSwap,
    ScheduleType,
    Shift,
    ShiftCycle,
    FlexibleWindow,
)
from hris.modules.attendance.schedule_schemas import (
    FlexibleWindowCreate,
    ScheduleDraftCreate,
    ScheduleDraftFailure,
    ScheduleDraftLine,
    ScheduleDraftResult,
    SchedulePublishBatchCreate,
    ScheduleSwapCreate,
    ScheduleSwapUpdate,
    ScheduleTypeCreate,
    ShiftCycleCreate,
    SCHEDULE_BATCH_MAX_LINES,
)
from hris.modules.platform.numbering import next_number
from hris.modules.workforce.models import Employment


class ScheduleManagementService(ExtendedAttendanceService):
    """排班管理服务。"""

    # —— 排班类型 ——

    async def create_schedule_type(self, payload: ScheduleTypeCreate) -> ScheduleType:
        existing = await self._session.scalar(
            select(ScheduleType.id).where(ScheduleType.code == payload.code)
        )
        if existing is not None:
            raise ApiError(
                status_code=409,
                code="SCHEDULE_TYPE_CODE_EXISTS",
                message="排班类型代码已存在",
            )
        schedule_type = ScheduleType(**payload.model_dump(), status="active")
        self._session.add(schedule_type)
        await self._session.flush()
        self._audit(
            action="attendance.schedule_type.create",
            object_type="schedule_type",
            object_id=schedule_type.id,
            after={"code": schedule_type.code, "name": schedule_type.name},
        )
        return schedule_type

    async def list_schedule_types(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[ScheduleType], int]:
        total = await self._session.scalar(
            select(func.count()).select_from(ScheduleType)
        )
        items = list(
            (
                await self._session.scalars(
                    select(ScheduleType)
                    .order_by(ScheduleType.code)
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return items, total or 0

    # —— 轮班周期 ——

    async def create_shift_cycle(self, payload: ShiftCycleCreate) -> ShiftCycle:
        if await self._session.get(ScheduleType, payload.schedule_type_id) is None:
            raise ApiError(
                status_code=404,
                code="SCHEDULE_TYPE_NOT_FOUND",
                message="排班类型不存在",
            )
        existing = await self._session.scalar(
            select(ShiftCycle.id).where(ShiftCycle.code == payload.code)
        )
        if existing is not None:
            raise ApiError(
                status_code=409,
                code="SHIFT_CYCLE_CODE_EXISTS",
                message="轮班周期代码已存在",
            )
        for shift_id in payload.shift_sequence:
            if await self._session.get(Shift, shift_id) is None:
                raise ApiError(
                    status_code=404,
                    code="SHIFT_NOT_FOUND",
                    message="班次不存在",
                )
        cycle = ShiftCycle(**payload.model_dump(), status="draft")
        self._session.add(cycle)
        await self._session.flush()
        self._audit(
            action="attendance.shift_cycle.create",
            object_type="shift_cycle",
            object_id=cycle.id,
            after={
                "code": cycle.code,
                "cycle_days": cycle.cycle_days,
                "status": cycle.status,
            },
        )
        return cycle

    async def list_shift_cycles(
        self,
        *,
        schedule_type_id: UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[ShiftCycle], int]:
        filters = []
        if schedule_type_id is not None:
            filters.append(ShiftCycle.schedule_type_id == schedule_type_id)
        total = await self._session.scalar(
            select(func.count()).select_from(ShiftCycle).where(*filters)
        )
        items = list(
            (
                await self._session.scalars(
                    select(ShiftCycle)
                    .where(*filters)
                    .order_by(ShiftCycle.code)
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return items, total or 0

    # —— 弹性窗口 ——

    async def create_flexible_window(
        self,
        payload: FlexibleWindowCreate,
    ) -> FlexibleWindow:
        if await self._session.get(ScheduleType, payload.schedule_type_id) is None:
            raise ApiError(
                status_code=404,
                code="SCHEDULE_TYPE_NOT_FOUND",
                message="排班类型不存在",
            )
        existing = await self._session.scalar(
            select(FlexibleWindow.id).where(FlexibleWindow.code == payload.code)
        )
        if existing is not None:
            raise ApiError(
                status_code=409,
                code="FLEXIBLE_WINDOW_CODE_EXISTS",
                message="弹性窗口代码已存在",
            )
        window = FlexibleWindow(**payload.model_dump(), status="draft")
        self._session.add(window)
        await self._session.flush()
        self._audit(
            action="attendance.flexible_window.create",
            object_type="flexible_window",
            object_id=window.id,
            after={"code": window.code, "status": window.status},
        )
        return window

    async def list_flexible_windows(
        self,
        *,
        schedule_type_id: UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[FlexibleWindow], int]:
        filters = []
        if schedule_type_id is not None:
            filters.append(FlexibleWindow.schedule_type_id == schedule_type_id)
        total = await self._session.scalar(
            select(func.count()).select_from(FlexibleWindow).where(*filters)
        )
        items = list(
            (
                await self._session.scalars(
                    select(FlexibleWindow)
                    .where(*filters)
                    .order_by(FlexibleWindow.code)
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return items, total or 0

    # —— 批量排班（草稿） ——

    async def generate_draft_schedules(
        self,
        payload: ScheduleDraftCreate,
    ) -> ScheduleDraftResult:
        """按批量明细生成草稿排班。

        Requirement: D-097 —— 明细上限 1000 条，超限整批拒绝。
        Requirement: D-052 —— 逐条校验，失败行返回原因，成功行照常写入。
        """
        if len(payload.lines) > SCHEDULE_BATCH_MAX_LINES:
            raise ApiError(
                status_code=422,
                code="SCHEDULE_BATCH_LIMIT_EXCEEDED",
                message=f"批量排班单次最多 {SCHEDULE_BATCH_MAX_LINES} 条明细",
                details=[{"limit": SCHEDULE_BATCH_MAX_LINES, "received": len(payload.lines)}],
            )
        if payload.schedule_type_id is not None and (
            await self._session.get(ScheduleType, payload.schedule_type_id) is None
        ):
            raise ApiError(
                status_code=404,
                code="SCHEDULE_TYPE_NOT_FOUND",
                message="排班类型不存在",
            )
        created = 0
        failures: list[ScheduleDraftFailure] = []
        for index, line in enumerate(payload.lines):
            try:
                async with self._session.begin_nested():
                    await self._create_draft_line(line, payload)
            except ApiError as error:
                failures.append(
                    ScheduleDraftFailure(
                        line_index=index,
                        employment_id=line.employment_id,
                        work_date=line.work_date,
                        code=error.code,
                        message=error.message,
                    )
                )
            except IntegrityError:
                failures.append(
                    ScheduleDraftFailure(
                        line_index=index,
                        employment_id=line.employment_id,
                        work_date=line.work_date,
                        code="SCHEDULE_DRAFT_CONFLICT",
                        message="该日期已存在排班",
                    )
                )
            else:
                created += 1
        await self._session.flush()
        self._audit(
            action="attendance.schedule_draft.generate",
            object_type="schedule_assignment",
            object_id=UUID(int=0),
            reason=f"批量排班草稿 {payload.period_code}",
            after={
                "period_code": payload.period_code,
                "created": created,
                "failed": len(failures),
            },
        )
        return ScheduleDraftResult(
            period_code=payload.period_code,
            created=created,
            failed=failures,
        )

    async def _create_draft_line(
        self,
        line: ScheduleDraftLine,
        payload: ScheduleDraftCreate,
    ) -> ScheduleAssignment:
        if await self._session.get(Employment, line.employment_id) is None:
            raise ApiError(
                status_code=404,
                code="EMPLOYMENT_NOT_FOUND",
                message="劳动关系不存在",
            )
        if await self._session.get(Shift, line.shift_id) is None:
            raise ApiError(
                status_code=404,
                code="SHIFT_NOT_FOUND",
                message="班次不存在",
            )
        existing_id = await self._session.scalar(
            select(ScheduleAssignment.id).where(
                ScheduleAssignment.employment_id == line.employment_id,
                ScheduleAssignment.work_date == line.work_date,
                ScheduleAssignment.sequence_no == line.sequence_no,
            )
        )
        if existing_id is not None:
            existing = await self._session.get(ScheduleAssignment, existing_id)
            if existing is None or existing.status != "cancelled":
                raise ApiError(
                    status_code=409,
                    code="SCHEDULE_EXISTS",
                    message="该日期已存在排班",
                )
            # 已取消的排班可以重新生成草稿。
            existing.shift_id = line.shift_id
            existing.source = payload.source
            existing.status = "active"
            existing.publish_status = "draft"
            existing.batch_id = None
            existing.schedule_type_id = payload.schedule_type_id
            await self._session.flush()
            return existing
        assignment = ScheduleAssignment(
            employment_id=line.employment_id,
            work_date=line.work_date,
            shift_id=line.shift_id,
            source=payload.source,
            status="active",
            publish_status="draft",
            sequence_no=line.sequence_no,
            schedule_type_id=payload.schedule_type_id,
        )
        self._session.add(assignment)
        await self._session.flush()
        return assignment

    # —— 发布批次 ——

    async def create_publish_batch(
        self,
        payload: SchedulePublishBatchCreate,
    ) -> SchedulePublishBatch:
        if payload.schedule_type_id is not None and (
            await self._session.get(ScheduleType, payload.schedule_type_id) is None
        ):
            raise ApiError(
                status_code=404,
                code="SCHEDULE_TYPE_NOT_FOUND",
                message="排班类型不存在",
            )
        year_text, month_text = payload.period_code.split("-")
        year = int(year_text)
        month = int(month_text)
        if month < 1 or month > 12:
            raise ApiError(
                status_code=422,
                code="SCHEDULE_PERIOD_INVALID",
                message="排班期间月份无效",
            )
        period_start = date(year, month, 1)
        period_end = date(year + (month == 12), (month % 12) + 1, 1) - timedelta(days=1)
        number = await next_number(
            self._session,
            sequence_code="SCHEDULE_PUBLISH_BATCH_NUMBER",
            width=8,
            max_value=99_999_999,
            prefix="SP",
        )
        batch = SchedulePublishBatch(
            batch_number=number,
            period_code=payload.period_code,
            period_start=period_start,
            period_end=period_end,
            schedule_type_id=payload.schedule_type_id,
            status="draft",
            created_by=self._actor_id,
        )
        self._session.add(batch)
        await self._session.flush()
        self._audit(
            action="attendance.schedule_publish_batch.create",
            object_type="schedule_publish_batch",
            object_id=batch.id,
            after={"batch_number": batch.batch_number, "period_code": batch.period_code},
        )
        return batch

    async def list_publish_batches(
        self,
        *,
        batch_status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[SchedulePublishBatch], int]:
        filters = []
        if batch_status is not None:
            filters.append(SchedulePublishBatch.status == batch_status)
        total = await self._session.scalar(
            select(func.count()).select_from(SchedulePublishBatch).where(*filters)
        )
        items = list(
            (
                await self._session.scalars(
                    select(SchedulePublishBatch)
                    .where(*filters)
                    .order_by(SchedulePublishBatch.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return items, total or 0

    async def publish_publish_batch(
        self,
        batch_id: UUID,
    ) -> SchedulePublishBatch:
        """按期间发布草稿排班：草稿行转已发布并挂到本批次。"""
        batch = await self._session.get(
            SchedulePublishBatch,
            batch_id,
            with_for_update=True,
        )
        if batch is None:
            raise ApiError(
                status_code=404,
                code="SCHEDULE_PUBLISH_BATCH_NOT_FOUND",
                message="排班发布批次不存在",
            )
        if batch.status != "draft":
            raise ApiError(
                status_code=409,
                code="SCHEDULE_PUBLISH_BATCH_NOT_DRAFT",
                message="只有草稿状态的发布批次可以发布",
            )
        filters = [
            ScheduleAssignment.publish_status == "draft",
            ScheduleAssignment.status == "active",
            ScheduleAssignment.work_date >= batch.period_start,
            ScheduleAssignment.work_date <= batch.period_end,
        ]
        if batch.schedule_type_id is not None:
            filters.append(ScheduleAssignment.schedule_type_id == batch.schedule_type_id)
        assignments = list(
            (
                await self._session.scalars(
                    select(ScheduleAssignment)
                    .where(*filters)
                    .with_for_update()
                    .order_by(ScheduleAssignment.work_date)
                )
            ).all()
        )
        for assignment in assignments:
            assignment.publish_status = "published"
            assignment.batch_id = batch.id
        batch.status = "published"
        batch.published_at = datetime.now(UTC)
        batch.published_by = self._actor_id
        batch.published_count = len(assignments)
        await self._session.flush()
        await self._session.refresh(batch)
        self._audit(
            action="attendance.schedule_publish_batch.publish",
            object_type="schedule_publish_batch",
            object_id=batch.id,
            reason=f"发布 {batch.period_code} 期间排班",
            after={
                "batch_number": batch.batch_number,
                "period_code": batch.period_code,
                "published_count": len(assignments),
            },
        )
        return batch

    # —— 换班记录 ——

    async def create_swap(self, payload: ScheduleSwapCreate) -> ScheduleSwap:
        if await self._session.get(Employment, payload.employment_id_a) is None:
            raise ApiError(
                status_code=404,
                code="EMPLOYMENT_NOT_FOUND",
                message="换班人 A 的劳动关系不存在",
            )
        if await self._session.get(Employment, payload.employment_id_b) is None:
            raise ApiError(
                status_code=404,
                code="EMPLOYMENT_NOT_FOUND",
                message="换班人 B 的劳动关系不存在",
            )
        original_shift_id = payload.original_shift_id
        if original_shift_id is None:
            assignment = await self._session.scalar(
                select(ScheduleAssignment).where(
                    ScheduleAssignment.employment_id == payload.employment_id_a,
                    ScheduleAssignment.work_date == payload.work_date,
                    ScheduleAssignment.status == "active",
                )
            )
            if assignment is not None:
                original_shift_id = assignment.shift_id
        if original_shift_id is not None and (
            await self._session.get(Shift, original_shift_id) is None
        ):
            raise ApiError(
                status_code=404,
                code="SHIFT_NOT_FOUND",
                message="原班次不存在",
            )
        if payload.new_shift_id is not None and (
            await self._session.get(Shift, payload.new_shift_id) is None
        ):
            raise ApiError(
                status_code=404,
                code="SHIFT_NOT_FOUND",
                message="新班次不存在",
            )
        number = await next_number(
            self._session,
            sequence_code="SCHEDULE_SWAP_NUMBER",
            width=8,
            max_value=99_999_999,
            prefix="SW",
        )
        swap = ScheduleSwap(
            request_number=number,
            employment_id_a=payload.employment_id_a,
            employment_id_b=payload.employment_id_b,
            work_date=payload.work_date,
            original_shift_id=original_shift_id,
            new_shift_id=payload.new_shift_id,
            status="draft",
            requested_by=self._actor_id,
            requested_at=datetime.now(UTC),
            effective_at=payload.effective_at,
            remark=payload.remark,
        )
        self._session.add(swap)
        await self._session.flush()
        self._audit(
            action="attendance.schedule_swap.create",
            object_type="schedule_swap",
            object_id=swap.id,
            after={
                "request_number": swap.request_number,
                "work_date": swap.work_date.isoformat(),
                "status": swap.status,
            },
        )
        return swap

    async def list_swaps(
        self,
        *,
        swap_status: str | None,
        employment_id: UUID | None,
        date_from: date | None,
        date_to: date | None,
        limit: int,
        offset: int,
    ) -> tuple[list[ScheduleSwap], int]:
        filters = []
        if swap_status is not None:
            filters.append(ScheduleSwap.status == swap_status)
        if employment_id is not None:
            filters.append(
                (ScheduleSwap.employment_id_a == employment_id)
                | (ScheduleSwap.employment_id_b == employment_id)
            )
        if date_from is not None:
            filters.append(ScheduleSwap.work_date >= date_from)
        if date_to is not None:
            filters.append(ScheduleSwap.work_date <= date_to)
        total = await self._session.scalar(
            select(func.count()).select_from(ScheduleSwap).where(*filters)
        )
        items = list(
            (
                await self._session.scalars(
                    select(ScheduleSwap)
                    .where(*filters)
                    .order_by(ScheduleSwap.work_date.desc(), ScheduleSwap.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return items, total or 0

    async def decide_swap(
        self,
        swap_id: UUID,
        payload: ScheduleSwapUpdate,
    ) -> ScheduleSwap:
        swap = await self._session.get(ScheduleSwap, swap_id, with_for_update=True)
        if swap is None:
            raise ApiError(
                status_code=404,
                code="SCHEDULE_SWAP_NOT_FOUND",
                message="换班记录不存在",
            )
        if swap.status != "draft":
            raise ApiError(
                status_code=409,
                code="SCHEDULE_SWAP_ALREADY_DECIDED",
                message="换班记录已处理",
            )
        if payload.status == "approved":
            await self._apply_swap(swap)
            swap.effective_at = datetime.now(UTC)
        swap.status = payload.status
        swap.decided_at = datetime.now(UTC)
        swap.decided_by = self._actor_id
        if payload.remark is not None:
            swap.remark = payload.remark
        await self._session.flush()
        await self._session.refresh(swap)
        self._audit(
            action="attendance.schedule_swap.decide",
            object_type="schedule_swap",
            object_id=swap.id,
            reason=payload.remark,
            after={"request_number": swap.request_number, "status": swap.status},
        )
        return swap

    async def _apply_swap(self, swap: ScheduleSwap) -> None:
        """换班生效：双方当日班次互换。"""
        if swap.original_shift_id is None or swap.new_shift_id is None:
            raise ApiError(
                status_code=422,
                code="SCHEDULE_SWAP_SHIFT_REQUIRED",
                message="换班生效需要明确的原班次与新班次",
            )
        assignment_a = await self._session.scalar(
            select(ScheduleAssignment)
            .where(
                ScheduleAssignment.employment_id == swap.employment_id_a,
                ScheduleAssignment.work_date == swap.work_date,
                ScheduleAssignment.status == "active",
            )
            .with_for_update()
        )
        assignment_b = await self._session.scalar(
            select(ScheduleAssignment)
            .where(
                ScheduleAssignment.employment_id == swap.employment_id_b,
                ScheduleAssignment.work_date == swap.work_date,
                ScheduleAssignment.status == "active",
            )
            .with_for_update()
        )
        if assignment_a is None or assignment_b is None:
            raise ApiError(
                status_code=409,
                code="SCHEDULE_SWAP_ASSIGNMENT_MISSING",
                message="换班双方当日缺少有效排班，无法生效",
            )
        assignment_a.shift_id = swap.new_shift_id
        assignment_b.shift_id = swap.original_shift_id
