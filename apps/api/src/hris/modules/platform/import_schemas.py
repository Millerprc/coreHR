import json
from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


ImportEntityType = Literal[
    "dictionary",
    "dictionary_item",
    "organization_type",
    "legal_entity",
    "job",
    "organization",
]


class ImportRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class ImportSourceRow(ImportRequest):
    source_record_id: str = Field(min_length=1, max_length=255)
    data: dict[str, Any]

    @model_validator(mode="after")
    def limit_row_payload(self) -> "ImportSourceRow":
        if not self.data:
            raise ValueError("导入行data不能为空")
        if len(self.data) > 20:
            raise ValueError("单行最多允许20个主数据字段")
        if len(json.dumps(self.data, ensure_ascii=False)) > 10_000:
            raise ValueError("单行主数据内容不能超过10000字符")
        return self


class ImportBatchValidate(ImportRequest):
    entity_type: ImportEntityType
    source_system: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
    source_table: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    file_name: str | None = Field(default=None, max_length=255)
    idempotency_key: UUID
    rows: list[ImportSourceRow] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def reject_duplicate_source_ids(self) -> "ImportBatchValidate":
        source_ids = [row.source_record_id for row in self.rows]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("同一批次source_record_id不能重复")
        return self


class DictionaryItemImport(ImportRequest):
    dictionary_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,99}$")
    code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{0,99}$")
    name: str = Field(min_length=1, max_length=200)
    english_name: str | None = Field(default=None, max_length=200)
    parent_item_code: str | None = Field(
        default=None,
        pattern=r"^[A-Z0-9][A-Z0-9_-]{0,99}$",
    )
    sort_order: int = Field(default=0, ge=0)
    description: str | None = Field(default=None, max_length=1000)


class OrganizationImport(ImportRequest):
    code: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,49}$")
    name: str = Field(min_length=1, max_length=200)
    organization_type_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{0,49}$")
    parent_code: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,49}$",
    )
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2,3}$")
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def validate_effective_period(self) -> "OrganizationImport":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to不能早于effective_from")
        return self


class ImportRowError(BaseModel):
    code: str
    field: str | None = None
    message: str


class ImportBatchRowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    row_number: int
    source_record_id: str
    status: str
    errors: list[ImportRowError]
    target_type: str | None
    target_id: UUID | None


class ImportBatchSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_type: str
    source_system: str
    source_table: str
    file_name: str | None
    idempotency_key: UUID
    status: str
    total_rows: int
    valid_rows: int
    rejected_rows: int
    imported_rows: int
    skipped_rows: int
    created_by: UUID
    executed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ImportBatchResponse(ImportBatchSummaryResponse):
    rows: list[ImportBatchRowResponse]


class ImportBatchListResponse(BaseModel):
    items: list[ImportBatchSummaryResponse]
    total: int
    limit: int
    offset: int


class ImportBatchExecute(ImportRequest):
    reason: str = Field(min_length=1, max_length=500)


class ImportTemplateResponse(BaseModel):
    entity_type: ImportEntityType
    columns: list[str]
    required_columns: list[str]
