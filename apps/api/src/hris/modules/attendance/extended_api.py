# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

from typing import Annotated, Any, Literal
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.core.errors import ApiError
from hris.modules.attendance.extended_schemas import (
    AttendanceCalculationKind,
    AttendanceCalculationRequest,
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
    LeaveBalanceAccountPage,
    LeaveBalanceAccountResponse,
    LeaveBalanceTransactionCreate,
    LeaveBalanceTransactionPage,
    LeaveBalanceTransactionResponse,
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
from hris.modules.attendance.grant_schemas import (
    LeaveGrantBatchCreate,
    LeaveGrantBatchDetailResponse,
    LeaveGrantBatchPage,
    LeaveGrantBatchResponse,
    LeaveGrantBatchVoid,
    LeaveGrantItemResponse,
    LeaveGrantRuleCreate,
    LeaveGrantRulePage,
    LeaveGrantRuleResponse,
    LeaveGrantRuleUpdate,
)
from hris.modules.attendance.grant_service import LeaveGrantService
from hris.modules.attendance.schedule_schemas import (
    FlexibleWindowCreate,
    FlexibleWindowPage,
    FlexibleWindowResponse,
    ScheduleDraftCreate,
    ScheduleDraftResult,
    SchedulePublishBatchCreate,
    SchedulePublishBatchPage,
    SchedulePublishBatchResponse,
    ScheduleSwapCreate,
    ScheduleSwapPage,
    ScheduleSwapResponse,
    ScheduleSwapUpdate,
    ScheduleTypeCreate,
    ScheduleTypePage,
    ScheduleTypeResponse,
    ShiftCycleCreate,
    ShiftCyclePage,
    ShiftCycleResponse,
)
from hris.modules.attendance.schedule_service import ScheduleManagementService
from hris.modules.platform.dependencies import (
    CurrentSession,
    granted_permission_codes,
    require_permission,
)
from hris.modules.platform.models import UserAccount
from hris.modules.platform.task_handlers import ATTENDANCE_CALCULATE
from hris.modules.platform.task_models import BackgroundTask
from hris.modules.platform.task_queue import TaskQueue
from hris.modules.platform.task_schemas import (
    BackgroundTaskResponse,
    BackgroundTaskSummaryResponse,
)


router = APIRouter(prefix="/api/v1/attendance", tags=["phase-3-attendance-admin"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
AdminUser = Annotated[UserAccount, Depends(require_permission("ATTENDANCE_ADMIN"))]

# Requirement: C5 — 考勤高风险动作拆独立权限码。
# 依据：docs/review/D-考勤-待确认-决策-文档规范.md §8「权限与审计」（14.md:185 行，P0）。
# 审计要求把「规则发布 / 批量排班 / 打卡补录 / 余额调整 / 日报重算 / 月报重算 / 冻结解冻」
# 7 类高风险动作从粗粒度的 ATTENDANCE_ADMIN 拆成独立权限码。
# 「规则发布」在 attendance/api.py（RulePublishUser），其余 6 类在本文件。
# 普通考勤操作（查询、班次、假期类型、请假单、发假规则配置等）仍用 ATTENDANCE_ADMIN。

# 批量排班：单条排班写入、草稿批量生成、发布批次、换班处理都属排班写入动作。
ScheduleWriteUser = Annotated[
    UserAccount, Depends(require_permission("ATTENDANCE_SCHEDULE_WRITE"))
]
# 打卡补录：打卡证据写入（含人工补录），会改变已发生事实的原始凭证。
PunchBackfillUser = Annotated[
    UserAccount, Depends(require_permission("ATTENDANCE_PUNCH_BACKFILL"))
]
# 余额调整：假期余额流水写入（人工调整、发放、发放作废），直接改变可用余额。
BalanceAdjustUser = Annotated[
    UserAccount, Depends(require_permission("ATTENDANCE_BALANCE_ADJUST"))
]
# 日报重算：重算并生成新版本日报。
DailyRecalcUser = Annotated[
    UserAccount, Depends(require_permission("ATTENDANCE_DAILY_RECALC"))
]
# 月报重算：重算并生成新版本月报。
MonthlyRecalcUser = Annotated[
    UserAccount, Depends(require_permission("ATTENDANCE_MONTHLY_RECALC"))
]
# 冻结与解冻：期间冻结阻断重算，解冻放行更正，二者都是高风险动作。
FreezeManageUser = Annotated[
    UserAccount, Depends(require_permission("ATTENDANCE_FREEZE_MANAGE"))
]


def service(db: AsyncSession, user: UserAccount, request: Request) -> ExtendedAttendanceService:
    return ExtendedAttendanceService(db, actor_id=user.id, trace_id=str(request.state.trace_id))


def grant_service(
    db: AsyncSession,
    user: UserAccount,
    request: Request,
) -> LeaveGrantService:
    return LeaveGrantService(db, actor_id=user.id, trace_id=str(request.state.trace_id))


def schedule_service(
    db: AsyncSession,
    user: UserAccount,
    request: Request,
) -> ScheduleManagementService:
    return ScheduleManagementService(db, actor_id=user.id, trace_id=str(request.state.trace_id))


@router.post(
    "/period-freezes",
    response_model=AttendancePeriodFreezeResponse,
    status_code=201,
)
async def create_period_freeze(
    payload: AttendancePeriodFreezeCreate,
    request: Request,
    db: DbSession,
    user: FreezeManageUser,
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
    user: FreezeManageUser,
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
    payload: ScheduleAssignmentCreate, request: Request, db: DbSession, user: ScheduleWriteUser
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
    publish_status: str | None = Query(default=None, alias="publish_status", max_length=20),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScheduleAssignmentPage:
    items, total = await service(db, user, request).list_schedules(
        employment_id=employment_id,
        date_from=date_from,
        date_to=date_to,
        publish_status=publish_status,
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
    user: ScheduleWriteUser,
) -> ScheduleAssignmentResponse:
    return ScheduleAssignmentResponse.model_validate(
        await service(db, user, request).update_schedule(schedule_id, payload)
    )


@router.post("/punches", response_model=PunchIngestResponse, status_code=201)
async def ingest_punch(
    payload: PunchCreate, request: Request, db: DbSession, user: PunchBackfillUser
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


@router.post(
    "/leave-balances/transactions",
    response_model=LeaveBalanceTransactionResponse,
    status_code=201,
)
async def create_leave_balance_transaction(
    payload: LeaveBalanceTransactionCreate,
    request: Request,
    db: DbSession,
    user: BalanceAdjustUser,
) -> LeaveBalanceTransactionResponse:
    return LeaveBalanceTransactionResponse.model_validate(
        await service(db, user, request).create_leave_balance_transaction(payload)
    )


@router.get("/leave-balances", response_model=LeaveBalanceAccountPage)
async def list_leave_balance_accounts(
    request: Request,
    db: DbSession,
    user: AdminUser,
    employment_id: UUID | None = Query(default=None),
    leave_type_id: UUID | None = Query(default=None),
    period_year: int | None = Query(default=None, ge=2000, le=2200),
    as_of: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> LeaveBalanceAccountPage:
    """假期余额账户。

    不传 `as_of` 返回当前余额（既有行为不变）；传 `as_of` 时额外返回该时点余额，
    口径见 `ExtendedAttendanceService.leave_balances_as_of`。
    """
    attendance = service(db, user, request)
    items, total = await attendance.list_leave_balance_accounts(
        employment_id=employment_id,
        leave_type_id=leave_type_id,
        period_year=period_year,
        limit=limit,
        offset=offset,
    )
    balances: dict[UUID, Decimal] = {}
    if as_of is not None:
        balances = await attendance.leave_balances_as_of([item.id for item in items], as_of)
    return LeaveBalanceAccountPage(
        items=[
            LeaveBalanceAccountResponse.model_validate(item).model_copy(
                update={
                    "as_of": as_of,
                    "balance_as_of": balances.get(item.id) if as_of is not None else None,
                }
            )
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/leave-balances/{account_id}/transactions",
    response_model=LeaveBalanceTransactionPage,
)
async def list_leave_balance_transactions(
    account_id: UUID,
    request: Request,
    db: DbSession,
    user: AdminUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> LeaveBalanceTransactionPage:
    items, total = await service(db, user, request).list_leave_balance_transactions(
        account_id,
        limit=limit,
        offset=offset,
    )
    return LeaveBalanceTransactionPage(
        items=[LeaveBalanceTransactionResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
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
    user: DailyRecalcUser,
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
    user: MonthlyRecalcUser,
) -> AttendanceMonthlyResultResponse:
    return AttendanceMonthlyResultResponse.model_validate(
        await service(db, user, request).calculate_monthly(payload)
    )


# Requirement: D-116 — 批量计算的权限按「计算类型」区分：
# 日报批量要 ATTENDANCE_DAILY_RECALC，月报批量要 ATTENDANCE_MONTHLY_RECALC。
# 所以这里不能用固定权限的 Depends（那会把两种类型绑死在一起），改为在函数体内按类型判定。
_CALCULATION_PERMISSION_BY_KIND: dict[AttendanceCalculationKind, str] = {
    AttendanceCalculationKind.DAILY: "ATTENDANCE_DAILY_RECALC",
    AttendanceCalculationKind.MONTHLY: "ATTENDANCE_MONTHLY_RECALC",
}

#: 查看计算任务所需的权限（发起人本人不需要额外权限）。
_CALCULATION_VIEW_PERMISSION_CODES = frozenset(
    {
        "ATTENDANCE_ADMIN",
        "ATTENDANCE_DAILY_RECALC",
        "ATTENDANCE_MONTHLY_RECALC",
    }
)


@router.post(
    "/calculation-tasks",
    response_model=BackgroundTaskSummaryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_attendance_calculation(
    payload: AttendanceCalculationRequest,
    request: Request,
    db: DbSession,
    current: CurrentSession,
) -> BackgroundTaskSummaryResponse:
    """把一次批量考勤计算排进后台任务队列。

    Requirement: D-116 — 逐人提交在 200 人规模下不可用（要点 200 次），
    批量计算因此走后台任务：提交即返回任务，实际计算由独立 Worker 执行，
    前端轮询任务状态拿结果。

    提交时就做**账期冻结预检**：冻结的账期直接 409，而不是让任务跑起来再失败。
    """

    user, _session = current
    required_code = _CALCULATION_PERMISSION_BY_KIND[payload.kind]
    granted = await granted_permission_codes(user, db)
    if "*" not in granted and required_code not in granted:
        raise ApiError(
            status_code=403,
            code="PERMISSION_DENIED",
            message="没有执行此操作的权限",
        )

    await service(db, user, request).assert_period_open_for_calculation(
        work_date=payload.work_date,
        period_month=payload.period_month,
    )
    # 提交时就校验范围里的人员是否真实存在：等任务跑起来才发现「这个人不存在」
    # 是异步反馈，管理员要等好几秒才知道自己白提交了一次。
    # 「排除人员」里不存在的人是无害的（排除一个本来就不存在的人等于没排除），
    # 因此 resolve_calculation_targets 只对「指定人员」做存在性校验。
    await service(db, user, request).resolve_calculation_targets(
        scope=payload.scope,
        employment_ids=payload.employment_ids,
    )

    task_payload: dict[str, Any] = {
        "kind": payload.kind.value,
        "scope": payload.scope.value,
        "employment_ids": [str(item) for item in payload.employment_ids],
        "actor_id": str(user.id),
        "trace_id": str(request.state.trace_id),
        "reason": payload.reason,
    }
    if payload.work_date is not None:
        task_payload["work_date"] = payload.work_date.isoformat()
    if payload.period_month is not None:
        task_payload["period_month"] = payload.period_month.isoformat()

    queue = TaskQueue(db)
    task = await queue.enqueue(
        ATTENDANCE_CALCULATE,
        task_payload,
        created_by=user.id,
    )
    return BackgroundTaskSummaryResponse.model_validate(task)


@router.get("/calculation-tasks/{task_id}", response_model=BackgroundTaskResponse)
async def get_attendance_calculation_task(
    task_id: UUID,
    db: DbSession,
    current: CurrentSession,
) -> BackgroundTaskResponse:
    """返回一条批量考勤计算任务的状态与结果统计。"""

    user, _session = current
    task = await db.get(BackgroundTask, task_id)
    if task is None or task.task_type != ATTENDANCE_CALCULATE:
        raise ApiError(
            status_code=404,
            code="BACKGROUND_TASK_NOT_FOUND",
            message="计算任务不存在",
        )
    granted = await granted_permission_codes(user, db)
    is_owner = task.created_by == user.id
    has_right = "*" in granted or bool(granted & _CALCULATION_VIEW_PERMISSION_CODES)
    if not (is_owner or has_right):
        raise ApiError(
            status_code=403,
            code="PERMISSION_DENIED",
            message="没有查看此任务的权限",
        )
    return BackgroundTaskResponse.model_validate(task)


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


# —————————————————————— 发假明细（复刻 Moka「发假明细」）——————————————————————


@router.get("/leave-grant-rules", response_model=LeaveGrantRulePage)
async def list_leave_grant_rules(
    request: Request,
    db: DbSession,
    user: AdminUser,
    leave_type_id: UUID | None = Query(default=None),
    rule_status: str | None = Query(default=None, alias="status", max_length=30),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> LeaveGrantRulePage:
    items, total = await grant_service(db, user, request).list_leave_grant_rules(
        leave_type_id=leave_type_id,
        status=rule_status,
        limit=limit,
        offset=offset,
    )
    return LeaveGrantRulePage(
        items=[LeaveGrantRuleResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/leave-grant-rules", response_model=LeaveGrantRuleResponse, status_code=201)
async def create_leave_grant_rule(
    payload: LeaveGrantRuleCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> LeaveGrantRuleResponse:
    """新建发假额度规则。同一代码重复提交视为新版本（规则按生效起止日期版本化）。"""
    return LeaveGrantRuleResponse.model_validate(
        await grant_service(db, user, request).create_leave_grant_rule(payload)
    )


@router.patch("/leave-grant-rules/{rule_id}", response_model=LeaveGrantRuleResponse)
async def update_leave_grant_rule(
    rule_id: UUID,
    payload: LeaveGrantRuleUpdate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> LeaveGrantRuleResponse:
    return LeaveGrantRuleResponse.model_validate(
        await grant_service(db, user, request).update_leave_grant_rule(rule_id, payload)
    )


@router.post("/leave-grant-rules/{rule_id}/activate", response_model=LeaveGrantRuleResponse)
async def activate_leave_grant_rule(
    rule_id: UUID,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> LeaveGrantRuleResponse:
    return LeaveGrantRuleResponse.model_validate(
        await grant_service(db, user, request).activate_leave_grant_rule(rule_id)
    )


@router.get("/leave-grant-batches", response_model=LeaveGrantBatchPage)
async def list_leave_grant_batches(
    request: Request,
    db: DbSession,
    user: AdminUser,
    batch_status: str | None = Query(default=None, alias="status", max_length=30),
    period_code: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> LeaveGrantBatchPage:
    items, total = await grant_service(db, user, request).list_leave_grant_batches(
        status=batch_status,
        period_code=period_code,
        limit=limit,
        offset=offset,
    )
    return LeaveGrantBatchPage(
        items=[LeaveGrantBatchResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/leave-grant-batches", response_model=LeaveGrantBatchResponse, status_code=201)
async def create_leave_grant_batch(
    payload: LeaveGrantBatchCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> LeaveGrantBatchResponse:
    """新建发假发放批次（草稿）。发放动作由 `/issue` 单独触发。"""
    return LeaveGrantBatchResponse.model_validate(
        await grant_service(db, user, request).create_leave_grant_batch(payload)
    )


@router.get("/leave-grant-batches/{batch_id}", response_model=LeaveGrantBatchDetailResponse)
async def get_leave_grant_batch(
    batch_id: UUID,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> LeaveGrantBatchDetailResponse:
    attendance = grant_service(db, user, request)
    batch = await attendance.get_leave_grant_batch(batch_id)
    items = await attendance.list_leave_grant_items(batch_id)
    return LeaveGrantBatchDetailResponse(
        **LeaveGrantBatchResponse.model_validate(batch).model_dump(),
        items=[LeaveGrantItemResponse.model_validate(item) for item in items],
    )


@router.post("/leave-grant-batches/{batch_id}/issue", response_model=LeaveGrantBatchResponse)
async def issue_leave_grant_batch(
    batch_id: UUID,
    request: Request,
    db: DbSession,
    user: BalanceAdjustUser,
) -> LeaveGrantBatchResponse:
    """发放批次：写假期余额流水并把批次置为已发放。"""
    return LeaveGrantBatchResponse.model_validate(
        await grant_service(db, user, request).issue_leave_grant_batch(batch_id)
    )


@router.post("/leave-grant-batches/{batch_id}/void", response_model=LeaveGrantBatchResponse)
async def void_leave_grant_batch(
    batch_id: UUID,
    payload: LeaveGrantBatchVoid,
    request: Request,
    db: DbSession,
    user: BalanceAdjustUser,
) -> LeaveGrantBatchResponse:
    return LeaveGrantBatchResponse.model_validate(
        await grant_service(db, user, request).void_leave_grant_batch(batch_id, payload.reason)
    )


# —————————————————————— 排班管理（复刻 Moka「排班管理 / 换班记录」）——————————————————————


@router.get("/schedule-types", response_model=ScheduleTypePage)
async def list_schedule_types(
    request: Request,
    db: DbSession,
    user: AdminUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScheduleTypePage:
    items, total = await schedule_service(db, user, request).list_schedule_types(
        limit=limit,
        offset=offset,
    )
    return ScheduleTypePage(
        items=[ScheduleTypeResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/schedule-types", response_model=ScheduleTypeResponse, status_code=201)
async def create_schedule_type(
    payload: ScheduleTypeCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> ScheduleTypeResponse:
    return ScheduleTypeResponse.model_validate(
        await schedule_service(db, user, request).create_schedule_type(payload)
    )


@router.get("/shift-cycles", response_model=ShiftCyclePage)
async def list_shift_cycles(
    request: Request,
    db: DbSession,
    user: AdminUser,
    schedule_type_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ShiftCyclePage:
    items, total = await schedule_service(db, user, request).list_shift_cycles(
        schedule_type_id=schedule_type_id,
        limit=limit,
        offset=offset,
    )
    return ShiftCyclePage(
        items=[ShiftCycleResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/shift-cycles", response_model=ShiftCycleResponse, status_code=201)
async def create_shift_cycle(
    payload: ShiftCycleCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> ShiftCycleResponse:
    return ShiftCycleResponse.model_validate(
        await schedule_service(db, user, request).create_shift_cycle(payload)
    )


@router.get("/flexible-windows", response_model=FlexibleWindowPage)
async def list_flexible_windows(
    request: Request,
    db: DbSession,
    user: AdminUser,
    schedule_type_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> FlexibleWindowPage:
    items, total = await schedule_service(db, user, request).list_flexible_windows(
        schedule_type_id=schedule_type_id,
        limit=limit,
        offset=offset,
    )
    return FlexibleWindowPage(
        items=[FlexibleWindowResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/flexible-windows", response_model=FlexibleWindowResponse, status_code=201)
async def create_flexible_window(
    payload: FlexibleWindowCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> FlexibleWindowResponse:
    return FlexibleWindowResponse.model_validate(
        await schedule_service(db, user, request).create_flexible_window(payload)
    )


@router.post("/schedules/draft", response_model=ScheduleDraftResult, status_code=201)
async def generate_schedule_drafts(
    payload: ScheduleDraftCreate,
    request: Request,
    db: DbSession,
    user: ScheduleWriteUser,
) -> ScheduleDraftResult:
    """批量生成草稿排班。单次最多 1000 条明细，超限整批拒绝。"""
    return await schedule_service(db, user, request).generate_draft_schedules(payload)


@router.get("/schedule-publish-batches", response_model=SchedulePublishBatchPage)
async def list_schedule_publish_batches(
    request: Request,
    db: DbSession,
    user: AdminUser,
    batch_status: str | None = Query(default=None, alias="status", max_length=30),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SchedulePublishBatchPage:
    items, total = await schedule_service(db, user, request).list_publish_batches(
        status=batch_status,
        limit=limit,
        offset=offset,
    )
    return SchedulePublishBatchPage(
        items=[SchedulePublishBatchResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/schedule-publish-batches",
    response_model=SchedulePublishBatchResponse,
    status_code=201,
)
async def create_schedule_publish_batch(
    payload: SchedulePublishBatchCreate,
    request: Request,
    db: DbSession,
    user: ScheduleWriteUser,
) -> SchedulePublishBatchResponse:
    return SchedulePublishBatchResponse.model_validate(
        await schedule_service(db, user, request).create_publish_batch(payload)
    )


@router.post(
    "/schedule-publish-batches/{batch_id}/publish",
    response_model=SchedulePublishBatchResponse,
)
async def publish_schedule_batch(
    batch_id: UUID,
    request: Request,
    db: DbSession,
    user: ScheduleWriteUser,
) -> SchedulePublishBatchResponse:
    """按期间发布草稿排班：草稿行转已发布并挂到本批次。"""
    return SchedulePublishBatchResponse.model_validate(
        await schedule_service(db, user, request).publish_publish_batch(batch_id)
    )


@router.get("/schedule-swaps", response_model=ScheduleSwapPage)
async def list_schedule_swaps(
    request: Request,
    db: DbSession,
    user: AdminUser,
    swap_status: str | None = Query(default=None, alias="status", max_length=30),
    employment_id: UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScheduleSwapPage:
    items, total = await schedule_service(db, user, request).list_swaps(
        status=swap_status,
        employment_id=employment_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return ScheduleSwapPage(
        items=[ScheduleSwapResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/schedule-swaps", response_model=ScheduleSwapResponse, status_code=201)
async def create_schedule_swap(
    payload: ScheduleSwapCreate,
    request: Request,
    db: DbSession,
    user: ScheduleWriteUser,
) -> ScheduleSwapResponse:
    return ScheduleSwapResponse.model_validate(
        await schedule_service(db, user, request).create_swap(payload)
    )


@router.patch("/schedule-swaps/{swap_id}", response_model=ScheduleSwapResponse)
async def decide_schedule_swap(
    swap_id: UUID,
    payload: ScheduleSwapUpdate,
    request: Request,
    db: DbSession,
    user: ScheduleWriteUser,
) -> ScheduleSwapResponse:
    """处理换班记录。批准时双方当日班次互换。"""
    return ScheduleSwapResponse.model_validate(
        await schedule_service(db, user, request).decide_swap(swap_id, payload)
    )
