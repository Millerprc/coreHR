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
    "job_dimension",
    "job_dimension_version",
    "job",
    "job_version",
    "organization",
    "person_basic",
]

ExportEntityType = Literal[
    "dictionary",
    "dictionary_item",
    "organization_type",
    "legal_entity",
    "job_dimension",
    "job",
    "organization",
    "person_basic",
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


class PersonBasicImport(ImportRequest):
    employee_number: str = Field(pattern=r"^[0-9]{6}$")
    legal_name: str = Field(min_length=1, max_length=200)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    former_name: str | None = Field(default=None, max_length=200)


class JobDimensionImport(ImportRequest):
    dimension_type: Literal["LEVEL", "GRADE", "CLASS", "SEQUENCE"]
    dimension_code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_.-]{0,49}$")
    dimension_name: str = Field(min_length=1, max_length=200)
    parent_dimension_type: Literal["LEVEL", "GRADE", "CLASS", "SEQUENCE"] | None = None
    parent_dimension_code: str | None = Field(
        default=None,
        pattern=r"^[A-Z0-9][A-Z0-9_.-]{0,49}$",
    )
    sort_order: int = Field(default=0, ge=0)
    effective_from: date
    effective_to: date | None = None
    status: Literal["active", "inactive"] = "active"
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_dimension(self) -> "JobDimensionImport":
        if (self.parent_dimension_type is None) != (self.parent_dimension_code is None):
            raise ValueError("父维度类型和代码必须同时填写")
        if (
            self.parent_dimension_type == self.dimension_type
            and self.parent_dimension_code == self.dimension_code
        ):
            raise ValueError("职务维度不能以自身为父级")
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to不能早于effective_from")
        return self


class JobImport(ImportRequest):
    job_code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_.-]{0,49}$")
    job_name: str = Field(min_length=1, max_length=200)
    level_code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_.-]{0,49}$")
    grade_code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_.-]{0,49}$")
    class_code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_.-]{0,49}$")
    sequence_code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_.-]{0,49}$")
    effective_from: date
    effective_to: date | None = None
    status: Literal["active", "inactive"] = "active"
    source_job_id: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_effective_period(self) -> "JobImport":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to不能早于effective_from")
        return self


class JobDimensionVersionImport(JobDimensionImport):
    change_reason: str = Field(min_length=1, max_length=500)


class JobVersionImport(JobImport):
    change_reason: str = Field(min_length=1, max_length=500)


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
