from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.modules.attendance.extended_schemas import (
    LeaveCancellationCreate,
    LeaveRequestCreate,
    LeaveRequestResponse,
    LeaveTypeCreate,
    LeaveTypeResponse,
    PunchCreate,
    PunchIngestResponse,
    PunchResponse,
    ScheduleAssignmentCreate,
    ScheduleAssignmentResponse,
    ShiftCreate,
    ShiftResponse,
)
from hris.modules.attendance.extended_service import ExtendedAttendanceService
from hris.modules.platform.dependencies import require_permission
from hris.modules.platform.models import UserAccount


router = APIRouter(prefix="/api/v1/attendance", tags=["phase-3-attendance-admin"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
AdminUser = Annotated[UserAccount, Depends(require_permission("ATTENDANCE_ADMIN"))]


def service(db: AsyncSession, user: UserAccount, request: Request) -> ExtendedAttendanceService:
    return ExtendedAttendanceService(db, actor_id=user.id, trace_id=str(request.state.trace_id))


@router.post("/shifts", response_model=ShiftResponse, status_code=201)
async def create_shift(
    payload: ShiftCreate, request: Request, db: DbSession, user: AdminUser
) -> ShiftResponse:
    return ShiftResponse.model_validate(await service(db, user, request).create_shift(payload))


@router.post("/schedules", response_model=ScheduleAssignmentResponse, status_code=201)
async def create_schedule(
    payload: ScheduleAssignmentCreate, request: Request, db: DbSession, user: AdminUser
) -> ScheduleAssignmentResponse:
    return ScheduleAssignmentResponse.model_validate(
        await service(db, user, request).create_schedule(payload)
    )


@router.post("/punches", response_model=PunchIngestResponse, status_code=201)
async def ingest_punch(
    payload: PunchCreate, request: Request, db: DbSession, user: AdminUser
) -> PunchIngestResponse:
    record, duplicate = await service(db, user, request).ingest_punch(payload)
    return PunchIngestResponse(
        duplicate=duplicate,
        record=PunchResponse.model_validate(record),
    )


@router.post("/leave-types", response_model=LeaveTypeResponse, status_code=201)
async def create_leave_type(
    payload: LeaveTypeCreate, request: Request, db: DbSession, user: AdminUser
) -> LeaveTypeResponse:
    return LeaveTypeResponse.model_validate(
        await service(db, user, request).create_leave_type(payload)
    )


@router.post("/leave-requests", response_model=LeaveRequestResponse, status_code=201)
async def create_leave_request(
    payload: LeaveRequestCreate, request: Request, db: DbSession, user: AdminUser
) -> LeaveRequestResponse:
    return LeaveRequestResponse.model_validate(
        await service(db, user, request).create_leave_request(payload)
    )


@router.post(
    "/leave-requests/{request_id}/cancel",
    response_model=LeaveRequestResponse,
    status_code=201,
)
async def cancel_leave_request(
    request_id: UUID,
    payload: LeaveCancellationCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> LeaveRequestResponse:
    return LeaveRequestResponse.model_validate(
        await service(db, user, request).cancel_leave_request(request_id, payload)
    )
