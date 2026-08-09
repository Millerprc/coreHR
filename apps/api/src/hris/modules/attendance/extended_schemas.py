from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


_BALANCE_MODES = {"none", "tracked", "enforced"}


def _validate_balance_rules(rules: dict[str, Any]) -> None:
    balance_mode = rules.get("balance_mode", "none")
    if balance_mode not in _BALANCE_MODES:
        raise ValueError("rules.balance_mode must be none, tracked, or enforced")


class AttendanceEmploymentOption(BaseModel):
    id: UUID
    person_id: UUID
    employee_number: str | None
    display_name: str
    employee_type_code: str
    status: str


class AttendanceEmploymentOptionPage(BaseModel):
    items: list[AttendanceEmploymentOption]
    total: int
    limit: int
    offset: int


class ShiftCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    start_time: time
    end_time: time
    crosses_midnight: bool = False
    rule_set_id: UUID

    @model_validator(mode="after")
    def validate_time_range(self) -> "ShiftCreate":
        if self.crosses_midnight and self.end_time > self.start_time:
            raise ValueError("跨午夜班次的结束时间应早于或等于开始时间")
        if not self.crosses_midnight and self.end_time <= self.start_time:
            raise ValueError("非跨午夜班次的结束时间必须晚于开始时间")
        return self


class ShiftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    start_time: time
    end_time: time
    crosses_midnight: bool
    rule_set_id: UUID
    status: str


class ShiftUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    start_time: time | None = None
    end_time: time | None = None
    crosses_midnight: bool | None = None
    rule_set_id: UUID | None = None
    status: Literal["active", "inactive"] | None = None

    @model_validator(mode="after")
    def validate_change(self) -> "ShiftUpdate":
        if not self.model_dump(exclude_unset=True):
            raise ValueError("at least one shift field must be changed")
        return self


class ShiftPage(BaseModel):
    items: list[ShiftResponse]
    total: int
    limit: int
    offset: int


class ScheduleAssignmentCreate(BaseModel):
    employment_id: UUID
    work_date: date
    shift_id: UUID
    source: str = Field(default="manual", min_length=1, max_length=50)


class ScheduleAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employment_id: UUID
    work_date: date
    shift_id: UUID
    source: str
    status: str


class ScheduleAssignmentUpdate(BaseModel):
    shift_id: UUID | None = None
    source: str | None = Field(default=None, min_length=1, max_length=50)
    status: Literal["active", "cancelled"] | None = None

    @model_validator(mode="after")
    def validate_change(self) -> "ScheduleAssignmentUpdate":
        if not self.model_dump(exclude_unset=True):
            raise ValueError("at least one schedule field must be changed")
        return self


class ScheduleAssignmentPage(BaseModel):
    items: list[ScheduleAssignmentResponse]
    total: int
    limit: int
    offset: int


class PunchCreate(BaseModel):
    employment_id: UUID
    punched_at: datetime
    punch_type: Literal["in", "out"] | None = None
    source: str = Field(min_length=1, max_length=50)
    source_record_id: str = Field(min_length=1, max_length=100)
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_timezone(self) -> "PunchCreate":
        if self.punched_at.tzinfo is None or self.punched_at.utcoffset() is None:
            raise ValueError("punched_at必须包含时区")
        return self


class PunchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employment_id: UUID
    punched_at: datetime
    punch_type: str | None
    source: str
    source_record_id: str
    raw_payload: dict[str, Any]


class PunchIngestResponse(BaseModel):
    duplicate: bool
    record: PunchResponse


class PunchPage(BaseModel):
    items: list[PunchResponse]
    total: int
    limit: int
    offset: int


class LeaveTypeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    unit: Literal["day", "hour"]
    rules: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_rules(self) -> "LeaveTypeCreate":
        _validate_balance_rules(self.rules)
        return self


class LeaveTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    unit: str
    status: str
    rules: dict[str, Any]


class LeaveTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    unit: Literal["day", "hour"] | None = None
    status: Literal["active", "inactive"] | None = None
    rules: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_change(self) -> "LeaveTypeUpdate":
        if not self.model_dump(exclude_unset=True):
            raise ValueError("at least one leave-type field must be changed")
        if self.rules is not None:
            _validate_balance_rules(self.rules)
        return self


class LeaveTypePage(BaseModel):
    items: list[LeaveTypeResponse]
    total: int
    limit: int
    offset: int


class LeaveRequestCreate(BaseModel):
    employment_id: UUID
    leave_type_id: UUID
    start_date: date
    end_date: date
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    reason: str = Field(min_length=1, max_length=5000)
    workflow_instance_id: UUID | None = None

    @model_validator(mode="after")
    def validate_period(self) -> "LeaveRequestCreate":
        if self.end_date < self.start_date:
            raise ValueError("end_date不能早于start_date")
        return self


class LeaveRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_number: str
    employment_id: UUID
    leave_type_id: UUID
    start_date: date
    end_date: date
    amount: Decimal
    status: str
    reason: str
    workflow_instance_id: UUID | None
    cancellation_of_id: UUID | None


class LeaveCancellationCreate(BaseModel):
    reason: str = Field(min_length=1, max_length=5000)
    workflow_instance_id: UUID | None = None


class LeaveRequestUpdate(BaseModel):
    status: Literal["draft", "approved", "rejected", "cancelled"]
    change_reason: str = Field(min_length=1, max_length=500)


class LeaveRequestPage(BaseModel):
    items: list[LeaveRequestResponse]
    total: int
    limit: int
    offset: int


class LeaveBalanceAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employment_id: UUID
    leave_type_id: UUID
    period_year: int
    unit: str
    current_balance: Decimal
    version: int
    status: str
    created_at: datetime
    updated_at: datetime


class LeaveBalanceAccountPage(BaseModel):
    items: list[LeaveBalanceAccountResponse]
    total: int
    limit: int
    offset: int


class LeaveBalanceTransactionCreate(BaseModel):
    employment_id: UUID
    leave_type_id: UUID
    period_year: int = Field(ge=2000, le=2200)
    transaction_type: Literal["grant", "adjustment", "carryover", "accrual"]
    amount: Decimal = Field(max_digits=12, decimal_places=2)
    effective_date: date
    reason: str = Field(min_length=1, max_length=5000)
    idempotency_key: UUID

    @model_validator(mode="after")
    def validate_transaction(self) -> "LeaveBalanceTransactionCreate":
        if self.amount == 0:
            raise ValueError("amount must not be zero")
        if self.transaction_type != "adjustment" and self.amount < 0:
            raise ValueError("only adjustment transactions may use a negative amount")
        if self.effective_date.year != self.period_year:
            raise ValueError("effective_date must be within period_year")
        return self


class LeaveBalanceTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    transaction_type: str
    amount: Decimal
    effective_date: date
    balance_before: Decimal
    balance_after: Decimal
    account_version: int
    source_type: str
    source_id: UUID | None
    idempotency_key: UUID
    reason: str
    actor_id: UUID
    created_at: datetime


class LeaveBalanceTransactionPage(BaseModel):
    items: list[LeaveBalanceTransactionResponse]
    total: int
    limit: int
    offset: int


class AttendanceDailyCalculate(BaseModel):
    employment_id: UUID
    work_date: date
    reason: str = Field(default="manual calculation", min_length=1, max_length=500)


class AttendanceDailyResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employment_id: UUID
    work_date: date
    status: str
    scheduled_minutes: int
    worked_minutes: int
    late_minutes: int
    early_leave_minutes: int
    exception_codes: list[str]
    evidence: dict[str, Any]
    version: int
    is_current: bool


class AttendanceDailyResultPage(BaseModel):
    items: list[AttendanceDailyResultResponse]
    total: int
    limit: int
    offset: int


class AttendanceMonthlyCalculate(BaseModel):
    employment_id: UUID
    period_month: date
    reason: str = Field(default="manual aggregation", min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_month(self) -> "AttendanceMonthlyCalculate":
        if self.period_month.day != 1:
            raise ValueError("period_month must be the first day of a month")
        return self


class AttendanceMonthlyResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employment_id: UUID
    period_month: date
    scheduled_days: Decimal
    worked_days: Decimal
    leave_days: Decimal
    absent_days: Decimal
    late_minutes: int
    early_leave_minutes: int
    version: int
    is_current: bool
    status: str


class AttendanceMonthlyResultPage(BaseModel):
    items: list[AttendanceMonthlyResultResponse]
    total: int
    limit: int
    offset: int


class AttendancePeriodFreezeCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    freeze_type: Literal["monthly", "special"]
    date_from: date
    date_to: date
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_period(self) -> "AttendancePeriodFreezeCreate":
        if self.date_to < self.date_from:
            raise ValueError("date_to不能早于date_from")
        if self.freeze_type == "monthly":
            next_month = date(
                self.date_from.year + (self.date_from.month == 12),
                1 if self.date_from.month == 12 else self.date_from.month + 1,
                1,
            )
            if self.date_from.day != 1 or self.date_to != next_month - timedelta(days=1):
                raise ValueError("月结冻结必须覆盖一个完整自然月")
        return self


class AttendancePeriodFreezeRelease(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    reason: str = Field(min_length=1, max_length=500)


class AttendancePeriodFreezeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    freeze_type: str
    date_from: date
    date_to: date
    status: str
    reason: str
    frozen_by: UUID
    frozen_at: datetime
    released_by: UUID | None
    released_at: datetime | None
    release_reason: str | None
    created_at: datetime
    updated_at: datetime


class AttendancePeriodFreezePage(BaseModel):
    items: list[AttendancePeriodFreezeResponse]
    total: int
    limit: int
    offset: int
