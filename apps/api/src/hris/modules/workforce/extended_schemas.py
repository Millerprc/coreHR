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


class JobCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    level_code: str | None = Field(default=None, max_length=50)
    grade_code: str | None = Field(default=None, max_length=50)
    class_code: str | None = Field(default=None, max_length=50)
    sequence_code: str | None = Field(default=None, max_length=50)
    effective_from: date
    effective_to: date | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    level_code: str | None
    grade_code: str | None
    class_code: str | None
    sequence_code: str | None
    status: str
    effective_from: date
    effective_to: date | None
    attributes: dict[str, Any]


class PersonCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    former_name: str | None = Field(default=None, max_length=200)
    gender_code: str | None = Field(default=None, max_length=30)
    birth_date: date | None = None
    nationality_code: str | None = Field(default=None, min_length=2, max_length=3)
    country_code: str | None = Field(default=None, min_length=2, max_length=3)
    employee_number: str | None = Field(default=None, pattern=r"^[0-9]{6}$")
    reserve_employee_number: bool = True
    change_reason: str = Field(min_length=1, max_length=500)


class PersonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_number: str | None
    display_name: str
    former_name: str | None
    gender_code: str | None
    birth_date: date | None
    nationality_code: str | None
    country_code: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class PersonUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    former_name: str | None = Field(default=None, max_length=200)
    gender_code: str | None = Field(default=None, max_length=30)
    birth_date: date | None = None
    nationality_code: str | None = Field(default=None, min_length=2, max_length=3)
    country_code: str | None = Field(default=None, min_length=2, max_length=3)
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
    assignments: list[EmploymentAssignmentResponse]
    agreements: list[AgreementRelationshipResponse]


class HeadcountPlanCreate(BaseModel):
    organization_id: UUID
    job_id: UUID
    period_month: date
    planned_count: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    change_reason: str = Field(min_length=1, max_length=500)

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


class PageResponse(BaseModel):
    items: list[Any]
    total: int
    limit: int
    offset: int
