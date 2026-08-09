from typing import Annotated, Literal
from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.modules.attendance.extended_schemas import (
    AttendanceEmploymentOption,
    AttendanceEmploymentOptionPage,
    AttendanceDailyCalculate,
    AttendanceDailyResultPage,
    AttendanceDailyResultResponse,
    AttendanceMonthlyCalculate,
    AttendanceMonthlyResultPage,
    AttendanceMonthlyResultResponse,
    AttendancePeriodFreezeCreate,
    AttendancePeriodFreezePage,
    AttendancePeriodFreezeRelease,
    AttendancePeriodFreezeResponse,
    LeaveCancellationCreate,
    LeaveRequestCreate,
    LeaveRequestPage,
    LeaveRequestResponse,
    LeaveRequestUpdate,
    LeaveTypeCreate,
    LeaveTypePage,
    LeaveTypeResponse,
    LeaveTypeUpdate,
    PunchCreate,
    PunchIngestResponse,
    PunchPage,
    PunchResponse,
    ScheduleAssignmentCreate,
    ScheduleAssignmentPage,
    ScheduleAssignmentResponse,
    ScheduleAssignmentUpdate,
    ShiftCreate,
    ShiftPage,
    ShiftResponse,
    ShiftUpdate,
)
from hris.modules.attendance.extended_service import ExtendedAttendanceService
from hris.modules.platform.dependencies import require_permission
from hris.modules.platform.models import UserAccount


router = APIRouter(prefix="/api/v1/attendance", tags=["phase-3-attendance-admin"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
AdminUser = Annotated[UserAccount, Depends(require_permission("ATTENDANCE_ADMIN"))]


def service(db: AsyncSession, user: UserAccount, request: Request) -> ExtendedAttendanceService:
    return ExtendedAttendanceService(db, actor_id=user.id, trace_id=str(request.state.trace_id))


@router.post(
    "/period-freezes",
    response_model=AttendancePeriodFreezeResponse,
    status_code=201,
)
async def create_period_freeze(
    payload: AttendancePeriodFreezeCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> AttendancePeriodFreezeResponse:
    return AttendancePeriodFreezeResponse.model_validate(
        await service(db, user, request).create_period_freeze(payload)
    )


@router.get("/period-freezes", response_model=AttendancePeriodFreezePage)
async def list_period_freezes(
    request: Request,
    db: DbSession,
    user: AdminUser,
    freeze_status: Literal["active", "released"] | None = Query(
        default=None,
        alias="status",
    ),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AttendancePeriodFreezePage:
    items, total = await service(db, user, request).list_period_freezes(
        status=freeze_status,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return AttendancePeriodFreezePage(
        items=[AttendancePeriodFreezeResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/period-freezes/{freeze_id}/release",
    response_model=AttendancePeriodFreezeResponse,
)
async def release_period_freeze(
    freeze_id: UUID,
    payload: AttendancePeriodFreezeRelease,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> AttendancePeriodFreezeResponse:
    return AttendancePeriodFreezeResponse.model_validate(
        await service(db, user, request).release_period_freeze(freeze_id, payload)
    )


@router.get("/employment-options", response_model=AttendanceEmploymentOptionPage)
async def list_employment_options(
    request: Request,
    db: DbSession,
    user: AdminUser,
    search: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=200, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AttendanceEmploymentOptionPage:
    items, total = await service(db, user, request).list_employment_options(
        search=search,
        limit=limit,
        offset=offset,
    )
    return AttendanceEmploymentOptionPage(
        items=[AttendanceEmploymentOption.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/shifts", response_model=ShiftResponse, status_code=201)
async def create_shift(
    payload: ShiftCreate, request: Request, db: DbSession, user: AdminUser
) -> ShiftResponse:
    return ShiftResponse.model_validate(await service(db, user, request).create_shift(payload))


@router.get("/shifts", response_model=ShiftPage)
async def list_shifts(
    request: Request,
    db: DbSession,
    user: AdminUser,
    shift_status: str | None = Query(default=None, alias="status", max_length=30),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ShiftPage:
    items, total = await service(db, user, request).list_shifts(
        status=shift_status,
        limit=limit,
        offset=offset,
    )
    return ShiftPage(
        items=[ShiftResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/shifts/{shift_id}", response_model=ShiftResponse)
async def update_shift(
    shift_id: UUID,
    payload: ShiftUpdate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> ShiftResponse:
    return ShiftResponse.model_validate(
        await service(db, user, request).update_shift(shift_id, payload)
    )


@router.post("/schedules", response_model=ScheduleAssignmentResponse, status_code=201)
async def create_schedule(
    payload: ScheduleAssignmentCreate, request: Request, db: DbSession, user: AdminUser
) -> ScheduleAssignmentResponse:
    return ScheduleAssignmentResponse.model_validate(
        await service(db, user, request).create_schedule(payload)
    )


@router.get("/schedules", response_model=ScheduleAssignmentPage)
async def list_schedules(
    request: Request,
    db: DbSession,
    user: AdminUser,
    employment_id: UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScheduleAssignmentPage:
    items, total = await service(db, user, request).list_schedules(
        employment_id=employment_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return ScheduleAssignmentPage(
        items=[ScheduleAssignmentResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/schedules/{schedule_id}", response_model=ScheduleAssignmentResponse)
async def update_schedule(
    schedule_id: UUID,
    payload: ScheduleAssignmentUpdate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> ScheduleAssignmentResponse:
    return ScheduleAssignmentResponse.model_validate(
        await service(db, user, request).update_schedule(schedule_id, payload)
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


@router.get("/punches", response_model=PunchPage)
async def list_punches(
    request: Request,
    db: DbSession,
    user: AdminUser,
    employment_id: UUID | None = Query(default=None),
    punched_from: datetime | None = Query(default=None),
    punched_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PunchPage:
    items, total = await service(db, user, request).list_punches(
        employment_id=employment_id,
        punched_from=punched_from,
        punched_to=punched_to,
        limit=limit,
        offset=offset,
    )
    return PunchPage(
        items=[PunchResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/leave-types", response_model=LeaveTypeResponse, status_code=201)
async def create_leave_type(
    payload: LeaveTypeCreate, request: Request, db: DbSession, user: AdminUser
) -> LeaveTypeResponse:
    return LeaveTypeResponse.model_validate(
        await service(db, user, request).create_leave_type(payload)
    )


@router.get("/leave-types", response_model=LeaveTypePage)
async def list_leave_types(
    request: Request,
    db: DbSession,
    user: AdminUser,
    leave_type_status: str | None = Query(default=None, alias="status", max_length=30),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> LeaveTypePage:
    items, total = await service(db, user, request).list_leave_types(
        status=leave_type_status,
        limit=limit,
        offset=offset,
    )
    return LeaveTypePage(
        items=[LeaveTypeResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/leave-types/{leave_type_id}", response_model=LeaveTypeResponse)
async def update_leave_type(
    leave_type_id: UUID,
    payload: LeaveTypeUpdate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> LeaveTypeResponse:
    return LeaveTypeResponse.model_validate(
        await service(db, user, request).update_leave_type(leave_type_id, payload)
    )


@router.post("/leave-requests", response_model=LeaveRequestResponse, status_code=201)
async def create_leave_request(
    payload: LeaveRequestCreate, request: Request, db: DbSession, user: AdminUser
) -> LeaveRequestResponse:
    return LeaveRequestResponse.model_validate(
        await service(db, user, request).create_leave_request(payload)
    )


@router.get("/leave-requests", response_model=LeaveRequestPage)
async def list_leave_requests(
    request: Request,
    db: DbSession,
    user: AdminUser,
    leave_status: str | None = Query(default=None, alias="status", max_length=30),
    employment_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> LeaveRequestPage:
    items, total = await service(db, user, request).list_leave_requests(
        status=leave_status,
        employment_id=employment_id,
        limit=limit,
        offset=offset,
    )
    return LeaveRequestPage(
        items=[LeaveRequestResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/leave-requests/{request_id}", response_model=LeaveRequestResponse)
async def update_leave_request(
    request_id: UUID,
    payload: LeaveRequestUpdate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> LeaveRequestResponse:
    return LeaveRequestResponse.model_validate(
        await service(db, user, request).update_leave_request(request_id, payload)
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


@router.post("/daily-results/calculate", response_model=AttendanceDailyResultResponse, status_code=201)
async def calculate_daily_result(
    payload: AttendanceDailyCalculate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> AttendanceDailyResultResponse:
    return AttendanceDailyResultResponse.model_validate(
        await service(db, user, request).calculate_daily(payload)
    )


@router.get("/daily-results", response_model=AttendanceDailyResultPage)
async def list_daily_results(
    request: Request,
    db: DbSession,
    user: AdminUser,
    employment_id: UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    current_only: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AttendanceDailyResultPage:
    items, total = await service(db, user, request).list_daily_results(
        employment_id=employment_id,
        date_from=date_from,
        date_to=date_to,
        current_only=current_only,
        limit=limit,
        offset=offset,
    )
    return AttendanceDailyResultPage(
        items=[AttendanceDailyResultResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/monthly-results/calculate", response_model=AttendanceMonthlyResultResponse, status_code=201)
async def calculate_monthly_result(
    payload: AttendanceMonthlyCalculate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> AttendanceMonthlyResultResponse:
    return AttendanceMonthlyResultResponse.model_validate(
        await service(db, user, request).calculate_monthly(payload)
    )


@router.get("/monthly-results", response_model=AttendanceMonthlyResultPage)
async def list_monthly_results(
    request: Request,
    db: DbSession,
    user: AdminUser,
    employment_id: UUID | None = Query(default=None),
    period_month: date | None = Query(default=None),
    current_only: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AttendanceMonthlyResultPage:
    items, total = await service(db, user, request).list_monthly_results(
        employment_id=employment_id,
        period_month=period_month,
        current_only=current_only,
        limit=limit,
        offset=offset,
    )
    return AttendanceMonthlyResultPage(
        items=[AttendanceMonthlyResultResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )
