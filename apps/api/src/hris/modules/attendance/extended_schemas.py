from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
