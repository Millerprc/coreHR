import hashlib
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.errors import ApiError
from hris.modules.attendance.extended_schemas import (
    AttendanceDailyCalculate,
    AttendanceMonthlyCalculate,
    AttendancePeriodFreezeCreate,
    AttendancePeriodFreezeRelease,
    LeaveBalanceTransactionCreate,
    LeaveCancellationCreate,
    LeaveRequestCreate,
    LeaveRequestUpdate,
    LeaveTypeCreate,
    LeaveTypeUpdate,
    PunchCreate,
    ScheduleAssignmentCreate,
    ScheduleAssignmentUpdate,
    ShiftCreate,
    ShiftUpdate,
)
from hris.modules.attendance.models import (
    AttendanceDailyResult,
    AttendanceMonthlyResult,
    AttendancePeriodFreeze,
    AttendancePunch,
    AttendanceRuleSet,
    LeaveBalanceAccount,
    LeaveBalanceTransaction,
    LeaveRequest,
    LeaveType,
    ScheduleAssignment,
    Shift,
)
from hris.modules.platform.numbering import next_number
from hris.modules.workflow.models import WorkflowInstance
from hris.modules.workforce.models import AuditLog, Employment, Person


_ATTENDANCE_PERIOD_LOCK_NAMESPACE = 1_096_049_732


class ExtendedAttendanceService:
    def __init__(self, session: AsyncSession, *, actor_id: UUID, trace_id: str) -> None:
        self._session = session
        self._actor_id = actor_id
        self._trace_id = trace_id

    def _audit(
        self,
        *,
        action: str,
        object_type: str,
        object_id: UUID,
        after: dict[str, Any],
        reason: str | None = None,
        before: dict[str, Any] | None = None,
    ) -> None:
        self._session.add(
            AuditLog(
                occurred_at=datetime.now(UTC),
                actor_id=self._actor_id,
                trace_id=self._trace_id,
                action=action,
                object_type=object_type,
                object_id=object_id,
                reason=reason,
                before_payload=before or {},
                after_payload=after,
                source="api",
            )
        )

    async def create_period_freeze(
        self,
        payload: AttendancePeriodFreezeCreate,
    ) -> AttendancePeriodFreeze:
        await self._lock_period(payload.date_from, payload.date_to)
        freeze = AttendancePeriodFreeze(
            **payload.model_dump(),
            status="active",
            frozen_by=self._actor_id,
            frozen_at=datetime.now(UTC),
        )
        self._session.add(freeze)
        await self._session.flush()
        self._audit(
            action="attendance.period_freeze.create",
            object_type="attendance_period_freeze",
            object_id=freeze.id,
            reason=freeze.reason,
            after={
                "freeze_type": freeze.freeze_type,
                "date_from": freeze.date_from.isoformat(),
                "date_to": freeze.date_to.isoformat(),
                "status": freeze.status,
            },
        )
        return freeze

    async def list_period_freezes(
        self,
        *,
        status: str | None,
        date_from: date | None,
        date_to: date | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AttendancePeriodFreeze], int]:
        if date_from is not None and date_to is not None and date_to < date_from:
            raise ApiError(
                status_code=422,
                code="ATTENDANCE_PERIOD_QUERY_INVALID",
                message="查询结束日期不能早于开始日期",
            )
        filters = []
        if status is not None:
            filters.append(AttendancePeriodFreeze.status == status)
        if date_from is not None:
            filters.append(AttendancePeriodFreeze.date_to >= date_from)
        if date_to is not None:
            filters.append(AttendancePeriodFreeze.date_from <= date_to)
        total = await self._session.scalar(
            select(func.count()).select_from(AttendancePeriodFreeze).where(*filters)
        )
        items = list(
            (
                await self._session.scalars(
                    select(AttendancePeriodFreeze)
                    .where(*filters)
                    .order_by(
                        AttendancePeriodFreeze.date_from.desc(),
                        AttendancePeriodFreeze.frozen_at.desc(),
                    )
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return items, total or 0

    async def release_period_freeze(
        self,
        freeze_id: UUID,
        payload: AttendancePeriodFreezeRelease,
    ) -> AttendancePeriodFreeze:
        freeze = await self._session.get(
            AttendancePeriodFreeze,
            freeze_id,
            with_for_update=True,
        )
        if freeze is None:
            raise ApiError(
                status_code=404,
                code="ATTENDANCE_PERIOD_FREEZE_NOT_FOUND",
                message="考勤冻结记录不存在",
            )
        if freeze.status == "released":
            return freeze
        await self._lock_period(freeze.date_from, freeze.date_to)
        freeze.status = "released"
        freeze.released_by = self._actor_id
        freeze.released_at = datetime.now(UTC)
        freeze.release_reason = payload.reason
        await self._session.flush()
        await self._session.refresh(freeze)
        self._audit(
            action="attendance.period_freeze.release",
            object_type="attendance_period_freeze",
            object_id=freeze.id,
            reason=payload.reason,
            before={"status": "active"},
            after={"status": freeze.status},
        )
        return freeze

    async def _assert_period_not_frozen(
        self,
        date_from: date,
        date_to: date,
    ) -> None:
        await self._lock_period(date_from, date_to)
        freezes = list(
            (
                await self._session.scalars(
                    select(AttendancePeriodFreeze)
                    .where(
                        AttendancePeriodFreeze.status == "active",
                        AttendancePeriodFreeze.date_from <= date_to,
                        AttendancePeriodFreeze.date_to >= date_from,
                    )
                    .order_by(
                        AttendancePeriodFreeze.date_from,
                        AttendancePeriodFreeze.frozen_at,
                    )
                    .limit(20)
                )
            ).all()
        )
        if not freezes:
            return
        raise ApiError(
            status_code=409,
            code="ATTENDANCE_PERIOD_FROZEN",
            message="所选日期处于考勤冻结期间，需先填写原因并解冻",
            details=[
                {
                    "freeze_id": str(item.id),
                    "freeze_type": item.freeze_type,
                    "date_from": item.date_from.isoformat(),
                    "date_to": item.date_to.isoformat(),
                }
                for item in freezes
            ],
        )

    async def _lock_period(self, date_from: date, date_to: date) -> None:
        cursor = date(date_from.year, date_from.month, 1)
        last_month = date(date_to.year, date_to.month, 1)
        while cursor <= last_month:
            month_key = cursor.year * 100 + cursor.month
            await self._session.execute(
                select(
                    func.pg_advisory_xact_lock(
                        _ATTENDANCE_PERIOD_LOCK_NAMESPACE,
                        month_key,
                    )
                )
            )
            cursor = self._next_month(cursor)

    async def list_employment_options(
        self,
        *,
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
        filters = []
        if search:
            term = f"%{search.strip()}%"
            filters.append(or_(Person.display_name.ilike(term), Person.employee_number.ilike(term)))
        total = await self._session.scalar(
            select(func.count()).select_from(Employment).join(Person, Person.id == Employment.person_id).where(*filters)
        )
        rows = (
            await self._session.execute(
                select(
                    Employment.id,
                    Employment.person_id,
                    Person.employee_number,
                    Person.display_name,
                    Employment.employee_type_code,
                    Employment.status,
                )
                .join(Person, Person.id == Employment.person_id)
                .where(*filters)
                .order_by(Person.employee_number, Person.display_name)
                .limit(limit)
                .offset(offset)
            )
        ).mappings().all()
        return [dict(row) for row in rows], total or 0

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

    async def list_shifts(
        self,
        *,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Shift], int]:
        filters = [Shift.status == status] if status else []
        total = await self._session.scalar(select(func.count()).select_from(Shift).where(*filters))
        items = list(
            (
                await self._session.scalars(
                    select(Shift).where(*filters).order_by(Shift.code).limit(limit).offset(offset)
                )
            ).all()
        )
        return items, total or 0

    async def update_shift(self, shift_id: UUID, payload: ShiftUpdate) -> Shift:
        shift = await self._session.get(Shift, shift_id, with_for_update=True)
        if shift is None:
            raise ApiError(status_code=404, code="SHIFT_NOT_FOUND", message="shift not found")
        changes = payload.model_dump(exclude_unset=True)
        rule_set_id = changes.get("rule_set_id")
        if rule_set_id is not None and await self._session.get(AttendanceRuleSet, rule_set_id) is None:
            raise ApiError(status_code=404, code="RULE_SET_NOT_FOUND", message="attendance rule set not found")
        start_time = changes.get("start_time", shift.start_time)
        end_time = changes.get("end_time", shift.end_time)
        crosses_midnight = changes.get("crosses_midnight", shift.crosses_midnight)
        if crosses_midnight and end_time > start_time:
            raise ApiError(status_code=422, code="SHIFT_TIME_RANGE_INVALID", message="invalid overnight shift time range")
        if not crosses_midnight and end_time <= start_time:
            raise ApiError(status_code=422, code="SHIFT_TIME_RANGE_INVALID", message="invalid shift time range")
        before = {field: str(getattr(shift, field)) for field in changes}
        for field, value in changes.items():
            setattr(shift, field, value)
        await self._session.flush()
        self._audit(
            action="update",
            object_type="shift",
            object_id=shift.id,
            before=before,
            after={field: str(value) for field, value in changes.items()},
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

    async def list_schedules(
        self,
        *,
        employment_id: UUID | None,
        date_from: date | None,
        date_to: date | None,
        limit: int,
        offset: int,
    ) -> tuple[list[ScheduleAssignment], int]:
        filters = []
        if employment_id is not None:
            filters.append(ScheduleAssignment.employment_id == employment_id)
        if date_from is not None:
            filters.append(ScheduleAssignment.work_date >= date_from)
        if date_to is not None:
            filters.append(ScheduleAssignment.work_date <= date_to)
        total = await self._session.scalar(
            select(func.count()).select_from(ScheduleAssignment).where(*filters)
        )
        items = list(
            (
                await self._session.scalars(
                    select(ScheduleAssignment)
                    .where(*filters)
                    .order_by(ScheduleAssignment.work_date.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return items, total or 0

    async def update_schedule(
        self,
        schedule_id: UUID,
        payload: ScheduleAssignmentUpdate,
    ) -> ScheduleAssignment:
        schedule = await self._session.get(ScheduleAssignment, schedule_id, with_for_update=True)
        if schedule is None:
            raise ApiError(status_code=404, code="SCHEDULE_NOT_FOUND", message="schedule not found")
        changes = payload.model_dump(exclude_unset=True)
        shift_id = changes.get("shift_id")
        if shift_id is not None and await self._session.get(Shift, shift_id) is None:
            raise ApiError(status_code=404, code="SHIFT_NOT_FOUND", message="shift not found")
        before = {field: str(getattr(schedule, field)) for field in changes}
        for field, value in changes.items():
            setattr(schedule, field, value)
        await self._session.flush()
        self._audit(
            action="update",
            object_type="schedule_assignment",
            object_id=schedule.id,
            before=before,
            after={field: str(value) for field, value in changes.items()},
        )
        return schedule

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

    async def list_punches(
        self,
        *,
        employment_id: UUID | None,
        punched_from: datetime | None,
        punched_to: datetime | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AttendancePunch], int]:
        filters = []
        if employment_id is not None:
            filters.append(AttendancePunch.employment_id == employment_id)
        if punched_from is not None:
            filters.append(AttendancePunch.punched_at >= punched_from)
        if punched_to is not None:
            filters.append(AttendancePunch.punched_at <= punched_to)
        total = await self._session.scalar(
            select(func.count()).select_from(AttendancePunch).where(*filters)
        )
        items = list(
            (
                await self._session.scalars(
                    select(AttendancePunch)
                    .where(*filters)
                    .order_by(AttendancePunch.punched_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return items, total or 0

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

    async def list_leave_types(
        self,
        *,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[LeaveType], int]:
        filters = [LeaveType.status == status] if status else []
        total = await self._session.scalar(select(func.count()).select_from(LeaveType).where(*filters))
        items = list(
            (
                await self._session.scalars(
                    select(LeaveType).where(*filters).order_by(LeaveType.code).limit(limit).offset(offset)
                )
            ).all()
        )
        return items, total or 0

    async def update_leave_type(self, leave_type_id: UUID, payload: LeaveTypeUpdate) -> LeaveType:
        leave_type = await self._session.get(LeaveType, leave_type_id, with_for_update=True)
        if leave_type is None:
            raise ApiError(status_code=404, code="LEAVE_TYPE_NOT_FOUND", message="leave type not found")
        changes = payload.model_dump(exclude_unset=True)
        if "unit" in changes and changes["unit"] != leave_type.unit:
            account_exists = await self._session.scalar(
                select(LeaveBalanceAccount.id).where(
                    LeaveBalanceAccount.leave_type_id == leave_type.id
                )
            )
            if account_exists is not None:
                raise ApiError(
                    status_code=409,
                    code="LEAVE_BALANCE_UNIT_IN_USE",
                    message="leave type unit cannot change after balance accounts exist",
                )
        before = {field: getattr(leave_type, field) for field in changes}
        for field, value in changes.items():
            setattr(leave_type, field, value)
        await self._session.flush()
        self._audit(
            action="update",
            object_type="leave_type",
            object_id=leave_type.id,
            before=before,
            after=changes,
        )
        return leave_type

    async def create_leave_balance_transaction(
        self,
        payload: LeaveBalanceTransactionCreate,
    ) -> LeaveBalanceTransaction:
        if await self._session.get(Employment, payload.employment_id) is None:
            raise ApiError(
                status_code=404,
                code="EMPLOYMENT_NOT_FOUND",
                message="employment not found",
            )
        leave_type = await self._session.get(LeaveType, payload.leave_type_id)
        if leave_type is None:
            raise ApiError(
                status_code=404,
                code="LEAVE_TYPE_NOT_FOUND",
                message="leave type not found",
            )
        if self._leave_balance_mode(leave_type) == "none":
            raise ApiError(
                status_code=409,
                code="LEAVE_BALANCE_NOT_TRACKED",
                message="leave type is not configured to track a balance",
            )
        return await self._apply_balance_delta(
            employment_id=payload.employment_id,
            leave_type=leave_type,
            period_year=payload.period_year,
            transaction_type=payload.transaction_type,
            amount=payload.amount,
            effective_date=payload.effective_date,
            source_type="manual",
            source_id=None,
            idempotency_key=payload.idempotency_key,
            reason=payload.reason,
            enforce_nonnegative=False,
        )

    async def list_leave_balance_accounts(
        self,
        *,
        employment_id: UUID | None,
        leave_type_id: UUID | None,
        period_year: int | None,
        limit: int,
        offset: int,
    ) -> tuple[list[LeaveBalanceAccount], int]:
        filters = []
        if employment_id is not None:
            filters.append(LeaveBalanceAccount.employment_id == employment_id)
        if leave_type_id is not None:
            filters.append(LeaveBalanceAccount.leave_type_id == leave_type_id)
        if period_year is not None:
            filters.append(LeaveBalanceAccount.period_year == period_year)
        total = await self._session.scalar(
            select(func.count()).select_from(LeaveBalanceAccount).where(*filters)
        )
        accounts = list(
            (
                await self._session.scalars(
                    select(LeaveBalanceAccount)
                    .where(*filters)
                    .order_by(
                        LeaveBalanceAccount.period_year.desc(),
                        LeaveBalanceAccount.updated_at.desc(),
                    )
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return accounts, total or 0

    async def list_leave_balance_transactions(
        self,
        account_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[LeaveBalanceTransaction], int]:
        if await self._session.get(LeaveBalanceAccount, account_id) is None:
            raise ApiError(
                status_code=404,
                code="LEAVE_BALANCE_ACCOUNT_NOT_FOUND",
                message="leave balance account not found",
            )
        total = await self._session.scalar(
            select(func.count())
            .select_from(LeaveBalanceTransaction)
            .where(LeaveBalanceTransaction.account_id == account_id)
        )
        transactions = list(
            (
                await self._session.scalars(
                    select(LeaveBalanceTransaction)
                    .where(LeaveBalanceTransaction.account_id == account_id)
                    .order_by(
                        LeaveBalanceTransaction.account_version.desc(),
                    )
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return transactions, total or 0

    async def _apply_balance_delta(
        self,
        *,
        employment_id: UUID,
        leave_type: LeaveType,
        period_year: int,
        transaction_type: str,
        amount: Decimal,
        effective_date: date,
        source_type: str,
        source_id: UUID | None,
        idempotency_key: UUID,
        reason: str,
        enforce_nonnegative: bool,
    ) -> LeaveBalanceTransaction:
        checksum = self._balance_transaction_checksum(
            employment_id=employment_id,
            leave_type_id=leave_type.id,
            period_year=period_year,
            transaction_type=transaction_type,
            amount=amount,
            effective_date=effective_date,
            source_type=source_type,
            source_id=source_id,
            reason=reason,
        )
        await self._lock_leave_balance_idempotency(idempotency_key)
        existing = await self._session.scalar(
            select(LeaveBalanceTransaction).where(
                LeaveBalanceTransaction.idempotency_key == idempotency_key
            )
        )
        if existing is not None:
            if existing.request_checksum != checksum:
                raise ApiError(
                    status_code=409,
                    code="LEAVE_BALANCE_IDEMPOTENCY_CONFLICT",
                    message="idempotency key has already been used for another transaction",
                )
            return existing

        await self._lock_leave_balance_scope(
            employment_id,
            leave_type.id,
            period_year,
        )
        account = await self._session.scalar(
            select(LeaveBalanceAccount)
            .where(
                LeaveBalanceAccount.employment_id == employment_id,
                LeaveBalanceAccount.leave_type_id == leave_type.id,
                LeaveBalanceAccount.period_year == period_year,
            )
            .with_for_update()
        )
        if account is None:
            account = LeaveBalanceAccount(
                employment_id=employment_id,
                leave_type_id=leave_type.id,
                period_year=period_year,
                unit=leave_type.unit,
                current_balance=Decimal("0.00"),
                version=0,
                status="active",
            )
            self._session.add(account)
            await self._session.flush()
        if account.status != "active":
            raise ApiError(
                status_code=409,
                code="LEAVE_BALANCE_ACCOUNT_CLOSED",
                message="leave balance account is closed",
            )

        balance_before = Decimal(account.current_balance)
        balance_after = balance_before + Decimal(amount)
        if enforce_nonnegative and balance_after < 0:
            raise ApiError(
                status_code=409,
                code="LEAVE_BALANCE_INSUFFICIENT",
                message="available leave balance is insufficient",
                details=[
                    {
                        "available": str(balance_before),
                        "requested": str(-Decimal(amount)),
                        "period_year": period_year,
                    }
                ],
            )
        account.version += 1
        transaction = LeaveBalanceTransaction(
            account_id=account.id,
            transaction_type=transaction_type,
            amount=amount,
            effective_date=effective_date,
            balance_before=balance_before,
            balance_after=balance_after,
            account_version=account.version,
            source_type=source_type,
            source_id=source_id,
            idempotency_key=idempotency_key,
            request_checksum=checksum,
            reason=reason,
            actor_id=self._actor_id,
        )
        account.current_balance = balance_after
        self._session.add(transaction)
        await self._session.flush()
        self._audit(
            action="attendance.leave_balance.post",
            object_type="leave_balance_transaction",
            object_id=transaction.id,
            reason=reason,
            before={"balance": str(balance_before), "version": account.version - 1},
            after={
                "account_id": str(account.id),
                "transaction_type": transaction_type,
                "amount": str(amount),
                "balance": str(balance_after),
                "version": account.version,
            },
        )
        return transaction

    async def _apply_leave_usage(
        self,
        request: LeaveRequest,
        leave_type: LeaveType,
    ) -> None:
        balance_mode = self._leave_balance_mode(leave_type)
        if balance_mode == "none":
            return
        if request.start_date.year != request.end_date.year:
            raise ApiError(
                status_code=422,
                code="LEAVE_BALANCE_CROSS_YEAR_UNSUPPORTED",
                message="managed leave requests must be split by calendar year",
            )
        await self._apply_balance_delta(
            employment_id=request.employment_id,
            leave_type=leave_type,
            period_year=request.start_date.year,
            transaction_type="usage",
            amount=-Decimal(request.amount),
            effective_date=request.start_date,
            source_type="leave_request",
            source_id=request.id,
            idempotency_key=uuid5(
                NAMESPACE_URL,
                f"corehr:leave-balance:usage:{request.id}",
            ),
            reason=f"leave request {request.request_number} approved",
            enforce_nonnegative=balance_mode == "enforced",
        )

    async def _reverse_leave_usage(
        self,
        original: LeaveRequest,
    ) -> None:
        usage = await self._session.scalar(
            select(LeaveBalanceTransaction).where(
                LeaveBalanceTransaction.transaction_type == "usage",
                LeaveBalanceTransaction.source_type == "leave_request",
                LeaveBalanceTransaction.source_id == original.id,
            )
        )
        if usage is None:
            return
        account = await self._session.get(LeaveBalanceAccount, usage.account_id)
        if account is None:
            raise ApiError(
                status_code=422,
                code="LEAVE_BALANCE_ACCOUNT_MISSING",
                message="leave balance account for the approved request is missing",
            )
        leave_type = await self._session.get(LeaveType, account.leave_type_id)
        if leave_type is None:
            raise ApiError(
                status_code=422,
                code="LEAVE_TYPE_NOT_FOUND",
                message="leave type for the approved request is missing",
            )
        await self._apply_balance_delta(
            employment_id=account.employment_id,
            leave_type=leave_type,
            period_year=account.period_year,
            transaction_type="reversal",
            amount=-Decimal(usage.amount),
            effective_date=original.start_date,
            source_type="leave_request",
            source_id=original.id,
            idempotency_key=uuid5(
                NAMESPACE_URL,
                f"corehr:leave-balance:reversal:{original.id}",
            ),
            reason=f"leave request {original.request_number} cancelled",
            enforce_nonnegative=False,
        )

    @staticmethod
    def _leave_balance_mode(leave_type: LeaveType) -> str:
        balance_mode = leave_type.rules.get("balance_mode", "none")
        if balance_mode not in {"none", "tracked", "enforced"}:
            raise ApiError(
                status_code=422,
                code="LEAVE_BALANCE_MODE_INVALID",
                message="leave type has an invalid balance mode",
            )
        return str(balance_mode)

    @staticmethod
    def _balance_transaction_checksum(
        *,
        employment_id: UUID,
        leave_type_id: UUID,
        period_year: int,
        transaction_type: str,
        amount: Decimal,
        effective_date: date,
        source_type: str,
        source_id: UUID | None,
        reason: str,
    ) -> str:
        value = "|".join(
            [
                str(employment_id),
                str(leave_type_id),
                str(period_year),
                transaction_type,
                format(Decimal(amount).quantize(Decimal("0.01")), "f"),
                effective_date.isoformat(),
                source_type,
                str(source_id or ""),
                reason,
            ]
        )
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    async def _lock_leave_balance_idempotency(self, key: UUID) -> None:
        lock_key = key.int & ((1 << 63) - 1)
        await self._session.execute(select(func.pg_advisory_xact_lock(lock_key)))

    async def _lock_leave_balance_scope(
        self,
        employment_id: UUID,
        leave_type_id: UUID,
        period_year: int,
    ) -> None:
        digest = hashlib.sha256(
            f"{employment_id}:{leave_type_id}:{period_year}".encode("ascii")
        ).digest()
        lock_key = int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)
        await self._session.execute(select(func.pg_advisory_xact_lock(lock_key)))

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

    async def list_leave_requests(
        self,
        *,
        status: str | None,
        employment_id: UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[LeaveRequest], int]:
        filters = []
        if status is not None:
            filters.append(LeaveRequest.status == status)
        if employment_id is not None:
            filters.append(LeaveRequest.employment_id == employment_id)
        total = await self._session.scalar(
            select(func.count()).select_from(LeaveRequest).where(*filters)
        )
        items = list(
            (
                await self._session.scalars(
                    select(LeaveRequest)
                    .where(*filters)
                    .order_by(LeaveRequest.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return items, total or 0

    async def update_leave_request(
        self,
        request_id: UUID,
        payload: LeaveRequestUpdate,
    ) -> LeaveRequest:
        request = await self._session.get(LeaveRequest, request_id, with_for_update=True)
        if request is None:
            raise ApiError(status_code=404, code="LEAVE_REQUEST_NOT_FOUND", message="leave request not found")
        allowed = {
            "draft": {"draft", "approved", "rejected", "cancelled"},
            "pending_approval": {"approved", "rejected", "cancelled"},
            "draft_cancellation": {"approved", "rejected", "cancelled"},
            "approved": {"approved", "cancelled"},
            "rejected": {"rejected"},
            "cancelled": {"cancelled"},
        }
        if payload.status not in allowed.get(request.status, set()):
            raise ApiError(
                status_code=409,
                code="LEAVE_STATUS_TRANSITION_INVALID",
                message="leave request status transition is not allowed",
            )
        before_status = request.status
        if (
            payload.status == "approved"
            and request.cancellation_of_id is None
            and before_status != "approved"
        ):
            overlap = await self._session.scalar(
                select(LeaveRequest.id).where(
                    LeaveRequest.employment_id == request.employment_id,
                    LeaveRequest.status == "approved",
                    LeaveRequest.cancellation_of_id.is_(None),
                    LeaveRequest.id != request.id,
                    LeaveRequest.start_date <= request.end_date,
                    LeaveRequest.end_date >= request.start_date,
                )
            )
            if overlap is not None:
                raise ApiError(
                    status_code=409,
                    code="LEAVE_REQUEST_OVERLAPS",
                    message="approved leave request overlaps an existing approved leave",
                )
            leave_type = await self._session.get(LeaveType, request.leave_type_id)
            if leave_type is None:
                raise ApiError(
                    status_code=422,
                    code="LEAVE_TYPE_NOT_FOUND",
                    message="leave type not found",
                )
            await self._apply_leave_usage(request, leave_type)
        if (
            payload.status == "approved"
            and request.cancellation_of_id is not None
            and before_status != "approved"
        ):
            original = await self._session.get(LeaveRequest, request.cancellation_of_id, with_for_update=True)
            if original is None:
                raise ApiError(status_code=422, code="LEAVE_ORIGINAL_MISSING", message="original leave request not found")
            await self._reverse_leave_usage(original)
            original.status = "cancelled"
        if (
            payload.status == "cancelled"
            and request.cancellation_of_id is None
            and before_status == "approved"
        ):
            await self._reverse_leave_usage(request)
        request.status = payload.status
        await self._session.flush()
        self._audit(
            action="status_change",
            object_type="leave_request",
            object_id=request.id,
            reason=payload.change_reason,
            before={"status": before_status},
            after={"status": request.status},
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

    async def calculate_daily(
        self,
        payload: AttendanceDailyCalculate,
    ) -> AttendanceDailyResult:
        if await self._session.get(Employment, payload.employment_id) is None:
            raise ApiError(status_code=404, code="EMPLOYMENT_NOT_FOUND", message="employment not found")
        await self._assert_period_not_frozen(payload.work_date, payload.work_date)
        schedule = await self._session.scalar(
            select(ScheduleAssignment).where(
                ScheduleAssignment.employment_id == payload.employment_id,
                ScheduleAssignment.work_date == payload.work_date,
                ScheduleAssignment.status == "active",
            )
        )
        scheduled_minutes = 0
        worked_minutes = 0
        late_minutes = 0
        early_leave_minutes = 0
        exception_codes: list[str] = []
        evidence: dict[str, Any] = {"calculation_reason": payload.reason}
        status = "unscheduled"

        if schedule is None:
            exception_codes.append("NO_SCHEDULE")
        else:
            shift = await self._session.get(Shift, schedule.shift_id)
            if shift is None:
                raise ApiError(status_code=422, code="SHIFT_NOT_FOUND", message="scheduled shift not found")
            rule_set = await self._session.get(AttendanceRuleSet, shift.rule_set_id)
            if rule_set is None:
                raise ApiError(status_code=422, code="RULE_SET_NOT_FOUND", message="attendance rule set not found")
            timezone = ZoneInfo(rule_set.timezone)
            scheduled_start = datetime.combine(payload.work_date, shift.start_time, tzinfo=timezone)
            end_date = payload.work_date + timedelta(days=1) if shift.crosses_midnight else payload.work_date
            scheduled_end = datetime.combine(end_date, shift.end_time, tzinfo=timezone)
            scheduled_minutes = max(0, int((scheduled_end - scheduled_start).total_seconds() // 60))
            grace_late = int(rule_set.rules.get("late_grace_minutes", 0) or 0)
            grace_early = int(rule_set.rules.get("early_leave_grace_minutes", 0) or 0)
            punches = list(
                (
                    await self._session.scalars(
                        select(AttendancePunch)
                        .where(
                            AttendancePunch.employment_id == payload.employment_id,
                            AttendancePunch.punched_at >= scheduled_start - timedelta(hours=6),
                            AttendancePunch.punched_at <= scheduled_end + timedelta(hours=6),
                        )
                        .order_by(AttendancePunch.punched_at)
                    )
                ).all()
            )
            leave = await self._session.scalar(
                select(LeaveRequest)
                .where(
                    LeaveRequest.employment_id == payload.employment_id,
                    LeaveRequest.status == "approved",
                    LeaveRequest.cancellation_of_id.is_(None),
                    LeaveRequest.start_date <= payload.work_date,
                    LeaveRequest.end_date >= payload.work_date,
                )
                .order_by(LeaveRequest.created_at.desc())
                .limit(1)
            )
            in_punches = [item for item in punches if item.punch_type == "in"]
            out_punches = [item for item in punches if item.punch_type == "out"]
            first_punch = min(in_punches or punches, key=lambda item: item.punched_at) if punches else None
            last_punch = max(out_punches or punches, key=lambda item: item.punched_at) if punches else None
            has_pair = (
                first_punch is not None
                and last_punch is not None
                and first_punch.id != last_punch.id
                and last_punch.punched_at > first_punch.punched_at
            )
            if first_punch is not None:
                late_minutes = max(
                    0,
                    int((first_punch.punched_at - scheduled_start).total_seconds() // 60) - grace_late,
                )
            if last_punch is not None:
                early_leave_minutes = max(
                    0,
                    int((scheduled_end - last_punch.punched_at).total_seconds() // 60) - grace_early,
                )
            if has_pair and first_punch is not None and last_punch is not None:
                worked_minutes = max(
                    0,
                    int((last_punch.punched_at - first_punch.punched_at).total_seconds() // 60),
                )
            if not punches:
                if leave is not None:
                    status = "leave"
                else:
                    status = "absent"
                    exception_codes.append("NO_PUNCH")
            elif not has_pair:
                status = "exception"
                exception_codes.append("MISSING_PUNCH")
            elif leave is not None:
                status = "leave_with_punch"
            elif late_minutes or early_leave_minutes:
                status = "exception"
            else:
                status = "normal"
            if late_minutes:
                exception_codes.append("LATE")
            if early_leave_minutes:
                exception_codes.append("EARLY_LEAVE")
            evidence.update(
                {
                    "schedule_id": str(schedule.id),
                    "shift_id": str(shift.id),
                    "rule_set_id": str(rule_set.id),
                    "rule_set_version": rule_set.version,
                    "timezone": rule_set.timezone,
                    "scheduled_start": scheduled_start.isoformat(),
                    "scheduled_end": scheduled_end.isoformat(),
                    "punch_ids": [str(item.id) for item in punches],
                    "punch_times": [item.punched_at.isoformat() for item in punches],
                    "leave_request_id": str(leave.id) if leave is not None else None,
                }
            )

        previous = list(
            (
                await self._session.scalars(
                    select(AttendanceDailyResult).where(
                        AttendanceDailyResult.employment_id == payload.employment_id,
                        AttendanceDailyResult.work_date == payload.work_date,
                    )
                )
            ).all()
        )
        for item in previous:
            item.is_current = False
        version = max((item.version for item in previous), default=0) + 1
        result = AttendanceDailyResult(
            employment_id=payload.employment_id,
            work_date=payload.work_date,
            status=status,
            scheduled_minutes=scheduled_minutes,
            worked_minutes=worked_minutes,
            late_minutes=late_minutes,
            early_leave_minutes=early_leave_minutes,
            exception_codes=exception_codes,
            evidence=evidence,
            version=version,
            is_current=True,
        )
        self._session.add(result)
        await self._session.flush()
        self._audit(
            action="calculate",
            object_type="attendance_daily_result",
            object_id=result.id,
            reason=payload.reason,
            after={"status": result.status, "version": result.version},
        )
        return result

    async def list_daily_results(
        self,
        *,
        employment_id: UUID | None,
        date_from: date | None,
        date_to: date | None,
        current_only: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[AttendanceDailyResult], int]:
        filters = []
        if employment_id is not None:
            filters.append(AttendanceDailyResult.employment_id == employment_id)
        if date_from is not None:
            filters.append(AttendanceDailyResult.work_date >= date_from)
        if date_to is not None:
            filters.append(AttendanceDailyResult.work_date <= date_to)
        if current_only:
            filters.append(AttendanceDailyResult.is_current.is_(True))
        total = await self._session.scalar(
            select(func.count()).select_from(AttendanceDailyResult).where(*filters)
        )
        items = list(
            (
                await self._session.scalars(
                    select(AttendanceDailyResult)
                    .where(*filters)
                    .order_by(AttendanceDailyResult.work_date.desc(), AttendanceDailyResult.version.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return items, total or 0

    @staticmethod
    def _next_month(period_month: date) -> date:
        return date(period_month.year + (period_month.month == 12), 1 if period_month.month == 12 else period_month.month + 1, 1)

    async def calculate_monthly(
        self,
        payload: AttendanceMonthlyCalculate,
    ) -> AttendanceMonthlyResult:
        if await self._session.get(Employment, payload.employment_id) is None:
            raise ApiError(status_code=404, code="EMPLOYMENT_NOT_FOUND", message="employment not found")
        next_month = self._next_month(payload.period_month)
        await self._assert_period_not_frozen(
            payload.period_month,
            next_month - timedelta(days=1),
        )
        schedules = list(
            (
                await self._session.scalars(
                    select(ScheduleAssignment).where(
                        ScheduleAssignment.employment_id == payload.employment_id,
                        ScheduleAssignment.status == "active",
                        ScheduleAssignment.work_date >= payload.period_month,
                        ScheduleAssignment.work_date < next_month,
                    )
                )
            ).all()
        )
        for schedule in schedules:
            existing = await self._session.scalar(
                select(AttendanceDailyResult.id).where(
                    AttendanceDailyResult.employment_id == payload.employment_id,
                    AttendanceDailyResult.work_date == schedule.work_date,
                    AttendanceDailyResult.is_current.is_(True),
                )
            )
            if existing is None:
                await self.calculate_daily(
                    AttendanceDailyCalculate(
                        employment_id=payload.employment_id,
                        work_date=schedule.work_date,
                        reason=f"monthly aggregation: {payload.reason}",
                    )
                )
        daily_results = list(
            (
                await self._session.scalars(
                    select(AttendanceDailyResult).where(
                        AttendanceDailyResult.employment_id == payload.employment_id,
                        AttendanceDailyResult.work_date >= payload.period_month,
                        AttendanceDailyResult.work_date < next_month,
                        AttendanceDailyResult.is_current.is_(True),
                    )
                )
            ).all()
        )
        scheduled_days = Decimal(sum(1 for item in daily_results if item.scheduled_minutes > 0))
        worked_days = Decimal(sum(1 for item in daily_results if item.worked_minutes > 0))
        leave_days = Decimal(sum(1 for item in daily_results if item.status == "leave"))
        absent_days = Decimal(sum(1 for item in daily_results if item.status == "absent"))
        previous = list(
            (
                await self._session.scalars(
                    select(AttendanceMonthlyResult).where(
                        AttendanceMonthlyResult.employment_id == payload.employment_id,
                        AttendanceMonthlyResult.period_month == payload.period_month,
                    )
                )
            ).all()
        )
        for item in previous:
            item.is_current = False
        version = max((item.version for item in previous), default=0) + 1
        result = AttendanceMonthlyResult(
            employment_id=payload.employment_id,
            period_month=payload.period_month,
            scheduled_days=scheduled_days,
            worked_days=worked_days,
            leave_days=leave_days,
            absent_days=absent_days,
            late_minutes=sum(item.late_minutes for item in daily_results),
            early_leave_minutes=sum(item.early_leave_minutes for item in daily_results),
            version=version,
            is_current=True,
            status="calculated",
        )
        self._session.add(result)
        await self._session.flush()
        self._audit(
            action="calculate",
            object_type="attendance_monthly_result",
            object_id=result.id,
            reason=payload.reason,
            after={"period_month": result.period_month.isoformat(), "version": result.version},
        )
        return result

    async def list_monthly_results(
        self,
        *,
        employment_id: UUID | None,
        period_month: date | None,
        current_only: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[AttendanceMonthlyResult], int]:
        filters = []
        if employment_id is not None:
            filters.append(AttendanceMonthlyResult.employment_id == employment_id)
        if period_month is not None:
            filters.append(AttendanceMonthlyResult.period_month == period_month)
        if current_only:
            filters.append(AttendanceMonthlyResult.is_current.is_(True))
        total = await self._session.scalar(
            select(func.count()).select_from(AttendanceMonthlyResult).where(*filters)
        )
        items = list(
            (
                await self._session.scalars(
                    select(AttendanceMonthlyResult)
                    .where(*filters)
                    .order_by(AttendanceMonthlyResult.period_month.desc(), AttendanceMonthlyResult.version.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return items, total or 0
