# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""Request and response schemas for the performance OKR endpoints."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# Requirement: HR-PERF-015 — 权重、目标值、实际值与得分统一保留两位/四位小数。
_WEIGHT_MAX_DIGITS = 10
_WEIGHT_DECIMAL_PLACES = 2
_VALUE_MAX_DIGITS = 20
_VALUE_DECIMAL_PLACES = 4
_SCORE_MAX_DIGITS = 10
_SCORE_DECIMAL_PLACES = 2


def _check_decimal_digits(
    value: Decimal | None,
    *,
    max_digits: int,
    decimal_places: int,
    field_name: str,
) -> Decimal | None:
    """Reject decimals that do not fit the persisted numeric precision."""
    if value is None:
        return None
    _, digits, exponent = value.as_tuple()
    if len(digits) > max_digits:
        raise ValueError(f"{field_name}数值位数超出允许范围")
    if -exponent > decimal_places:
        raise ValueError(f"{field_name}最多允许{decimal_places}位小数")
    return value


class PerformanceRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class PerformanceCycleCreate(PerformanceRequest):
    code: str = Field(
        min_length=1,
        max_length=50,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,49}$",
    )
    name: str = Field(min_length=1, max_length=200)
    cycle_type: str = Field(min_length=1, max_length=30)
    start_date: date
    end_date: date


class PerformanceCycleUpdate(PerformanceRequest):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    cycle_type: str | None = Field(default=None, min_length=1, max_length=30)
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = Field(default=None, min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_payload(self) -> "PerformanceCycleUpdate":
        # Requirement: HR-PERF-002 — 周期更新必须至少提交一个字段，且不可置空。
        if not self.model_fields_set:
            raise ValueError("至少需要提交一个待修改字段")
        for field in ("name", "cycle_type", "start_date", "end_date", "status"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field}不能为空")
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("end_date不能早于start_date")
        return self


class PerformanceObjectiveCreate(PerformanceRequest):
    person_id: UUID
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    weight: Decimal = Field(
        max_digits=_WEIGHT_MAX_DIGITS,
        decimal_places=_WEIGHT_DECIMAL_PLACES,
    )


class PerformanceObjectiveUpdate(PerformanceRequest):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    weight: Decimal | None = None
    status: str | None = Field(default=None, min_length=1, max_length=30)

    @field_validator("weight")
    @classmethod
    def validate_weight(cls, value: Decimal | None) -> Decimal | None:
        return _check_decimal_digits(
            value,
            max_digits=_WEIGHT_MAX_DIGITS,
            decimal_places=_WEIGHT_DECIMAL_PLACES,
            field_name="weight",
        )

    @model_validator(mode="after")
    def validate_payload(self) -> "PerformanceObjectiveUpdate":
        # Requirement: HR-PERF-008 — 目标更新必须至少提交一个字段，权重与状态不可置空。
        if not self.model_fields_set:
            raise ValueError("至少需要提交一个待修改字段")
        for field in ("title", "weight", "status"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field}不能为空")
        return self


class PerformanceKeyResultCreate(PerformanceRequest):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    target_value: Decimal | None = None
    unit: str | None = Field(default=None, max_length=50)
    weight: Decimal = Field(
        max_digits=_WEIGHT_MAX_DIGITS,
        decimal_places=_WEIGHT_DECIMAL_PLACES,
    )

    @field_validator("target_value")
    @classmethod
    def validate_target_value(cls, value: Decimal | None) -> Decimal | None:
        return _check_decimal_digits(
            value,
            max_digits=_VALUE_MAX_DIGITS,
            decimal_places=_VALUE_DECIMAL_PLACES,
            field_name="target_value",
        )


class PerformanceKeyResultUpdate(PerformanceRequest):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    target_value: Decimal | None = None
    actual_value: Decimal | None = None
    unit: str | None = Field(default=None, max_length=50)
    weight: Decimal | None = None
    score: Decimal | None = None
    status: str | None = Field(default=None, min_length=1, max_length=30)

    @field_validator("weight")
    @classmethod
    def validate_weight(cls, value: Decimal | None) -> Decimal | None:
        return _check_decimal_digits(
            value,
            max_digits=_WEIGHT_MAX_DIGITS,
            decimal_places=_WEIGHT_DECIMAL_PLACES,
            field_name="weight",
        )

    @field_validator("target_value", "actual_value")
    @classmethod
    def validate_measure(cls, value: Decimal | None) -> Decimal | None:
        return _check_decimal_digits(
            value,
            max_digits=_VALUE_MAX_DIGITS,
            decimal_places=_VALUE_DECIMAL_PLACES,
            field_name="数值",
        )

    @field_validator("score")
    @classmethod
    def validate_score(cls, value: Decimal | None) -> Decimal | None:
        # Requirement: HR-PERF-007 — 得分区间校验放在服务层，这里只保证数值精度可落库。
        return _check_decimal_digits(
            value,
            max_digits=_SCORE_MAX_DIGITS,
            decimal_places=_SCORE_DECIMAL_PLACES,
            field_name="score",
        )

    @model_validator(mode="after")
    def validate_payload(self) -> "PerformanceKeyResultUpdate":
        # Requirement: HR-PERF-007 — 关键结果更新必须至少提交一个字段，权重与状态不可置空。
        if not self.model_fields_set:
            raise ValueError("至少需要提交一个待修改字段")
        for field in ("title", "weight", "status"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field}不能为空")
        return self


class PerformanceKeyResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    objective_id: UUID
    title: str
    description: str | None
    target_value: Decimal | None
    actual_value: Decimal | None
    unit: str | None
    weight: Decimal
    score: Decimal | None
    status: str
    sequence_no: int
    created_at: datetime
    updated_at: datetime


class PerformanceObjectiveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cycle_id: UUID
    person_id: UUID
    title: str
    description: str | None
    weight: Decimal
    status: str
    sequence_no: int
    key_results: list[PerformanceKeyResultResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class PerformanceObjectiveGroupResponse(BaseModel):
    person_id: UUID
    objective_count: int
    objective_total_weight: Decimal
    key_result_count: int
    key_result_total_weight: Decimal
    objectives: list[PerformanceObjectiveResponse]


class PerformanceObjectiveListResponse(BaseModel):
    items: list[PerformanceObjectiveResponse]
    total: int
    grouped_by_person: bool
    person_groups: list[PerformanceObjectiveGroupResponse]


class PerformanceCycleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    cycle_type: str
    start_date: date
    end_date: date
    status: str
    created_at: datetime
    updated_at: datetime


class PerformanceCycleDetailResponse(PerformanceCycleResponse):
    objective_count: int
    person_count: int
    key_result_count: int
    objective_total_weight: Decimal


class PerformanceCyclePage(BaseModel):
    items: list[PerformanceCycleResponse]
    total: int
    page: int
    page_size: int


class PerformanceObjectiveScoreResponse(BaseModel):
    objective_id: UUID
    title: str
    weight: Decimal
    key_result_count: int
    key_result_total_weight: Decimal
    scored_key_result_count: int
    objective_score: Decimal | None


class PerformanceScorecardEntry(BaseModel):
    person_id: UUID
    objective_count: int
    objective_total_weight: Decimal
    key_result_count: int
    key_result_total_weight: Decimal
    scored_key_result_count: int
    weighted_score: Decimal | None
    objectives: list[PerformanceObjectiveScoreResponse]


class PerformanceScorecardResponse(BaseModel):
    cycle_id: UUID
    cycle_code: str
    cycle_status: str
    entries: list[PerformanceScorecardEntry]
    total: int
