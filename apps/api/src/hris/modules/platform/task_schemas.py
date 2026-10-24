# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""Background task API schemas.

Requirement: D-110 — 任务响应只暴露任务坐标与统计值。
``payload`` 里放的是批次 id、发起人 id、链路 id、执行原因，
不包含姓名、手机号等个人信息，因此可以原样返回给治理端查看。
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BackgroundTaskSummaryResponse(BaseModel):
    """任务摘要：入队即返回的最小视图。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_type: str
    status: str
    created_at: datetime


class BackgroundTaskResponse(BaseModel):
    """任务详情：全字段视图。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_type: str
    status: str
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error_code: str | None
    attempts: int
    max_attempts: int
    next_attempt_at: datetime
    lease_owner: str | None
    lease_expires_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    created_by: UUID | None
    idempotency_key: str | None
    progress: str | None
    created_at: datetime
    updated_at: datetime


class BackgroundTaskListResponse(BaseModel):
    """任务列表：分页视图。"""

    items: list[BackgroundTaskResponse]
    total: int
    limit: int
    offset: int
