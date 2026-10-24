# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""发假明细契约：额度规则、发放批次、发放明细行。

Requirement: D-107 —— 计提频率、工龄折算、封顶、清零、结转上限、有效期、离职处理
只提供可配置字段容器，取值语义待企业输入（`docs/input-packs/07-attendance-rule-input.md`
§4.5）。本模块**不提供任何默认值**：未配置的规则字段保持 `None`，由服务层拒绝据此计提。

Requirement: D-097 —— 单个发放批次最多 1000 条明细，超限整批拒绝。
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


GRANT_BATCH_MAX_ITEMS = 1000


def _validate_period_code(period_code: str, period_type: str) -> None:
    if period_type == "month":
        if len(period_code) != 7 or period_code[4] != "-" or not period_code[:4].isdigit():
            raise ValueError("month period must use the YYYY-MM format")
    elif period_type == "year":
        if len(period_code) != 4 or not period_code.isdigit():
            raise ValueError("year period must use the YYYY format")
    else:
        raise ValueError("period_type must be month or year")


class LeaveGrantRuleCreate(BaseModel):
    """发假额度规则（D-107 规则容器）。

    除 `code` / `name` / `leave_type_id` / `effective_from` 外全部可留空：
    留空表示「企业规则未输入」，自动计提会跳过并记录原因。
    """

    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    leave_type_id: UUID
    effective_from: date
    effective_to: date | None = None
    entitlement_days: Decimal | None = None
    seniority_min_years: int | None = None
    seniority_max_years: int | None = None
    proration_method: str | None = Field(default=None, max_length=30)
    accrual_frequency: str | None = Field(default=None, max_length=30)
    cap_days: Decimal | None = None
    carryover_cap_days: Decimal | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    reset_policy: str | None = Field(default=None, max_length=30)
    termination_policy: str | None = Field(default=None, max_length=30)
    rules: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_rule(self) -> "LeaveGrantRuleCreate":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to 不能早于 effective_from")
        if self.entitlement_days is not None and self.entitlement_days <= 0:
            raise ValueError("entitlement_days 必须大于 0")
        if self.cap_days is not None and self.cap_days < 0:
            raise ValueError("cap_days 不能为负数")
        if self.carryover_cap_days is not None and self.carryover_cap_days < 0:
            raise ValueError("carryover_cap_days 不能为负数")
        if (
            self.seniority_min_years is not None
            and self.seniority_max_years is not None
            and self.seniority_max_years < self.seniority_min_years
        ):
            raise ValueError("seniority_max_years 不能小于 seniority_min_years")
        if (
            self.seniority_min_years is not None
            and self.seniority_min_years < 0
        ) or (
            self.seniority_max_years is not None
            and self.seniority_max_years < 0
        ):
            raise ValueError("工龄年数不能为负数")
        if self.valid_from is not None and self.valid_to is not None:
            if self.valid_to < self.valid_from:
                raise ValueError("valid_to 不能早于 valid_from")
        return self


class LeaveGrantRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    effective_to: date | None = None
    entitlement_days: Decimal | None = None
    seniority_min_years: int | None = None
    seniority_max_years: int | None = None
    proration_method: str | None = Field(default=None, max_length=30)
    accrual_frequency: str | None = Field(default=None, max_length=30)
    cap_days: Decimal | None = None
    carryover_cap_days: Decimal | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    reset_policy: str | None = Field(default=None, max_length=30)
    termination_policy: str | None = Field(default=None, max_length=30)
    rules: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_rule(self) -> "LeaveGrantRuleUpdate":
        if not self.model_dump(exclude_unset=True):
            raise ValueError("至少需要修改一个发假额度规则字段")
        if self.entitlement_days is not None and self.entitlement_days <= 0:
            raise ValueError("entitlement_days 必须大于 0")
        if self.cap_days is not None and self.cap_days < 0:
            raise ValueError("cap_days 不能为负数")
        if self.carryover_cap_days is not None and self.carryover_cap_days < 0:
            raise ValueError("carryover_cap_days 不能为负数")
        if (
            self.seniority_min_years is not None
            and self.seniority_max_years is not None
            and self.seniority_max_years < self.seniority_min_years
        ):
            raise ValueError("seniority_max_years 不能小于 seniority_min_years")
        if self.valid_from is not None and self.valid_to is not None:
            if self.valid_to < self.valid_from:
                raise ValueError("valid_to 不能早于 valid_from")
        return self


class LeaveGrantRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    version: int
    leave_type_id: UUID
    status: str
    entitlement_days: Decimal | None
    seniority_min_years: int | None
    seniority_max_years: int | None
    proration_method: str | None
    accrual_frequency: str | None
    cap_days: Decimal | None
    carryover_cap_days: Decimal | None
    valid_from: date | None
    valid_to: date | None
    reset_policy: str | None
    termination_policy: str | None
    effective_from: date
    effective_to: date | None
    rules: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class LeaveGrantRulePage(BaseModel):
    items: list[LeaveGrantRuleResponse]
    total: int
    limit: int
    offset: int


class LeaveGrantItemCreate(BaseModel):
    employment_id: UUID
    leave_type_id: UUID
    grant_days: Decimal
    valid_from: date | None = None
    valid_to: date | None = None
    rule_id: UUID | None = None
    idempotency_key: UUID | None = None

    @model_validator(mode="after")
    def validate_item(self) -> "LeaveGrantItemCreate":
        if self.grant_days <= 0:
            raise ValueError("grant_days 必须大于 0")
        if self.valid_from is not None and self.valid_to is not None:
            if self.valid_to < self.valid_from:
                raise ValueError("valid_to 不能早于 valid_from")
        return self


class LeaveGrantBatchCreate(BaseModel):
    period_code: str = Field(min_length=1, max_length=20)
    period_type: Literal["month", "year"]
    grant_date: date
    source: Literal["manual", "rule_accrual"] = "manual"
    items: list[LeaveGrantItemCreate]

    @model_validator(mode="after")
    def validate_batch(self) -> "LeaveGrantBatchCreate":
        _validate_period_code(self.period_code, self.period_type)
        if not self.items:
            raise ValueError("发放批次至少需要一条明细")
        if len(self.items) > GRANT_BATCH_MAX_ITEMS:
            raise ValueError(f"单个发放批次最多 {GRANT_BATCH_MAX_ITEMS} 条明细")
        pairs = [(item.employment_id, item.leave_type_id) for item in self.items]
        if len(set(pairs)) != len(pairs):
            raise ValueError("同一批次内不允许重复的员工与假期类型组合")
        return self


class LeaveGrantItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_id: UUID
    employment_id: UUID
    leave_type_id: UUID
    account_id: UUID | None
    transaction_id: UUID | None
    rule_id: UUID | None
    grant_days: Decimal
    valid_from: date | None
    valid_to: date | None
    source: str
    status: str
    idempotency_key: UUID
    created_at: datetime
    updated_at: datetime


class LeaveGrantBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_number: str
    period_code: str
    period_type: str
    grant_date: date
    status: str
    source: str
    created_by: UUID
    issued_at: datetime | None
    issued_by: UUID | None
    voided_at: datetime | None
    voided_by: UUID | None
    void_reason: str | None
    created_at: datetime
    updated_at: datetime


class LeaveGrantBatchDetailResponse(LeaveGrantBatchResponse):
    items: list[LeaveGrantItemResponse] = Field(default_factory=list)


class LeaveGrantBatchPage(BaseModel):
    items: list[LeaveGrantBatchResponse]
    total: int
    limit: int
    offset: int


class LeaveGrantBatchVoid(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
