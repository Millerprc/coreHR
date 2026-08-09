from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CandidateCreate(BaseModel):
    candidate_number: str | None = Field(default=None, max_length=50)
    display_name: str = Field(min_length=1, max_length=200)
    contact_payload: dict[str, Any] = Field(default_factory=dict)


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    candidate_number: str
    display_name: str
    contact_payload: dict[str, Any]
    status: str
    linked_person_id: UUID | None
    created_at: datetime
    updated_at: datetime


class RecruitmentRequestCreate(BaseModel):
    request_number: str | None = Field(default=None, max_length=50)
    organization_id: UUID
    job_id: UUID
    requested_count: int = Field(gt=0, le=10000)
    target_month: date | None = None
    reason: str = Field(min_length=1, max_length=5000)


class RecruitmentRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_number: str
    organization_id: UUID
    job_id: UUID
    requested_count: int
    target_month: date | None
    status: str
    reason: str
    workflow_instance_id: UUID | None


class RecruitmentRequestUpdate(BaseModel):
    requested_count: int | None = Field(default=None, gt=0, le=10000)
    target_month: date | None = None
    reason: str | None = Field(default=None, min_length=1, max_length=5000)
    status: Literal["draft", "submitted", "closed", "cancelled"] | None = None
    change_reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_change(self) -> "RecruitmentRequestUpdate":
        changed = self.model_dump(exclude={"change_reason"}, exclude_unset=True)
        if not changed:
            raise ValueError("至少提供一个招聘需求变更字段")
        return self


class RecruitmentRequestPage(BaseModel):
    items: list[RecruitmentRequestResponse]
    total: int
    limit: int
    offset: int


class JobApplicationCreate(BaseModel):
    candidate_id: UUID
    recruitment_request_id: UUID
    current_stage: str | None = Field(default=None, max_length=50)


class JobApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    candidate_id: UUID
    recruitment_request_id: UUID
    status: str
    current_stage: str | None
    offer_payload: dict[str, Any]


class ContractCreate(BaseModel):
    person_id: UUID
    employment_id: UUID | None = None
    contract_type_code: str = Field(min_length=1, max_length=50)
    contract_number: str = Field(min_length=1, max_length=100)
    legal_entity_id: UUID | None = None
    effective_from: date
    effective_to: date | None = None
    metadata_payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_dates(self) -> "ContractCreate":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to不能早于effective_from")
        return self


class ContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    person_id: UUID
    employment_id: UUID | None
    contract_type_code: str
    contract_number: str
    legal_entity_id: UUID | None
    effective_from: date
    effective_to: date | None
    status: str
    metadata_payload: dict[str, Any]


class HrEventCreate(BaseModel):
    event_type: str = Field(min_length=1, max_length=50)
    object_type: str = Field(min_length=1, max_length=50)
    object_id: UUID
    effective_date: date
    execution_mode: Literal["direct", "approval"] = "approval"
    reason: str = Field(min_length=1, max_length=500)
    before_payload: dict[str, Any] = Field(default_factory=dict)
    planned_payload: dict[str, Any] = Field(default_factory=dict)
    workflow_instance_id: UUID | None = None


class HrEventRollbackCreate(BaseModel):
    execution_mode: Literal["direct", "approval"] = "approval"
    effective_date: date
    reason: str = Field(min_length=1, max_length=500)


class HrEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_number: str
    event_type: str
    object_type: str
    object_id: UUID
    effective_date: date
    status: str
    source: str
    reason: str
    before_payload: dict[str, Any]
    planned_payload: dict[str, Any]
    actual_payload: dict[str, Any]
    workflow_instance_id: UUID | None
    related_event_id: UUID | None
    attempts: int
    last_error: str | None
    executed_at: datetime | None
    version: int


class WorkflowPublishResponse(BaseModel):
    definition_id: UUID
    version: int
    status: str


class WorkflowInstanceCreate(BaseModel):
    workflow_definition_id: UUID
    business_object_type: str = Field(min_length=1, max_length=50)
    business_object_id: UUID
    context: dict[str, Any] = Field(default_factory=dict)


class WorkflowInstanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    instance_number: str
    workflow_version_id: UUID
    business_object_type: str
    business_object_id: UUID
    status: str
    current_node_code: str | None
    started_by: UUID | None
    started_at: datetime
    completed_at: datetime | None
    context: dict[str, Any]
