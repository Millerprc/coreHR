# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""批量异动方案的接口契约。

请求字段语义与现有单条人事事件（HrEventCreate）保持一致，
差别只在于：明细不支持 execution_mode / workflow_instance_id，
这两项由方案在提交审批时统一决定。
"""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BatchChangeCreate(BaseModel):
    """创建批量异动方案草稿。"""

    title: str = Field(min_length=1, max_length=200)
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("title")
    @classmethod
    def reject_blank_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("方案标题不能为空白")
        return stripped

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class BatchChangeLineCreate(BaseModel):
    """方案明细，字段语义与 HrEventCreate 对齐。"""

    idempotency_key: UUID | None = None
    event_type: str = Field(min_length=1, max_length=50)
    object_type: str = Field(min_length=1, max_length=50)
    object_id: UUID
    effective_date: date
    reason: str = Field(min_length=1, max_length=500)
    before_payload: dict[str, Any] = Field(default_factory=dict)
    planned_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("reason must not be blank")
        return normalized


class BatchChangeLinesCreate(BaseModel):
    """追加明细请求，一次可以提交多条。"""

    # Requirement: HR-BATCH-001 — 条数上限由服务端按方案总行数判定，
    # 因此这里不做条数限制，超限统一返回 BATCH_CHANGE_LINE_LIMIT_EXCEEDED。
    lines: list[BatchChangeLineCreate]


class BatchChangeSubmit(BaseModel):
    """提交审批请求。"""

    # Requirement: HR-BATCH-009 — 不指定流程定义时使用默认的批量异动审批流程。
    workflow_definition_id: UUID | None = None


class BatchChangeSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_number: str
    title: str
    status: str
    line_count: int
    reason: str | None
    workflow_instance_id: UUID | None
    submitted_at: datetime | None
    approved_at: datetime | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class BatchChangeLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_number: str
    idempotency_key: UUID | None
    event_type: str
    object_type: str
    object_id: UUID
    effective_date: date
    status: str
    reason: str
    before_payload: dict[str, Any]
    planned_payload: dict[str, Any]
    workflow_instance_id: UUID | None


class BatchChangeDetailResponse(BatchChangeSummaryResponse):
    """方案详情，含全部明细。"""

    lines: list[BatchChangeLineResponse]


class BatchChangeListResponse(BaseModel):
    items: list[BatchChangeSummaryResponse]
    total: int
    page: int
    page_size: int


class BatchChangeLinesResponse(BaseModel):
    """追加明细结果：created 为新建明细，skipped 为幂等命中的既有明细。"""

    batch: BatchChangeSummaryResponse
    created: list[BatchChangeLineResponse]
    skipped: list[BatchChangeLineResponse]
