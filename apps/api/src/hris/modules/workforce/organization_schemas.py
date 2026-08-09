from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hris.core.concurrency import VersionCommand


class OrganizationRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class EffectivePeriod(OrganizationRequest):
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def validate_period(self) -> "EffectivePeriod":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to不能早于effective_from")
        return self


class OrganizationTypeCreate(OrganizationRequest):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{0,49}$")
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = Field(default=0, ge=0)


class OrganizationTypeUpdate(OrganizationRequest):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    change_reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def require_change(self) -> "OrganizationTypeUpdate":
        if not ({"name", "sort_order", "is_active"} & self.model_fields_set):
            raise ValueError("至少提供一个组织类型修改字段")
        return self


class OrganizationTypeView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class OrganizationCreate(EffectivePeriod):
    name: str = Field(min_length=1, max_length=200)
    organization_type_id: UUID
    parent_organization_id: UUID | None = None
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2,3}$")
    command: VersionCommand


class OrganizationVersionCreate(OrganizationRequest):
    name: str = Field(min_length=1, max_length=200)
    organization_type_id: UUID
    parent_organization_id: UUID | None = None
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2,3}$")
    status: Literal["active", "inactive"] = "active"
    effective_date: date
    command: VersionCommand


class OrganizationEventView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    event_type: str
    effective_date: date
    status: str
    payload: dict[str, object]
    expected_version: int
    idempotency_key: UUID
    change_reason: str
    applied_at: datetime | None
    cancelled_at: datetime | None


class OrganizationView(BaseModel):
    id: UUID
    code: str
    name: str
    organization_type_id: UUID
    organization_type_code: str
    organization_type_name: str
    parent_organization_id: UUID | None
    parent_organization_code: str | None
    country_code: str | None
    status: str
    effective_from: date
    effective_to: date | None
    version: int
    planned_events: list[OrganizationEventView] = Field(default_factory=list)


class OrganizationTreeNode(BaseModel):
    id: UUID
    code: str
    name: str
    organization_type_code: str
    status: str
    children: list["OrganizationTreeNode"] = Field(default_factory=list)


class OrganizationLegalEntitySet(EffectivePeriod):
    legal_entity_ids: list[UUID]
    command: VersionCommand


class OrganizationLeaderSet(EffectivePeriod):
    person_ids: list[UUID] = Field(max_length=3)
    command: VersionCommand


class BpMembershipCreate(EffectivePeriod):
    person_id: UUID
    bp_type: Literal["HRBP", "EBP", "TBP", "FBP"]
    organization_ids: list[UUID] = Field(min_length=1)
    command: VersionCommand


class BpServiceScopeSet(EffectivePeriod):
    organization_ids: list[UUID] = Field(min_length=1)
    command: VersionCommand


class OrganizationRelationsView(BaseModel):
    effective_at: date
    legal_entity_ids: list[UUID]
    leader_person_ids: list[UUID]
    bp_membership_ids: list[UUID]


class CostCenterCreate(EffectivePeriod):
    code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{0,49}$")
    name: str = Field(min_length=1, max_length=200)
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2,3}$")


class CostCenterView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    country_code: str | None
    status: str
    effective_from: date
    effective_to: date | None
    version: int


class CostAllocationLine(OrganizationRequest):
    cost_center_id: UUID
    allocation_percent: Decimal = Field(gt=0, le=100, decimal_places=4)


class CostAllocationSet(EffectivePeriod):
    lines: list[CostAllocationLine] = Field(min_length=1)
    command: VersionCommand


class CostAllocationView(BaseModel):
    organization_id: UUID
    effective_at: date
    version: int
    lines: list[CostAllocationLine]


class RevenueTargetMonthInput(OrganizationRequest):
    month: int = Field(ge=1, le=12)
    amount: Decimal = Field(ge=0, decimal_places=4)


class RevenueTargetSet(OrganizationRequest):
    year: int = Field(ge=2000, le=2200)
    currency_code: str = Field(pattern=r"^[A-Z]{3}$")
    annual_amount: Decimal = Field(ge=0, decimal_places=4)
    months: list[RevenueTargetMonthInput] = Field(min_length=12, max_length=12)
    command: VersionCommand


class RevenueTargetView(BaseModel):
    id: UUID
    organization_id: UUID
    year: int
    currency_code: str
    annual_amount: Decimal
    months: list[RevenueTargetMonthInput]
    version: int


class RevenueAggregationView(BaseModel):
    organization_id: UUID
    year: int
    totals_by_currency: dict[str, Decimal]
