from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConfigurationRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class DictionaryCreate(ConfigurationRequest):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,99}$")
    name: str = Field(min_length=1, max_length=200)
    english_name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=1000)


class DictionaryItemCreate(ConfigurationRequest):
    code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{0,99}$")
    name: str = Field(min_length=1, max_length=200)
    english_name: str | None = Field(default=None, max_length=200)
    parent_item_id: UUID | None = None
    sort_order: int = Field(default=0, ge=0)
    description: str | None = Field(default=None, max_length=1000)


class DictionaryItemUpdate(ConfigurationRequest):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    english_name: str | None = Field(default=None, max_length=200)
    parent_item_id: UUID | None = None
    sort_order: int | None = Field(default=None, ge=0)
    description: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def require_change(self) -> "DictionaryItemUpdate":
        if not self.model_fields_set:
            raise ValueError("至少提供一个修改字段")
        return self


class DictionaryItemDeactivate(ConfigurationRequest):
    reason: str = Field(min_length=1, max_length=500)


class DictionaryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dictionary_id: UUID
    parent_item_id: UUID | None
    code: str
    name: str
    english_name: str | None
    sort_order: int
    level: int
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DictionaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    english_name: str | None
    description: str | None
    source: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DictionaryListResponse(BaseModel):
    items: list[DictionaryResponse]
    total: int
    limit: int
    offset: int


class DictionaryItemListResponse(BaseModel):
    items: list[DictionaryItemResponse]
    total: int
