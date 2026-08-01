from datetime import date, datetime
from typing import Any
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

