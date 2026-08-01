from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.errors import ApiError
from hris.modules.attendance.extended_schemas import (
    LeaveCancellationCreate,
    LeaveRequestCreate,
    LeaveTypeCreate,
    PunchCreate,
    ScheduleAssignmentCreate,
    ShiftCreate,
)
from hris.modules.attendance.models import (
    AttendancePunch,
    AttendanceRuleSet,
    LeaveRequest,
    LeaveType,
    ScheduleAssignment,
    Shift,
)
from hris.modules.platform.numbering import next_number
from hris.modules.workflow.models import WorkflowInstance
from hris.modules.workforce.models import AuditLog, Employment


class ExtendedAttendanceService:
    def __init__(self, session: AsyncSession, *, actor_id: UUID, trace_id: str) -> None:
        self._session = session
        self._actor_id = actor_id
        self._trace_id = trace_id

    def _audit(self, *, action: str, object_type: str, object_id: UUID, after: dict[str, Any]) -> None:
        self._session.add(
            AuditLog(
                occurred_at=datetime.now(UTC),
                actor_id=self._actor_id,
                trace_id=self._trace_id,
                action=action,
                object_type=object_type,
                object_id=object_id,
                reason=None,
                before_payload={},
                after_payload=after,
                source="api",
            )
        )

    async def create_shift(self, payload: ShiftCreate) -> Shift:
        if await self._session.scalar(select(Shift.id).where(Shift.code == payload.code)) is not None:
            raise ApiError(status_code=409, code="SHIFT_CODE_EXISTS", message="班次代码已存在")
        if await self._session.get(AttendanceRuleSet, payload.rule_set_id) is None:
            raise ApiError(status_code=404, code="RULE_SET_NOT_FOUND", message="考勤规则集不存在")
        shift = Shift(**payload.model_dump(), status="active")
        self._session.add(shift)
        await self._session.flush()
        self._audit(
            action="create",
            object_type="shift",
            object_id=shift.id,
            after={"code": shift.code, "name": shift.name},
        )
        return shift

    async def create_schedule(self, payload: ScheduleAssignmentCreate) -> ScheduleAssignment:
        if await self._session.get(Employment, payload.employment_id) is None:
            raise ApiError(status_code=404, code="EMPLOYMENT_NOT_FOUND", message="劳动关系不存在")
        if await self._session.get(Shift, payload.shift_id) is None:
            raise ApiError(status_code=404, code="SHIFT_NOT_FOUND", message="班次不存在")
        existing = await self._session.scalar(
            select(ScheduleAssignment.id).where(
                ScheduleAssignment.employment_id == payload.employment_id,
                ScheduleAssignment.work_date == payload.work_date,
            )
        )
        if existing is not None:
            raise ApiError(status_code=409, code="SCHEDULE_EXISTS", message="该日期已存在排班")
        assignment = ScheduleAssignment(**payload.model_dump(), status="active")
        self._session.add(assignment)
        await self._session.flush()
        self._audit(
            action="create",
            object_type="schedule_assignment",
            object_id=assignment.id,
            after={"work_date": assignment.work_date.isoformat()},
        )
        return assignment

    async def ingest_punch(self, payload: PunchCreate) -> tuple[AttendancePunch, bool]:
        existing = await self._session.scalar(
            select(AttendancePunch).where(
                AttendancePunch.source == payload.source,
                AttendancePunch.source_record_id == payload.source_record_id,
            )
        )
        if existing is not None:
            return existing, True
        if await self._session.get(Employment, payload.employment_id) is None:
            raise ApiError(status_code=404, code="EMPLOYMENT_NOT_FOUND", message="劳动关系不存在")
        punch = AttendancePunch(**payload.model_dump())
        self._session.add(punch)
        await self._session.flush()
        self._audit(
            action="ingest",
            object_type="attendance_punch",
            object_id=punch.id,
            after={"source": punch.source, "source_record_id": punch.source_record_id},
        )
        return punch, False

    async def create_leave_type(self, payload: LeaveTypeCreate) -> LeaveType:
        if await self._session.scalar(
            select(LeaveType.id).where(LeaveType.code == payload.code)
        ) is not None:
            raise ApiError(status_code=409, code="LEAVE_TYPE_CODE_EXISTS", message="假期类型代码已存在")
        leave_type = LeaveType(**payload.model_dump(), status="active")
        self._session.add(leave_type)
        await self._session.flush()
        self._audit(
            action="create",
            object_type="leave_type",
            object_id=leave_type.id,
            after={"code": leave_type.code},
        )
        return leave_type

    async def create_leave_request(self, payload: LeaveRequestCreate) -> LeaveRequest:
        if await self._session.get(Employment, payload.employment_id) is None:
            raise ApiError(status_code=404, code="EMPLOYMENT_NOT_FOUND", message="劳动关系不存在")
        if await self._session.get(LeaveType, payload.leave_type_id) is None:
            raise ApiError(status_code=404, code="LEAVE_TYPE_NOT_FOUND", message="假期类型不存在")
        if payload.workflow_instance_id is not None and await self._session.get(
            WorkflowInstance, payload.workflow_instance_id
        ) is None:
            raise ApiError(status_code=404, code="WORKFLOW_INSTANCE_NOT_FOUND", message="流程实例不存在")
        number = await next_number(
            self._session,
            sequence_code="LEAVE_REQUEST_NUMBER",
            width=10,
            max_value=9999999999,
            prefix="L",
        )
        request = LeaveRequest(
            **payload.model_dump(),
            request_number=number,
            status="pending_approval" if payload.workflow_instance_id else "draft",
        )
        self._session.add(request)
        await self._session.flush()
        self._audit(
            action="create",
            object_type="leave_request",
            object_id=request.id,
            after={"request_number": request.request_number, "status": request.status},
        )
        return request

    async def cancel_leave_request(
        self,
        request_id: UUID,
        payload: LeaveCancellationCreate,
    ) -> LeaveRequest:
        original = await self._session.get(LeaveRequest, request_id)
        if original is None:
            raise ApiError(status_code=404, code="LEAVE_REQUEST_NOT_FOUND", message="请假记录不存在")
        if payload.workflow_instance_id is not None and await self._session.get(
            WorkflowInstance, payload.workflow_instance_id
        ) is None:
            raise ApiError(status_code=404, code="WORKFLOW_INSTANCE_NOT_FOUND", message="流程实例不存在")
        number = await next_number(
            self._session,
            sequence_code="LEAVE_REQUEST_NUMBER",
            width=10,
            max_value=9999999999,
            prefix="L",
        )
        cancellation = LeaveRequest(
            request_number=number,
            employment_id=original.employment_id,
            leave_type_id=original.leave_type_id,
            start_date=original.start_date,
            end_date=original.end_date,
            amount=original.amount,
            status="pending_approval" if payload.workflow_instance_id else "draft_cancellation",
            reason=payload.reason,
            workflow_instance_id=payload.workflow_instance_id,
            cancellation_of_id=original.id,
        )
        self._session.add(cancellation)
        await self._session.flush()
        self._audit(
            action="cancel_requested",
            object_type="leave_request",
            object_id=cancellation.id,
            after={"cancellation_of_id": str(original.id), "status": cancellation.status},
        )
        return cancellation
