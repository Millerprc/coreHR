from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AttendanceRuleSetCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80, pattern=r"^[A-Z0-9_]+$")
    name: str = Field(min_length=1, max_length=200)
    timezone: str = Field(min_length=1, max_length=100)
    effective_from: date
    effective_to: date | None = None
    rules: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_rule_set(self) -> "AttendanceRuleSetCreate":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to不能早于effective_from")
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone必须是有效的IANA时区") from exc
        return self


class AttendanceRuleSetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    timezone: str
    version: int
    status: str
    effective_from: date
    effective_to: date | None
    rules: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AttendanceRuleSetListResponse(BaseModel):
    items: list[AttendanceRuleSetResponse]
    total: int
    limit: int
    offset: int


class AttendanceRuleSetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    timezone: str | None = Field(default=None, min_length=1, max_length=100)
    effective_from: date | None = None
    effective_to: date | None = None
    rules: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_rule_set(self) -> "AttendanceRuleSetUpdate":
        if not self.model_dump(exclude_unset=True):
            raise ValueError("at least one rule-set field must be changed")
        if self.timezone is not None:
            try:
                ZoneInfo(self.timezone)
            except ZoneInfoNotFoundError as exc:
                raise ValueError("timezone must be a valid IANA timezone") from exc
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be earlier than effective_from")
        return self


class AttendanceRuleSetVersionCreate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    timezone: str | None = Field(default=None, min_length=1, max_length=100)
    effective_from: date
    effective_to: date | None = None
    rules: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_version(self) -> "AttendanceRuleSetVersionCreate":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be earlier than effective_from")
        if self.timezone is not None:
            try:
                ZoneInfo(self.timezone)
            except ZoneInfoNotFoundError as exc:
                raise ValueError("timezone must be a valid IANA timezone") from exc
        return self
