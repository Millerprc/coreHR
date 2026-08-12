from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EffectiveDatedInput(BaseModel):
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def validate_effective_period(self) -> "EffectiveDatedInput":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to不能早于effective_from")
        return self


class PersonDocumentCreate(EffectiveDatedInput):
    document_type_code: str = Field(min_length=1, max_length=50)
    document_number: str = Field(min_length=1, max_length=255)
    issuing_country_code: str = Field(min_length=2, max_length=3)
    issue_date: date | None = None
    expiry_date: date | None = None
    is_primary: bool = False
    verification_status: str = Field(default="unverified", min_length=1, max_length=30)
    change_reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_document_dates(self) -> "PersonDocumentCreate":
        if not any(character.isalnum() for character in self.document_number):
            raise ValueError("document_number规范化后不能为空")
        if (
            self.issue_date is not None
            and self.expiry_date is not None
            and self.expiry_date < self.issue_date
        ):
            raise ValueError("expiry_date不能早于issue_date")
        return self


class PersonDocumentUpdate(BaseModel):
    document_type_code: str | None = Field(default=None, min_length=1, max_length=50)
    document_number: str | None = Field(default=None, min_length=1, max_length=255)
    issuing_country_code: str | None = Field(default=None, min_length=2, max_length=3)
    issue_date: date | None = None
    expiry_date: date | None = None
    is_primary: bool | None = None
    verification_status: str | None = Field(default=None, min_length=1, max_length=30)
    effective_from: date | None = None
    effective_to: date | None = None
    change_reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_document_number(self) -> "PersonDocumentUpdate":
        if (
            self.document_number is not None
            and not any(character.isalnum() for character in self.document_number)
        ):
            raise ValueError("document_number规范化后不能为空")
        return self


class PersonDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    person_id: UUID
    document_type_code: str
    masked_document_number: str
    issuing_country_code: str
    issue_date: date | None
    expiry_date: date | None
    is_primary: bool
    verification_status: str
    effective_from: date
    effective_to: date | None
    created_at: datetime
    updated_at: datetime


ContactType = Literal["personal_phone", "work_phone", "personal_email", "work_email"]


class PersonContactCreate(EffectiveDatedInput):
    contact_type: ContactType
    contact_value: str = Field(min_length=1, max_length=320)
    is_primary: bool = False
    change_reason: str = Field(min_length=1, max_length=500)


class PersonContactUpdate(BaseModel):
    contact_type: ContactType | None = None
    contact_value: str | None = Field(default=None, min_length=1, max_length=320)
    is_primary: bool | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    change_reason: str = Field(min_length=1, max_length=500)


class PersonContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    person_id: UUID
    contact_type: ContactType
    masked_contact_value: str
    is_primary: bool
    effective_from: date
    effective_to: date | None
    created_at: datetime
    updated_at: datetime


class PersonAddressCreate(EffectiveDatedInput):
    address_type: Literal["residential", "mailing"]
    country_code: str = Field(min_length=2, max_length=3)
    region_code: str | None = Field(default=None, max_length=50)
    address_detail: str = Field(min_length=1, max_length=500)
    change_reason: str = Field(min_length=1, max_length=500)


class PersonAddressUpdate(BaseModel):
    address_type: Literal["residential", "mailing"] | None = None
    country_code: str | None = Field(default=None, min_length=2, max_length=3)
    region_code: str | None = Field(default=None, max_length=50)
    address_detail: str | None = Field(default=None, min_length=1, max_length=500)
    effective_from: date | None = None
    effective_to: date | None = None
    change_reason: str = Field(min_length=1, max_length=500)


class PersonAddressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    person_id: UUID
    address_type: str
    country_code: str
    region_code: str | None
    masked_address_detail: str
    effective_from: date
    effective_to: date | None
    created_at: datetime
    updated_at: datetime


class EmergencyContactCreate(EffectiveDatedInput):
    name: str = Field(min_length=1, max_length=200)
    relationship_code: str = Field(min_length=1, max_length=50)
    phone: str = Field(min_length=1, max_length=50)
    change_reason: str = Field(min_length=1, max_length=500)


class EmergencyContactUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    relationship_code: str | None = Field(default=None, min_length=1, max_length=50)
    phone: str | None = Field(default=None, min_length=1, max_length=50)
    effective_from: date | None = None
    effective_to: date | None = None
    change_reason: str = Field(min_length=1, max_length=500)


class EmergencyContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    person_id: UUID
    masked_name: str
    relationship_code: str
    masked_phone: str
    effective_from: date
    effective_to: date | None
    created_at: datetime
    updated_at: datetime


class EducationRecordCreate(EffectiveDatedInput):
    institution_name: str = Field(min_length=1, max_length=300)
    education_level_code: str = Field(min_length=1, max_length=50)
    major_name: str | None = Field(default=None, max_length=200)
    study_start_date: date
    study_end_date: date | None = None
    change_reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_study_period(self) -> "EducationRecordCreate":
        if self.study_end_date is not None and self.study_end_date < self.study_start_date:
            raise ValueError("study_end_date不能早于study_start_date")
        return self


class EducationRecordUpdate(BaseModel):
    institution_name: str | None = Field(default=None, min_length=1, max_length=300)
    education_level_code: str | None = Field(default=None, min_length=1, max_length=50)
    major_name: str | None = Field(default=None, max_length=200)
    study_start_date: date | None = None
    study_end_date: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    change_reason: str = Field(min_length=1, max_length=500)


class EducationRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    person_id: UUID
    masked_institution_name: str
    education_level_code: str
    masked_major_name: str | None
    study_start_date: date
    study_end_date: date | None
    effective_from: date
    effective_to: date | None
    created_at: datetime
    updated_at: datetime


class WorkExperienceCreate(EffectiveDatedInput):
    employer_name: str = Field(min_length=1, max_length=300)
    job_title: str | None = Field(default=None, max_length=200)
    work_start_date: date
    work_end_date: date | None = None
    change_reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_work_period(self) -> "WorkExperienceCreate":
        if self.work_end_date is not None and self.work_end_date < self.work_start_date:
            raise ValueError("work_end_date不能早于work_start_date")
        return self


class WorkExperienceUpdate(BaseModel):
    employer_name: str | None = Field(default=None, min_length=1, max_length=300)
    job_title: str | None = Field(default=None, max_length=200)
    work_start_date: date | None = None
    work_end_date: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    change_reason: str = Field(min_length=1, max_length=500)


class WorkExperienceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    person_id: UUID
    masked_employer_name: str
    masked_job_title: str | None
    work_start_date: date
    work_end_date: date | None
    effective_from: date
    effective_to: date | None
    created_at: datetime
    updated_at: datetime


class FamilyMemberCreate(EffectiveDatedInput):
    name: str = Field(min_length=1, max_length=200)
    relationship_code: str = Field(min_length=1, max_length=50)
    change_reason: str = Field(min_length=1, max_length=500)


class FamilyMemberUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    relationship_code: str | None = Field(default=None, min_length=1, max_length=50)
    effective_from: date | None = None
    effective_to: date | None = None
    change_reason: str = Field(min_length=1, max_length=500)


class FamilyMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    person_id: UUID
    masked_name: str
    relationship_code: str
    effective_from: date
    effective_to: date | None
    created_at: datetime
    updated_at: datetime


SensitiveRecordType = Literal[
    "document",
    "contact",
    "address",
    "emergency_contact",
    "education",
    "work_experience",
    "family_member",
]


class SensitiveRevealRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class SensitiveRevealResponse(BaseModel):
    record_type: SensitiveRecordType
    record_id: UUID
    field_code: str
    value: str


class SensitiveRecordExpire(BaseModel):
    effective_to: date
    reason: str = Field(min_length=1, max_length=500)
