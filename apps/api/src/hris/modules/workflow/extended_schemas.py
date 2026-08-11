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


class CandidateUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    contact_payload: dict[str, Any] | None = None
    status: Literal["active", "converted", "inactive"] | None = None
    linked_person_id: UUID | None = None
    change_reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_change(self) -> "CandidateUpdate":
        if not self.model_dump(exclude={"change_reason"}, exclude_unset=True):
            raise ValueError("at least one candidate field must be changed")
        return self


class CandidatePage(BaseModel):
    items: list[CandidateResponse]
    total: int
    limit: int
    offset: int


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


class JobApplicationUpdate(BaseModel):
    status: Literal[
        "active",
        "screening",
        "interview",
        "offer",
        "hired",
        "rejected",
        "withdrawn",
    ] | None = None
    current_stage: str | None = Field(default=None, max_length=50)
    offer_payload: dict[str, Any] | None = None
    change_reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_change(self) -> "JobApplicationUpdate":
        if not self.model_dump(exclude={"change_reason"}, exclude_unset=True):
            raise ValueError("at least one application field must be changed")
        return self


class JobApplicationPage(BaseModel):
    items: list[JobApplicationResponse]
    total: int
    limit: int
    offset: int


class ApplicationHireCreate(BaseModel):
    idempotency_key: UUID
    planned_start_date: date
    employee_type_code: str = Field(
        min_length=1,
        max_length=50,
        pattern=r"^[A-Z][A-Z0-9_]*$",
    )
    contract_legal_entity_id: UUID
    payroll_legal_entity_id: UUID | None = None
    social_insurance_legal_entity_id: UUID | None = None
    tax_legal_entity_id: UUID | None = None
    existing_person_id: UUID | None = None
    gender_code: str | None = Field(default=None, max_length=30)
    birth_date: date | None = None
    nationality_code: str | None = Field(default=None, min_length=2, max_length=3)
    country_code: str | None = Field(default=None, min_length=2, max_length=3)
    probation_end_date: date | None = None
    reason: str = Field(min_length=1, max_length=500)


class ApplicationHireConversionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    application_id: UUID
    candidate_id: UUID
    person_id: UUID
    employment_id: UUID
    assignment_id: UUID
    idempotency_key: UUID
    planned_start_date: date
    employee_type_code: str
    converted_by: UUID
    converted_at: datetime
    created_at: datetime
    updated_at: datetime


class ContractCreate(BaseModel):
    person_id: UUID
    employment_id: UUID | None = None
    agreement_relationship_id: UUID | None = None
    contract_type_code: str = Field(
        min_length=1,
        max_length=50,
        pattern=r"^[A-Z][A-Z0-9_]*$",
    )
    contract_number: str = Field(min_length=1, max_length=100)
    legal_entity_id: UUID | None = None
    signed_on: date | None = None
    effective_from: date
    effective_to: date | None = None
    expiry_notice_days: int = Field(default=30, ge=0, le=3650)
    metadata_payload: dict[str, Any] = Field(default_factory=dict)
    change_reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_dates(self) -> "ContractCreate":
        if self.employment_id is not None and self.agreement_relationship_id is not None:
            raise ValueError("a contract can link to employment or agreement, not both")
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be earlier than effective_from")
        return self


class ContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    person_id: UUID
    employment_id: UUID | None
    agreement_relationship_id: UUID | None
    predecessor_contract_id: UUID | None
    contract_type_code: str
    contract_number: str
    legal_entity_id: UUID | None
    signed_on: date | None
    effective_from: date
    effective_to: date | None
    expiry_notice_days: int
    version: int
    status: str
    metadata_payload: dict[str, Any]


class ContractUpdate(BaseModel):
    signed_on: date | None = None
    legal_entity_id: UUID | None = None
    expiry_notice_days: int | None = Field(default=None, ge=0, le=3650)
    metadata_payload: dict[str, Any] | None = None
    change_reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_change(self) -> "ContractUpdate":
        if not self.model_dump(exclude={"change_reason"}, exclude_unset=True):
            raise ValueError("at least one contract field must be changed")
        return self


class ContractAmendment(BaseModel):
    signed_on: date | None = None
    effective_to: date | None = None
    legal_entity_id: UUID | None = None
    expiry_notice_days: int | None = Field(default=None, ge=0, le=3650)
    metadata_payload: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_change(self) -> "ContractAmendment":
        if not self.model_dump(exclude_unset=True):
            raise ValueError("at least one amendment field must be changed")
        return self


class ContractRenewal(BaseModel):
    contract_number: str = Field(min_length=1, max_length=100)
    effective_to: date | None = None
    signed_on: date | None = None
    legal_entity_id: UUID | None = None
    expiry_notice_days: int = Field(default=30, ge=0, le=3650)
    metadata_payload: dict[str, Any] = Field(default_factory=dict)


class ContractActionCreate(BaseModel):
    idempotency_key: UUID
    action_type: Literal["amendment", "renewal", "termination", "cancellation"]
    effective_date: date
    execution_mode: Literal["direct", "approval"] = "direct"
    reason: str = Field(min_length=1, max_length=500)
    workflow_instance_id: UUID | None = None
    amendment: ContractAmendment | None = None
    renewal: ContractRenewal | None = None

    @model_validator(mode="after")
    def validate_action_payload(self) -> "ContractActionCreate":
        if self.action_type == "amendment" and self.amendment is None:
            raise ValueError("amendment payload is required for amendment action")
        if self.action_type != "amendment" and self.amendment is not None:
            raise ValueError("amendment payload is only valid for amendment action")
        if self.action_type == "renewal" and self.renewal is None:
            raise ValueError("renewal payload is required for renewal action")
        if self.action_type != "renewal" and self.renewal is not None:
            raise ValueError("renewal payload is only valid for renewal action")
        return self


class ContractExpiryAlert(BaseModel):
    contract_id: UUID
    contract_number: str
    person_id: UUID
    effective_to: date
    expiry_notice_days: int
    days_remaining: int
    status: str


class ContractExpiryAlertPage(BaseModel):
    items: list[ContractExpiryAlert]
    total: int
    as_of: date
    days_ahead: int


class ContractStatusProcessRequest(BaseModel):
    as_of: date | None = None


class ContractStatusProcessResponse(BaseModel):
    processed_ids: list[UUID]


class ContractPage(BaseModel):
    items: list[ContractResponse]
    total: int
    limit: int
    offset: int


class HrEventCreate(BaseModel):
    idempotency_key: UUID | None = None
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
    idempotency_key: UUID | None = None
    execution_mode: Literal["direct", "approval"] = "approval"
    effective_date: date
    reason: str = Field(min_length=1, max_length=500)


class HrEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_number: str
    idempotency_key: UUID | None
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


class HrEventPage(BaseModel):
    items: list[HrEventResponse]
    total: int
    limit: int
    offset: int


class HrEventProcessRequest(BaseModel):
    as_of: date | None = None


class HrEventProcessResponse(BaseModel):
    processed_ids: list[UUID]
    failed: list[dict[str, str]]


class WorkflowPublishResponse(BaseModel):
    definition_id: UUID
    version: int
    status: str


class WorkflowInstanceCreate(BaseModel):
    workflow_definition_id: UUID
    business_object_type: str = Field(min_length=1, max_length=50)
    business_object_id: UUID
    context: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def protect_runtime_context(self) -> "WorkflowInstanceCreate":
        if any(key.startswith("_workflow_") for key in self.context):
            raise ValueError("_workflow_前缀由流程引擎保留")
        return self


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


class WorkflowTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_instance_id: UUID
    node_code: str
    sign_mode: str
    assignee_type: str
    assignee_ref: str
    status: str
    decision: str | None
    comment: str | None
    decided_by: UUID | None
    decided_at: datetime | None


class WorkflowTaskPage(BaseModel):
    items: list[WorkflowTaskResponse]
    total: int
    limit: int
    offset: int


class WorkflowInstanceDetailResponse(BaseModel):
    instance: WorkflowInstanceResponse
    tasks: list[WorkflowTaskResponse]


class WorkflowInstancePage(BaseModel):
    items: list[WorkflowInstanceResponse]
    total: int
    limit: int
    offset: int


class WorkflowTaskDecision(BaseModel):
    decision: Literal["approve", "reject"]
    comment: str | None = Field(default=None, max_length=2000)
