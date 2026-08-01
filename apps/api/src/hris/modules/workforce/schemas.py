from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OrganizationTypeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50, pattern=r"^[A-Z0-9_]+$")
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = Field(default=0, ge=0)


class OrganizationTypeResponse(OrganizationTypeCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class OrganizationCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50, pattern=r"^[0-9]+$")
    name: str = Field(min_length=1, max_length=200)
    organization_type_code: str = Field(min_length=1, max_length=50)
    parent_organization_id: UUID | None = None
    country_code: str | None = Field(default=None, min_length=2, max_length=3)
    effective_from: date
    effective_to: date | None = None
    change_reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_effective_period(self) -> "OrganizationCreate":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to不能早于effective_from")
        return self


class OrganizationResponse(BaseModel):
    id: UUID
    code: str
    name: str
    organization_type_code: str
    organization_type_name: str
    parent_organization_id: UUID | None
    country_code: str | None
    status: str
    effective_from: date
    effective_to: date | None
    version: int


class OrganizationListResponse(BaseModel):
    items: list[OrganizationResponse]
    total: int
    limit: int
    offset: int

