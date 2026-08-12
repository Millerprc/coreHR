from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LegalEntityCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    registered_name: str | None = Field(default=None, max_length=300)
    country_code: str = Field(min_length=2, max_length=3)
    registration_number: str | None = Field(default=None, max_length=100)
    effective_from: date
    effective_to: date | None = None


class LegalEntityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    registered_name: str | None
    country_code: str
    registration_number: str | None
    status: str
    effective_from: date
    effective_to: date | None


JobDimensionType = Literal["LEVEL", "GRADE", "CLASS", "SEQUENCE"]
JobStatus = Literal["active", "inactive"]


class JobDimensionCreate(BaseModel):
    dimension_type: JobDimensionType
    code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_.-]{0,49}$")
    name: str = Field(min_length=1, max_length=200)
    parent_dimension_type: JobDimensionType | None = None
    parent_dimension_code: str | None = Field(
        default=None,
        pattern=r"^[A-Z0-9][A-Z0-9_.-]{0,49}$",
    )
    sort_order: int = Field(default=0, ge=0)
    status: JobStatus = "active"
    effective_from: date
    effective_to: date | None = None
    notes: str | None = Field(default=None, max_length=1000)
    change_reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_dimension(self) -> "JobDimensionCreate":
        if (self.parent_dimension_type is None) != (self.parent_dimension_code is None):
            raise ValueError("父维度类型和代码必须同时填写")
        if (
            self.parent_dimension_type == self.dimension_type
            and self.parent_dimension_code == self.code
        ):
            raise ValueError("职务维度不能以自身为父级")
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to不能早于effective_from")
        return self


class JobDimensionVersionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    parent_dimension_type: JobDimensionType | None = None
    parent_dimension_code: str | None = Field(
        default=None,
        pattern=r"^[A-Z0-9][A-Z0-9_.-]{0,49}$",
    )
    sort_order: int = Field(default=0, ge=0)
    status: JobStatus = "active"
    effective_from: date
    effective_to: date | None = None
    notes: str | None = Field(default=None, max_length=1000)
    change_reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_dimension_version(self) -> "JobDimensionVersionCreate":
        if (self.parent_dimension_type is None) != (self.parent_dimension_code is None):
            raise ValueError("父维度类型和代码必须同时填写")
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to不能早于effective_from")
        return self


class JobDimensionResponse(BaseModel):
    id: UUID
    dimension_type: JobDimensionType
    code: str
    name: str
    parent_dimension_id: UUID | None
    parent_dimension_type: JobDimensionType | None
    parent_dimension_code: str | None
    sort_order: int
    status: str
    effective_from: date
    effective_to: date | None
    version: int
    notes: str | None


class JobCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_.-]{0,49}$")
    name: str = Field(min_length=1, max_length=200)
    level_code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_.-]{0,49}$")
    grade_code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_.-]{0,49}$")
    class_code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_.-]{0,49}$")
    sequence_code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_.-]{0,49}$")
    status: JobStatus = "active"
    effective_from: date
    effective_to: date | None = None
    source_job_id: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=1000)
    attributes: dict[str, Any] = Field(default_factory=dict)
    change_reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_effective_period(self) -> "JobCreate":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to不能早于effective_from")
        return self


class JobVersionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    level_code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_.-]{0,49}$")
    grade_code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_.-]{0,49}$")
    class_code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_.-]{0,49}$")
    sequence_code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_.-]{0,49}$")
    status: JobStatus = "active"
    effective_from: date
    effective_to: date | None = None
    source_job_id: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=1000)
    attributes: dict[str, Any] = Field(default_factory=dict)
    change_reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_effective_period(self) -> "JobVersionCreate":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to不能早于effective_from")
        return self


class JobResponse(BaseModel):
    id: UUID
    code: str
    name: str
    level_code: str
    grade_code: str
    class_code: str
    sequence_code: str
    status: str
    effective_from: date
    effective_to: date | None
    version: int
    source_job_id: str | None
    notes: str | None
    attributes: dict[str, Any]


class PersonCreate(BaseModel):
    legal_name: str = Field(min_length=1, max_length=200)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    former_name: str | None = Field(default=None, max_length=200)
    gender_code: str | None = Field(default=None, max_length=30)
    birth_date: date | None = None
    ethnicity_code: str | None = Field(default=None, max_length=50)
    nationality_code: str | None = Field(default=None, min_length=2, max_length=3)
    country_code: str | None = Field(default=None, min_length=2, max_length=3)
    marital_status_code: str | None = Field(default=None, max_length=50)
    political_status_code: str | None = Field(default=None, max_length=50)
    employee_number: str | None = Field(default=None, pattern=r"^[0-9]{6}$")
    reserve_employee_number: bool = True
    change_reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def default_display_name(self) -> "PersonCreate":
        if self.display_name is None:
            self.display_name = self.legal_name
        return self


class PersonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_number: str | None
    legal_name: str
    display_name: str
    former_name: str | None
    gender_code: str | None
    birth_date: date | None
    ethnicity_code: str | None
    nationality_code: str | None
    country_code: str | None
    marital_status_code: str | None
    political_status_code: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class PersonUpdate(BaseModel):
    legal_name: str | None = Field(default=None, min_length=1, max_length=200)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    former_name: str | None = Field(default=None, max_length=200)
    gender_code: str | None = Field(default=None, max_length=30)
    birth_date: date | None = None
    ethnicity_code: str | None = Field(default=None, max_length=50)
    nationality_code: str | None = Field(default=None, min_length=2, max_length=3)
    country_code: str | None = Field(default=None, min_length=2, max_length=3)
    marital_status_code: str | None = Field(default=None, max_length=50)
    political_status_code: str | None = Field(default=None, max_length=50)
    change_reason: str = Field(min_length=1, max_length=500)


class EmployeeNumberResponse(BaseModel):
    person_id: UUID
    employee_number: str


class EmploymentCreate(BaseModel):
    person_id: UUID
    employee_type_code: str = Field(min_length=1, max_length=50)
    planned_start_date: date
    actual_start_date: date | None = None
    probation_end_date: date | None = None
    end_date: date | None = None
    contract_legal_entity_id: UUID
    payroll_legal_entity_id: UUID | None = None
    social_insurance_legal_entity_id: UUID | None = None
    tax_legal_entity_id: UUID | None = None
    change_reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_dates(self) -> "EmploymentCreate":
        start = self.actual_start_date or self.planned_start_date
        if self.end_date is not None and self.end_date < start:
            raise ValueError("end_date不能早于开始日期")
        return self


class EmploymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    person_id: UUID
    employee_type_code: str
    status: str
    planned_start_date: date
    actual_start_date: date | None
    probation_end_date: date | None
    end_date: date | None
    contract_legal_entity_id: UUID | None
    payroll_legal_entity_id: UUID | None
    social_insurance_legal_entity_id: UUID | None
    tax_legal_entity_id: UUID | None
    version: int


EmploymentLegalEntityKind = Literal["contract", "payroll", "social_insurance", "tax"]


class EmploymentLegalEntityRelationCreate(BaseModel):
    relation_kind: EmploymentLegalEntityKind
    legal_entity_id: UUID
    effective_from: date
    change_reason: str = Field(min_length=1, max_length=500)


class EmploymentLegalEntityRelationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employment_id: UUID
    relation_kind: EmploymentLegalEntityKind
    legal_entity_id: UUID
    effective_from: date
    effective_to: date | None
    source_event_id: UUID | None
    version: int
    change_reason: str


class EmploymentAssignmentCreate(BaseModel):
    employment_id: UUID
    organization_id: UUID
    job_id: UUID | None = None
    relation_type: Literal["primary", "concurrent", "secondment", "project", "virtual"]
    effective_from: date
    effective_to: date | None = None
    change_reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_assignment(self) -> "EmploymentAssignmentCreate":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to不能早于effective_from")
        if self.relation_type == "primary" and self.job_id is None:
            raise ValueError("主组织关系必须指定职务")
        return self


class EmploymentAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employment_id: UUID
    organization_id: UUID
    job_id: UUID | None
    relation_type: str
    effective_from: date
    effective_to: date | None
    version: int


class AgreementRelationshipCreate(BaseModel):
    person_id: UUID
    agreement_type_code: str = Field(min_length=1, max_length=50)
    legal_entity_id: UUID | None = None
    counterparty_name: str | None = Field(default=None, max_length=300)
    effective_from: date
    effective_to: date | None = None
    source: str = Field(default="manual", min_length=1, max_length=50)
    change_reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_agreement(self) -> "AgreementRelationshipCreate":
        if self.legal_entity_id is None and not self.counterparty_name:
            raise ValueError("法人主体和合作方名称至少填写一项")
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to不能早于effective_from")
        return self


class AgreementRelationshipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    person_id: UUID
    agreement_type_code: str
    legal_entity_id: UUID | None
    counterparty_name: str | None
    effective_from: date
    effective_to: date | None
    source: str


class PersonArchiveResponse(BaseModel):
    person: PersonResponse
    employments: list[EmploymentResponse]
    legal_entity_relations: list[EmploymentLegalEntityRelationResponse]
    assignments: list[EmploymentAssignmentResponse]
    agreements: list[AgreementRelationshipResponse]


class HeadcountPlanCreate(BaseModel):
    organization_id: UUID
    job_id: UUID
    period_month: date
    planned_count: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    change_reason: str = Field(min_length=1, max_length=500)
    override_freeze: bool = False

    @model_validator(mode="after")
    def validate_month(self) -> "HeadcountPlanCreate":
        if self.period_month.day != 1:
            raise ValueError("period_month必须使用月份第一天")
        return self


class HeadcountPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    job_id: UUID
    period_month: date
    planned_count: Decimal
    version: int
    is_current: bool
    change_reason: str


class OccupancyRuleCreate(BaseModel):
    employee_type_code: str = Field(min_length=1, max_length=50)
    counts_for_headcount: bool
    effective_from: date
    effective_to: date | None = None
    change_reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_period(self) -> "OccupancyRuleCreate":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to不能早于effective_from")
        return self


class OccupancyRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_type_code: str
    counts_for_headcount: bool
    effective_from: date
    effective_to: date | None
    version: int


class HeadcountFreezeCreate(BaseModel):
    freeze_type: Literal["month_close", "business"]
    period_month: date | None = None
    organization_id: UUID | None = None
    job_id: UUID | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_freeze(self) -> "HeadcountFreezeCreate":
        if self.period_month is not None and self.period_month.day != 1:
            raise ValueError("period_month必须使用月份第一天")
        if self.freeze_type == "month_close" and self.period_month is None:
            raise ValueError("月结冻结必须指定月份")
        if self.starts_at.tzinfo is None or (
            self.ends_at is not None and self.ends_at.tzinfo is None
        ):
            raise ValueError("冻结起止时间必须包含时区")
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("ends_at必须晚于starts_at")
        return self


class HeadcountFreezeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    freeze_type: str
    period_month: date | None
    organization_id: UUID | None
    job_id: UUID | None
    status: str
    starts_at: datetime
    ends_at: datetime | None
    reason: str


class HeadcountFreezeClose(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class HeadcountSnapshotGenerate(BaseModel):
    snapshot_type: Literal["month_start", "month_end"]
    period_month: date
    timezone: str = Field(min_length=1, max_length=100)
    boundary_at: datetime
    rule_version: str = Field(min_length=1, max_length=50)
    parent_batch_id: UUID | None = None
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_snapshot(self) -> "HeadcountSnapshotGenerate":
        if self.period_month.day != 1:
            raise ValueError("period_month必须使用月份第一天")
        if self.boundary_at.tzinfo is None:
            raise ValueError("boundary_at必须包含时区")
        return self


class HeadcountSnapshotBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    snapshot_type: str
    period_month: date
    timezone: str
    boundary_at: datetime
    rule_version: str
    version: int
    parent_batch_id: UUID | None
    status: str
    reason: str | None


class HeadcountResultLine(BaseModel):
    organization_id: UUID
    organization_code: str
    job_id: UUID
    job_code: str
    job_name: str
    period_month: date
    planned_count: Decimal
    plan_version: int
    current_count: int
    variance: Decimal
    month_start_count: int | None
    month_end_count: int | None
    average_count: Decimal | None
    frozen: bool


class HeadcountResultResponse(BaseModel):
    period_month: date
    as_of: date
    items: list[HeadcountResultLine]


class PageResponse(BaseModel):
    items: list[Any]
    total: int
    limit: int
    offset: int
