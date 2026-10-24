# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""排班管理契约：排班类型、轮班周期、弹性窗口、草稿生成、发布批次、换班记录。

Requirement: D-107 —— 轮班周期、弹性窗口、同日多班次只建规则容器与占位约束，
取值语义待企业输入（`docs/input-packs/07-attendance-rule-input.md` §4.2）。

Requirement: D-097 —— 批量排班单次最多 1000 条明细，超限整批拒绝。
"""

from datetime import date, datetime, time
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


SCHEDULE_BATCH_MAX_LINES = 1000


def _validate_month_period(period_code: str) -> None:
    if len(period_code) != 7 or period_code[4] != "-" or not period_code[:4].isdigit():
        raise ValueError("period 必须使用 YYYY-MM 格式")


class ScheduleTypeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    requires_shift_cycle: bool = False
    requires_flexible_window: bool = False
    allows_multiple_shifts_per_day: bool = False
    requires_publish: bool = True
    rules: dict[str, Any] = Field(default_factory=dict)


class ScheduleTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    requires_shift_cycle: bool
    requires_flexible_window: bool
    allows_multiple_shifts_per_day: bool
    requires_publish: bool
    status: str
    rules: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ScheduleTypePage(BaseModel):
    items: list[ScheduleTypeResponse]
    total: int
    limit: int
    offset: int


class ShiftCycleCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    schedule_type_id: UUID
    cycle_start_date: date
    cycle_days: int
    shift_sequence: list[UUID] = Field(default_factory=list)
    rules: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_cycle(self) -> "ShiftCycleCreate":
        if self.cycle_days <= 0:
            raise ValueError("cycle_days 必须大于 0")
        if self.shift_sequence and len(self.shift_sequence) != self.cycle_days:
            raise ValueError("shift_sequence 的长度必须与 cycle_days 一致")
        return self


class ShiftCycleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    schedule_type_id: UUID
    cycle_start_date: date
    cycle_days: int
    shift_sequence: list[Any]
    status: str
    rules: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ShiftCyclePage(BaseModel):
    items: list[ShiftCycleResponse]
    total: int
    limit: int
    offset: int


class FlexibleWindowCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    schedule_type_id: UUID
    arrival_window_start: time | None = None
    arrival_window_end: time | None = None
    departure_window_start: time | None = None
    departure_window_end: time | None = None
    standard_daily_minutes: int | None = None
    rules: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_window(self) -> "FlexibleWindowCreate":
        if (
            self.arrival_window_start is not None
            and self.arrival_window_end is not None
            and self.arrival_window_end < self.arrival_window_start
        ):
            raise ValueError("上班浮动窗口的结束时间不能早于开始时间")
        if (
            self.departure_window_start is not None
            and self.departure_window_end is not None
            and self.departure_window_end < self.departure_window_start
        ):
            raise ValueError("下班浮动窗口的结束时间不能早于开始时间")
        if self.standard_daily_minutes is not None and self.standard_daily_minutes <= 0:
            raise ValueError("standard_daily_minutes 必须大于 0")
        return self


class FlexibleWindowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    schedule_type_id: UUID
    arrival_window_start: time | None
    arrival_window_end: time | None
    departure_window_start: time | None
    departure_window_end: time | None
    standard_daily_minutes: int | None
    status: str
    rules: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class FlexibleWindowPage(BaseModel):
    items: list[FlexibleWindowResponse]
    total: int
    limit: int
    offset: int


class ScheduleDraftLine(BaseModel):
    employment_id: UUID
    work_date: date
    shift_id: UUID
    sequence_no: int = 1
    source: str = Field(default="batch", min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_line(self) -> "ScheduleDraftLine":
        if self.sequence_no < 1:
            raise ValueError("sequence_no 必须大于等于 1")
        return self


class ScheduleDraftCreate(BaseModel):
    period_code: str = Field(min_length=1, max_length=20)
    schedule_type_id: UUID | None = None
    source: str = Field(default="batch", min_length=1, max_length=50)
    lines: list[ScheduleDraftLine]

    @model_validator(mode="after")
    def validate_draft(self) -> "ScheduleDraftCreate":
        _validate_month_period(self.period_code)
        if not self.lines:
            raise ValueError("批量排班至少需要一条明细")
        return self


class ScheduleDraftFailure(BaseModel):
    line_index: int
    employment_id: UUID
    work_date: date
    code: str
    message: str


class ScheduleDraftResult(BaseModel):
    period_code: str
    created: int
    failed: list[ScheduleDraftFailure] = Field(default_factory=list)


class SchedulePublishBatchCreate(BaseModel):
    period_code: str = Field(min_length=1, max_length=20)
    schedule_type_id: UUID | None = None

    @model_validator(mode="after")
    def validate_batch(self) -> "SchedulePublishBatchCreate":
        _validate_month_period(self.period_code)
        return self


class SchedulePublishBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_number: str
    period_code: str
    period_start: date
    period_end: date
    schedule_type_id: UUID | None
    status: str
    published_at: datetime | None
    published_by: UUID | None
    created_by: UUID
    published_count: int
    created_at: datetime
    updated_at: datetime


class SchedulePublishBatchPage(BaseModel):
    items: list[SchedulePublishBatchResponse]
    total: int
    limit: int
    offset: int


class ScheduleSwapCreate(BaseModel):
    employment_id_a: UUID
    employment_id_b: UUID
    work_date: date
    original_shift_id: UUID | None = None
    new_shift_id: UUID | None = None
    remark: str | None = Field(default=None, max_length=500)
    effective_at: datetime | None = None

    @model_validator(mode="after")
    def validate_swap(self) -> "ScheduleSwapCreate":
        if self.employment_id_a == self.employment_id_b:
            raise ValueError("换班双方必须是不同的劳动关系")
        return self


class ScheduleSwapUpdate(BaseModel):
    status: Literal["approved", "rejected", "cancelled"]
    remark: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_swap(self) -> "ScheduleSwapUpdate":
        if not self.model_dump(exclude_unset=True):
            raise ValueError("至少需要修改一个换班字段")
        return self


class ScheduleSwapResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_number: str
    employment_id_a: UUID
    employment_id_b: UUID
    work_date: date
    original_shift_id: UUID | None
    new_shift_id: UUID | None
    status: str
    requested_by: UUID
    requested_at: datetime
    decided_at: datetime | None
    decided_by: UUID | None
    effective_at: datetime | None
    remark: str | None
    created_at: datetime
    updated_at: datetime


class ScheduleSwapPage(BaseModel):
    items: list[ScheduleSwapResponse]
    total: int
    limit: int
    offset: int
